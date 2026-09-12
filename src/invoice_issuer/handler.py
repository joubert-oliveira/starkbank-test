"""Lambda that issues a random batch of Invoices on each invocation (RF1)."""

import logging
import os
import random
from typing import Optional

import starkbank

from src.common.random_person import generate_person
from src.common.starkbank_client import get_project

logger = logging.getLogger()
logger.setLevel(logging.INFO)

MIN_INVOICES_PER_BATCH = 8
MAX_INVOICES_PER_BATCH = 12
MIN_AMOUNT_CENTS = int(os.environ.get("INVOICE_MIN_AMOUNT_CENTS", "1000"))  # R$ 10,00
MAX_AMOUNT_CENTS = int(os.environ.get("INVOICE_MAX_AMOUNT_CENTS", "100000"))  # R$ 1000,00


class UniquePersonGenerator:
    """Generates random people whose tax IDs never repeat within one instance (RF1.2)."""

    def __init__(self, min_amount_cents: int, max_amount_cents: int):
        self._min_amount_cents = min_amount_cents
        self._max_amount_cents = max_amount_cents
        self._seen_tax_ids = set()

    def next(self) -> dict:
        person = generate_person(self._min_amount_cents, self._max_amount_cents)
        while person["tax_id"] in self._seen_tax_ids:
            person = generate_person(self._min_amount_cents, self._max_amount_cents)
        self._seen_tax_ids.add(person["tax_id"])
        return person


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


def handler(event, context):
    project = get_project()
    batch_size = random.randint(MIN_INVOICES_PER_BATCH, MAX_INVOICES_PER_BATCH)
    person_generator = UniquePersonGenerator(MIN_AMOUNT_CENTS, MAX_AMOUNT_CENTS)
    issuer = InvoiceBatchIssuer(project, person_generator)
    return issuer.issue_batch(batch_size)
