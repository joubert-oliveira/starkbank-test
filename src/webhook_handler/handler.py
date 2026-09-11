import base64
import json
import logging
import os
import time

import boto3
import starkbank
from botocore.exceptions import ClientError

from src.common.starkbank_client import get_project

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLE_NAME_ENV_VAR = "PROCESSED_EVENTS_TABLE"
PROCESSED_EVENT_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days, matches the table's TTL attribute
DEFAULT_TABLE_NAME = "processed-events"

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


def handler(event, context):
    content = _get_body(event)
    signature = _get_header(event, "digital-signature")

    try:
        parsed_event = starkbank.event.parse(content=content, signature=signature, user=get_project())
    except starkbank.error.InvalidSignatureError:
        logger.warning("invalid webhook signature")
        return _response(400, {"message": "invalid signature"})

    if parsed_event.subscription != INVOICE_SUBSCRIPTION or parsed_event.log.type != CREDITED_LOG_TYPE:
        logger.info("ignoring event id=%s subscription=%s", parsed_event.id, parsed_event.subscription)
        return _response(200, {"message": "ignored"})

    if not _claim_event(parsed_event.id):
        logger.info("event id=%s already processed, skipping", parsed_event.id)
        return _response(200, {"message": "already processed"})

    net_amount = parsed_event.log.invoice.amount - parsed_event.log.invoice.fee

    try:
        transfer = starkbank.transfer.create(
            [starkbank.Transfer(amount=net_amount, **TRANSFER_DESTINATION)],
            user=get_project(),
        )[0]
    except Exception:
        _mark_result(parsed_event.id, status=STATUS_FAILED, transfer_id=None)
        logger.exception("failed to create transfer for event=%s", parsed_event.id)
        return _response(500, {"message": "transfer failed"})

    _mark_result(parsed_event.id, status=STATUS_COMPLETED, transfer_id=transfer.id)
    logger.info("transfer created id=%s amount=%s for event=%s", transfer.id, net_amount, parsed_event.id)
    return _response(200, {"message": "transfer created", "transfer_id": transfer.id})


def _get_body(event) -> str:
    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")
    return body


def _get_header(event, header_name: str):
    headers = event.get("headers") or {}
    for key, value in headers.items():
        if key.lower() == header_name:
            return value
    return None


def _claim_event(event_id: str) -> bool:
    """Atomically claims an event for processing.

    Allows retrying events stuck in "processing"/"failed" (e.g. after a
    prior Transfer failure or a Lambda timeout) but blocks duplicates of
    events already marked "completed".
    """
    try:
        _table().put_item(
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


def _mark_result(event_id: str, status: str, transfer_id):
    _table().update_item(
        Key={"event_id": event_id},
        UpdateExpression="SET #status = :status, transfer_id = :transfer_id",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":status": status, ":transfer_id": transfer_id},
    )


def _table():
    table_name = os.environ.get(TABLE_NAME_ENV_VAR, DEFAULT_TABLE_NAME)
    return boto3.resource("dynamodb").Table(table_name)


def _response(status_code: int, body: dict) -> dict:
    return {"statusCode": status_code, "body": json.dumps(body)}
