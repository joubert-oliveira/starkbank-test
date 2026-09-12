from types import SimpleNamespace
from unittest.mock import patch

from src.invoice_issuer import handler as invoice_issuer


def _fake_invoice(id_):
    return [SimpleNamespace(id=id_)]


def _fix_batch_size(monkeypatch, size):
    monkeypatch.setattr(invoice_issuer, "MIN_INVOICES_PER_BATCH", size)
    monkeypatch.setattr(invoice_issuer, "MAX_INVOICES_PER_BATCH", size)


class _FixedPersonGenerator:
    def __init__(self, people):
        self._people = iter(people)

    def next(self):
        return next(self._people)


# --- UniquePersonGenerator ---------------------------------------------------


def test_unique_person_generator_never_repeats_tax_ids():
    generator = invoice_issuer.UniquePersonGenerator(1000, 2000)

    tax_ids = [generator.next()["tax_id"] for _ in range(50)]

    assert len(tax_ids) == len(set(tax_ids))


def test_unique_person_generator_retries_on_tax_id_collision():
    generator = invoice_issuer.UniquePersonGenerator(1000, 2000)
    generator._seen_tax_ids.add("11111111111")

    with patch("src.invoice_issuer.handler.generate_person") as mock_generate:
        mock_generate.side_effect = [
            {"name": "Foo", "tax_id": "11111111111", "amount": 100},
            {"name": "Bar", "tax_id": "22222222222", "amount": 200},
        ]
        person = generator.next()

    assert person["tax_id"] == "22222222222"
    assert mock_generate.call_count == 2


# --- InvoiceBatchIssuer -------------------------------------------------------


@patch("starkbank.invoice.create")
def test_invoice_batch_issuer_creates_full_batch_when_all_succeed(mock_create):
    people = [{"name": f"Person {i}", "tax_id": str(i) * 11, "amount": 100 + i} for i in range(3)]
    mock_create.side_effect = [_fake_invoice(str(i)) for i in range(3)]
    issuer = invoice_issuer.InvoiceBatchIssuer("fake-project", _FixedPersonGenerator(people))

    result = issuer.issue_batch(3)

    assert mock_create.call_count == 3
    assert result == {"attempted": 3, "created": 3, "invoice_ids": ["0", "1", "2"]}
    for call, person in zip(mock_create.call_args_list, people):
        invoice = call.args[0][0]
        assert invoice.amount == person["amount"]
        assert invoice.tax_id == person["tax_id"]
        assert call.kwargs["user"] == "fake-project"


@patch("starkbank.invoice.create")
def test_invoice_batch_issuer_continues_after_individual_failure(mock_create):
    people = [{"name": f"Person {i}", "tax_id": str(i) * 11, "amount": 100} for i in range(3)]
    mock_create.side_effect = [
        _fake_invoice("1"),
        Exception("stark bank api error"),
        _fake_invoice("3"),
    ]
    issuer = invoice_issuer.InvoiceBatchIssuer("fake-project", _FixedPersonGenerator(people))

    result = issuer.issue_batch(3)

    assert mock_create.call_count == 3
    assert result == {"attempted": 3, "created": 2, "invoice_ids": ["1", "3"]}


# --- handler (wiring) ---------------------------------------------------------


@patch("src.invoice_issuer.handler.get_project", return_value="fake-project")
@patch("starkbank.invoice.create")
def test_handler_issues_a_batch_of_the_configured_size(mock_create, mock_get_project, monkeypatch):
    _fix_batch_size(monkeypatch, 10)
    mock_create.side_effect = [_fake_invoice(str(i)) for i in range(10)]

    result = invoice_issuer.handler({}, None)

    assert mock_create.call_count == 10
    assert result["attempted"] == 10
    assert result["created"] == 10


@patch("src.invoice_issuer.handler.get_project", return_value="fake-project")
@patch("starkbank.invoice.create")
def test_handler_generates_amounts_within_configured_range(mock_create, mock_get_project, monkeypatch):
    _fix_batch_size(monkeypatch, 5)
    mock_create.side_effect = [_fake_invoice(str(i)) for i in range(5)]

    invoice_issuer.handler({}, None)

    for call in mock_create.call_args_list:
        invoice = call.args[0][0]
        assert invoice_issuer.MIN_AMOUNT_CENTS <= invoice.amount <= invoice_issuer.MAX_AMOUNT_CENTS
        assert len(invoice.tax_id) == 11
