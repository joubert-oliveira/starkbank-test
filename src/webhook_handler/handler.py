"""Webhook receiver for Stark Bank Invoice "credited" events.

On each valid, non-duplicate credit, settles the net amount (amount - fee)
to the fixed destination account via a Transfer (RF2, RF3).
"""

import base64
import json
import logging
import os
import time
from typing import Optional

import boto3
import starkbank
from botocore.exceptions import ClientError

from src.common.starkbank_client import get_project

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLE_NAME_ENV_VAR = "PROCESSED_EVENTS_TABLE"
DEFAULT_TABLE_NAME = "processed-events"
PROCESSED_EVENT_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days, matches the table's TTL attribute

INVOICE_SUBSCRIPTION = "invoice"
CREDITED_LOG_TYPE = "credited"

STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"

# Fixed destination account for the challenge (see specs/requirements.md, RF3.1).
TRANSFER_DESTINATION = {
    "bank_code": "20018183",
    "branch_code": "0001",
    "account_number": "6341320293482496",
    "name": "Stark Bank S.A.",
    "tax_id": "20.018.183/0001-80",
    "account_type": "payment",
}


class ProcessedEventRepository:
    """Tracks which webhook events have already been settled.

    Backed by a DynamoDB table keyed by event_id, chosen specifically because
    single-item writes there give us the ACID guarantees this idempotency
    check depends on:
      - Atomicity: try_claim's put_item either fully succeeds or fully fails,
        never leaves a half-written record.
      - Consistency: the conditional expression enforces the invariant "an
        event already completed can never be claimed again", regardless of
        how many callers race for it.
      - Isolation: DynamoDB serializes concurrent writes to the same item, so
        two overlapping webhook redeliveries for the same event can't both
        win try_claim.
      - Durability: once acknowledged, a record survives past this Lambda's
        ephemeral execution environment.
    """

    def __init__(self, table_name: Optional[str] = None):
        self._table_name = table_name or os.environ.get(TABLE_NAME_ENV_VAR, DEFAULT_TABLE_NAME)

    def try_claim(self, event_id: str) -> bool:
        """Marks an event as being processed. Returns False if already completed."""
        try:
            self._table().put_item(
                Item={
                    "event_id": event_id,
                    "status": STATUS_PROCESSING,
                    "ttl": int(time.time()) + PROCESSED_EVENT_TTL_SECONDS,
                },
                ConditionExpression="attribute_not_exists(event_id) OR #status <> :completed",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":completed": STATUS_COMPLETED},
            )
            return True
        except ClientError as error:
            if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise

    def mark_completed(self, event_id: str, transfer_id: str) -> None:
        self._update(event_id, status=STATUS_COMPLETED, transfer_id=transfer_id)

    def mark_failed(self, event_id: str) -> None:
        self._update(event_id, status=STATUS_FAILED, transfer_id=None)

    def _update(self, event_id: str, status: str, transfer_id) -> None:
        self._table().update_item(
            Key={"event_id": event_id},
            UpdateExpression="SET #status = :status, transfer_id = :transfer_id",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":status": status, ":transfer_id": transfer_id},
        )

    def _table(self):
        return boto3.resource("dynamodb").Table(self._table_name)


class CreditSettlementService:
    """Settles a credited Invoice by transferring its net amount (RF3)."""

    def __init__(self, destination: dict):
        self._destination = destination

    def settle(self, event_id: str, invoice_log) -> "starkbank.Transfer":
        gross_amount = invoice_log.amount
        fee = invoice_log.fee
        net_amount = gross_amount - fee
        logger.info(
            "credited event=%s gross_amount=%s fee=%s net_amount=%s",
            event_id,
            gross_amount,
            fee,
            net_amount,
        )

        # external_id ties the Transfer to this event. DynamoDB and Stark
        # Bank are two independent systems, so a crash between a successful
        # Transfer and the DynamoDB write that records it can't be made
        # atomic end-to-end. Setting external_id=event_id turns that gap
        # from a silent double payment into a loud, safe failure: a retry
        # rejects instead of moving the money twice.
        transfer = starkbank.transfer.create(
            [starkbank.Transfer(amount=net_amount, external_id=event_id, **self._destination)],
            user=get_project(),
        )[0]
        logger.info("transfer created id=%s amount=%s for event=%s", transfer.id, net_amount, event_id)
        return transfer


_event_repository = ProcessedEventRepository()
_settlement_service = CreditSettlementService(TRANSFER_DESTINATION)


def handler(event, context):
    content = _get_body(event)
    signature = _get_header(event, "digital-signature")

    try:
        parsed_event = starkbank.event.parse(content=content, signature=signature, user=get_project())
    except starkbank.error.InvalidSignatureError:
        logger.warning("invalid webhook signature")
        return _response(400, {"message": "invalid signature"})

    if not _is_credited_invoice(parsed_event):
        logger.info("ignoring event id=%s subscription=%s", parsed_event.id, parsed_event.subscription)
        return _response(200, {"message": "ignored"})

    if not _event_repository.try_claim(parsed_event.id):
        logger.info("event id=%s already processed, skipping", parsed_event.id)
        return _response(200, {"message": "already processed"})

    try:
        transfer = _settlement_service.settle(parsed_event.id, parsed_event.log.invoice)
    except Exception:
        _event_repository.mark_failed(parsed_event.id)
        logger.exception("failed to create transfer for event=%s", parsed_event.id)
        return _response(500, {"message": "transfer failed"})

    _event_repository.mark_completed(parsed_event.id, transfer.id)
    return _response(200, {"message": "transfer created", "transfer_id": transfer.id})


def _is_credited_invoice(parsed_event) -> bool:
    return parsed_event.subscription == INVOICE_SUBSCRIPTION and parsed_event.log.type == CREDITED_LOG_TYPE


def _get_body(event: dict) -> str:
    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")
    return body


def _get_header(event: dict, header_name: str) -> Optional[str]:
    headers = event.get("headers") or {}
    for key, value in headers.items():
        if key.lower() == header_name:
            return value
    return None


def _response(status_code: int, body: dict) -> dict:
    return {"statusCode": status_code, "body": json.dumps(body)}
