"""Webhook receiver for Stark Bank Invoice "credited" events.

On each valid, non-duplicate credit, settles the net amount (amount - fee)
to the fixed destination account via a Transfer (RF2, RF3).
"""

import base64
import json
from typing import Optional

import starkbank

from src.common.logging_utils import get_logger
from src.common.starkbank_client import get_project
from src.webhook_handler.repository import ProcessedEventRepository
from src.webhook_handler.service import TRANSFER_DESTINATION, CreditSettlementService

logger = get_logger("WEBHOOK_HANDLER")

INVOICE_SUBSCRIPTION = "invoice"
CREDITED_LOG_TYPE = "credited"

# Stark Bank's static outbound IPs for webhook delivery (docs.starkbank.com).
# Checked here, in application code, because AWS WAFv2's WebACLAssociation
# does not support API Gateway HTTP APIs (only REST APIs, ALB, AppSync,
# Cognito, App Runner, Verified Access and Amplify) — see ADR.md item 14c.
STARK_BANK_WEBHOOK_IPS = {
    "35.199.76.124",  # production
    "34.85.188.162",  # production
    "35.247.226.240",  # sandbox
    "35.245.182.229",  # sandbox
}

_event_repository = ProcessedEventRepository()
_settlement_service = CreditSettlementService(TRANSFER_DESTINATION)


def handler(event, context):
    if not _is_from_stark_bank(event):
        source_ip = event.get("requestContext", {}).get("http", {}).get("sourceIp")
        logger.warning("rejected webhook request from unexpected source_ip=%s", source_ip)
        return _response(403, {"message": "forbidden"})

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


def _is_from_stark_bank(event: dict) -> bool:
    source_ip = event.get("requestContext", {}).get("http", {}).get("sourceIp")
    return source_ip in STARK_BANK_WEBHOOK_IPS


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
