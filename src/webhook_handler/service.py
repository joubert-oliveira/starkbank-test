import starkbank

from src.common.logging_utils import get_logger
from src.common.starkbank_client import get_project

logger = get_logger("WEBHOOK_HANDLER")

# Fixed destination account for the challenge (see specs/requirements.md, RF3.1).
TRANSFER_DESTINATION = {
    "bank_code": "20018183",
    "branch_code": "0001",
    "account_number": "6341320293482496",
    "name": "Stark Bank S.A.",
    "tax_id": "20.018.183/0001-80",
    "account_type": "payment",
}


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
