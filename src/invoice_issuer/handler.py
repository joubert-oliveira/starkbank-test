import logging
import os
import random

import starkbank

from src.common.random_person import generate_person
from src.common.starkbank_client import get_project

logger = logging.getLogger()
logger.setLevel(logging.INFO)

MIN_INVOICES_PER_BATCH = 8
MAX_INVOICES_PER_BATCH = 12
MIN_AMOUNT_CENTS = int(os.environ.get("INVOICE_MIN_AMOUNT_CENTS", "1000"))  # R$ 10,00
MAX_AMOUNT_CENTS = int(os.environ.get("INVOICE_MAX_AMOUNT_CENTS", "100000"))  # R$ 1000,00


def handler(event, context):
    project = get_project()
    batch_size = random.randint(MIN_INVOICES_PER_BATCH, MAX_INVOICES_PER_BATCH)

    created_ids = []
    used_tax_ids = set()

    for _ in range(batch_size):
        person = _generate_unique_person(used_tax_ids)
        used_tax_ids.add(person["tax_id"])

        try:
            invoice = starkbank.invoice.create(
                [starkbank.Invoice(amount=person["amount"], tax_id=person["tax_id"], name=person["name"])],
                user=project,
            )[0]
            created_ids.append(invoice.id)
            logger.info("invoice created id=%s amount=%s", invoice.id, person["amount"])
        except Exception:
            logger.exception("failed to create invoice for tax_id=%s", person["tax_id"])

    logger.info("batch complete: %d/%d invoices created", len(created_ids), batch_size)
    return {"attempted": batch_size, "created": len(created_ids), "invoice_ids": created_ids}


def _generate_unique_person(used_tax_ids: set) -> dict:
    person = generate_person(MIN_AMOUNT_CENTS, MAX_AMOUNT_CENTS)
    while person["tax_id"] in used_tax_ids:
        person = generate_person(MIN_AMOUNT_CENTS, MAX_AMOUNT_CENTS)
    return person
