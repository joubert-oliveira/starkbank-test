"""Lambda that issues a random batch of Invoices on each invocation (RF1)."""

import os
import random

from src.common.starkbank_client import get_project
from src.invoice_issuer.generator import UniquePersonGenerator
from src.invoice_issuer.service import InvoiceBatchIssuer

MIN_INVOICES_PER_BATCH = 8
MAX_INVOICES_PER_BATCH = 12
MIN_AMOUNT_CENTS = int(os.environ.get("INVOICE_MIN_AMOUNT_CENTS", "1000"))  # R$ 10,00
MAX_AMOUNT_CENTS = int(os.environ.get("INVOICE_MAX_AMOUNT_CENTS", "100000"))  # R$ 1000,00


def handler(event, context):
    project = get_project()
    batch_size = random.randint(MIN_INVOICES_PER_BATCH, MAX_INVOICES_PER_BATCH)
    person_generator = UniquePersonGenerator(MIN_AMOUNT_CENTS, MAX_AMOUNT_CENTS)
    issuer = InvoiceBatchIssuer(project, person_generator)
    return issuer.issue_batch(batch_size)
