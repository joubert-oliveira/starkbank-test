from types import SimpleNamespace
from unittest.mock import patch

from src.invoice_issuer import handler as invoice_issuer


def _fake_invoice(id_):
    return [SimpleNamespace(id=id_)]


def _fix_batch_size(monkeypatch, size):
    monkeypatch.setattr(invoice_issuer, "MIN_INVOICES_PER_BATCH", size)
    monkeypatch.setattr(invoice_issuer, "MAX_INVOICES_PER_BATCH", size)


@patch("src.invoice_issuer.handler.get_project", return_value="fake-project")
@patch("starkbank.invoice.create")
def test_handler_creates_full_batch_when_all_succeed(mock_create, mock_get_project, monkeypatch):
    _fix_batch_size(monkeypatch, 10)
    mock_create.side_effect = [_fake_invoice(str(i)) for i in range(10)]

    result = invoice_issuer.handler({}, None)

    assert mock_create.call_count == 10
    assert result == {"attempted": 10, "created": 10, "invoice_ids": [str(i) for i in range(10)]}


@patch("src.invoice_issuer.handler.get_project", return_value="fake-project")
@patch("starkbank.invoice.create")
def test_handler_continues_after_individual_failure(mock_create, mock_get_project, monkeypatch):
    _fix_batch_size(monkeypatch, 5)
    mock_create.side_effect = [
        _fake_invoice("1"),
        Exception("stark bank api error"),
        _fake_invoice("3"),
        Exception("stark bank api error"),
        _fake_invoice("5"),
    ]

    result = invoice_issuer.handler({}, None)

    assert mock_create.call_count == 5
    assert result == {"attempted": 5, "created": 3, "invoice_ids": ["1", "3", "5"]}


@patch("src.invoice_issuer.handler.get_project", return_value="fake-project")
@patch("starkbank.invoice.create")
def test_handler_uses_generated_person_data_for_each_invoice(mock_create, mock_get_project, monkeypatch):
    _fix_batch_size(monkeypatch, 8)
    mock_create.side_effect = [_fake_invoice(str(i)) for i in range(8)]

    invoice_issuer.handler({}, None)

    for call in mock_create.call_args_list:
        invoices, kwargs = call.args, call.kwargs
        invoice = invoices[0][0]
        assert kwargs["user"] == "fake-project"
        assert invoice_issuer.MIN_AMOUNT_CENTS <= invoice.amount <= invoice_issuer.MAX_AMOUNT_CENTS
        assert len(invoice.tax_id) == 11


def test_generate_unique_person_retries_on_tax_id_collision():
    used = {"11111111111"}
    with patch("src.invoice_issuer.handler.generate_person") as mock_generate:
        mock_generate.side_effect = [
            {"name": "Foo", "tax_id": "11111111111", "amount": 100},
            {"name": "Bar", "tax_id": "22222222222", "amount": 200},
        ]
        person = invoice_issuer._generate_unique_person(used)

    assert person["tax_id"] == "22222222222"
    assert mock_generate.call_count == 2
