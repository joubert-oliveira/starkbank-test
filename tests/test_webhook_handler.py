from types import SimpleNamespace
from unittest.mock import patch

import boto3
import starkbank
from moto import mock_aws

from src.webhook_handler import handler as webhook_handler

TABLE_NAME = "processed-events"


def _create_table():
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    dynamodb.create_table(
        TableName=TABLE_NAME,
        KeySchema=[{"AttributeName": "event_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "event_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    return dynamodb.Table(TABLE_NAME)


def _api_gateway_event(body="raw-content", signature="sig123", source_ip="35.199.76.124"):
    return {
        "body": body,
        "headers": {"Digital-Signature": signature},
        "requestContext": {"http": {"sourceIp": source_ip}},
    }


def _fake_credited_event(event_id="evt-1", amount=1000, fee=50):
    invoice = SimpleNamespace(amount=amount, fee=fee)
    log = SimpleNamespace(type="credited", invoice=invoice)
    return SimpleNamespace(id=event_id, subscription="invoice", log=log)


def _fake_transfer(transfer_id="transfer-1"):
    return [SimpleNamespace(id=transfer_id)]


def test_rejects_request_from_unexpected_source_ip():
    event = _api_gateway_event(source_ip="1.2.3.4")

    result = webhook_handler.handler(event, None)

    assert result["statusCode"] == 403


@patch("src.webhook_handler.handler.get_project", return_value="fake-project")
@patch("starkbank.event.parse")
def test_invalid_signature_returns_400(mock_parse, mock_get_project):
    mock_parse.side_effect = starkbank.error.InvalidSignatureError("bad signature")

    result = webhook_handler.handler(_api_gateway_event(), None)

    assert result["statusCode"] == 400


@mock_aws
@patch("src.webhook_handler.handler.get_project", return_value="fake-project")
@patch("starkbank.event.parse")
def test_ignores_non_invoice_subscription(mock_parse, mock_get_project):
    _create_table()
    mock_parse.return_value = SimpleNamespace(id="evt-1", subscription="transfer", log=SimpleNamespace(type="success"))

    result = webhook_handler.handler(_api_gateway_event(), None)

    assert result["statusCode"] == 200
    assert "ignored" in result["body"]


@mock_aws
@patch("src.webhook_handler.handler.get_project", return_value="fake-project")
@patch("starkbank.event.parse")
def test_ignores_invoice_event_not_credited(mock_parse, mock_get_project):
    _create_table()
    mock_parse.return_value = SimpleNamespace(
        id="evt-1", subscription="invoice", log=SimpleNamespace(type="registered")
    )

    result = webhook_handler.handler(_api_gateway_event(), None)

    assert result["statusCode"] == 200
    assert "ignored" in result["body"]


@mock_aws
@patch("src.webhook_handler.handler.get_project", return_value="fake-project")
@patch("starkbank.transfer.create")
@patch("starkbank.event.parse")
def test_creates_transfer_for_credited_invoice(mock_parse, mock_transfer_create, mock_get_project):
    table = _create_table()
    mock_parse.return_value = _fake_credited_event(event_id="evt-1", amount=1000, fee=50)
    mock_transfer_create.return_value = _fake_transfer("transfer-1")

    result = webhook_handler.handler(_api_gateway_event(), None)

    assert result["statusCode"] == 200
    assert "transfer-1" in result["body"]

    transfer_arg = mock_transfer_create.call_args.args[0][0]
    assert transfer_arg.amount == 950  # amount - fee
    assert transfer_arg.external_id == "evt-1"
    assert transfer_arg.bank_code == "20018183"
    assert transfer_arg.account_number == "6341320293482496"

    item = table.get_item(Key={"event_id": "evt-1"})["Item"]
    assert item["status"] == "completed"
    assert item["transfer_id"] == "transfer-1"


@mock_aws
@patch("src.webhook_handler.handler.get_project", return_value="fake-project")
@patch("starkbank.transfer.create")
@patch("starkbank.event.parse")
def test_duplicate_completed_event_does_not_create_second_transfer(mock_parse, mock_transfer_create, mock_get_project):
    table = _create_table()
    table.put_item(Item={"event_id": "evt-1", "status": "completed", "transfer_id": "transfer-1"})
    mock_parse.return_value = _fake_credited_event(event_id="evt-1")

    result = webhook_handler.handler(_api_gateway_event(), None)

    assert result["statusCode"] == 200
    assert "already processed" in result["body"]
    mock_transfer_create.assert_not_called()


@mock_aws
@patch("src.webhook_handler.handler.get_project", return_value="fake-project")
@patch("starkbank.transfer.create")
@patch("starkbank.event.parse")
def test_retries_transfer_after_previous_failure(mock_parse, mock_transfer_create, mock_get_project):
    table = _create_table()
    table.put_item(Item={"event_id": "evt-1", "status": "failed", "transfer_id": None})
    mock_parse.return_value = _fake_credited_event(event_id="evt-1", amount=1000, fee=50)
    mock_transfer_create.return_value = _fake_transfer("transfer-2")

    result = webhook_handler.handler(_api_gateway_event(), None)

    assert result["statusCode"] == 200
    item = table.get_item(Key={"event_id": "evt-1"})["Item"]
    assert item["status"] == "completed"
    assert item["transfer_id"] == "transfer-2"


@mock_aws
@patch("src.webhook_handler.handler.get_project", return_value="fake-project")
@patch("starkbank.transfer.create")
@patch("starkbank.event.parse")
def test_marks_event_failed_when_transfer_creation_raises(mock_parse, mock_transfer_create, mock_get_project):
    table = _create_table()
    mock_parse.return_value = _fake_credited_event(event_id="evt-1")
    mock_transfer_create.side_effect = Exception("stark bank api error")

    result = webhook_handler.handler(_api_gateway_event(), None)

    assert result["statusCode"] == 500
    item = table.get_item(Key={"event_id": "evt-1"})["Item"]
    assert item["status"] == "failed"


def test_get_header_is_case_insensitive():
    event = {"headers": {"Digital-Signature": "abc"}}
    assert webhook_handler._get_header(event, "digital-signature") == "abc"


def test_get_body_decodes_base64_when_flagged():
    import base64

    raw = "hello world"
    event = {"body": base64.b64encode(raw.encode()).decode(), "isBase64Encoded": True}
    assert webhook_handler._get_body(event) == raw
