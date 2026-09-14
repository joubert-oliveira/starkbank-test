from typing import Optional

import starkbank

from src.common.logging_utils import get_logger
from src.invoice_issuer.generator import UniquePersonGenerator

logger = get_logger("INVOICE_ISSUER")


class InvoiceBatchIssuer:
    """Issues a batch of Invoices, isolating individual failures (RF1.5)."""

    def __init__(self, project, person_generator: UniquePersonGenerator):
        self._project = project
        self._person_generator = person_generator

    def issue_batch(self, batch_size: int) -> dict:
        created_ids = []
        for _ in range(batch_size):
            invoice_id = self._issue_one(self._person_generator.next())
            if invoice_id is not None:
                created_ids.append(invoice_id)

        logger.info("batch complete: %d/%d invoices created", len(created_ids), batch_size)
        return {"attempted": batch_size, "created": len(created_ids), "invoice_ids": created_ids}

    def _issue_one(self, person: dict) -> Optional[str]:
        try:
            invoice = starkbank.invoice.create(
                [starkbank.Invoice(amount=person["amount"], tax_id=person["tax_id"], name=person["name"])],
                user=self._project,
            )[0]
        except Exception:
            logger.exception("failed to create invoice for tax_id=%s", person["tax_id"])
            return None

        logger.info("invoice created id=%s amount=%s", invoice.id, person["amount"])
        return invoice.id
