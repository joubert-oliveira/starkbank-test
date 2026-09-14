import logging

from src.common.logging_utils import get_logger


def test_get_logger_prefixes_messages_with_component_name(caplog):
    logger = get_logger("INVOICE_ISSUER")

    with caplog.at_level(logging.INFO):
        logger.info("batch complete: %d/%d invoices created", 8, 8)

    assert "[INVOICE_ISSUER] batch complete: 8/8 invoices created" in caplog.text


def test_get_logger_uses_different_prefix_per_component(caplog):
    invoice_logger = get_logger("INVOICE_ISSUER")
    webhook_logger = get_logger("WEBHOOK_HANDLER")

    with caplog.at_level(logging.INFO):
        invoice_logger.info("hello")
        webhook_logger.info("hello")

    assert "[INVOICE_ISSUER] hello" in caplog.text
    assert "[WEBHOOK_HANDLER] hello" in caplog.text
