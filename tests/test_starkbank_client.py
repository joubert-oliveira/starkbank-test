import json

import boto3
import starkbank
from moto import mock_aws

from src.common import starkbank_client

SECRET_NAME = "starkbank/credentials"
PRIVATE_KEY, _ = starkbank.key.create()


def _create_secret(secretsmanager, **overrides):
    payload = {
        "project_id": "123456",
        "private_key": PRIVATE_KEY,
        "environment": "sandbox",
        **overrides,
    }
    secretsmanager.create_secret(Name=SECRET_NAME, SecretString=json.dumps(payload))


@mock_aws
def test_get_project_builds_starkbank_project_from_secret():
    starkbank_client.get_project.cache_clear()
    secretsmanager = boto3.client("secretsmanager", region_name="us-east-1")
    _create_secret(secretsmanager)

    project = starkbank_client.get_project()

    assert isinstance(project, starkbank.Project)
    assert project.id == "123456"
    assert project.environment == "sandbox"


@mock_aws
def test_get_project_is_cached_across_calls():
    starkbank_client.get_project.cache_clear()
    secretsmanager = boto3.client("secretsmanager", region_name="us-east-1")
    _create_secret(secretsmanager)

    first = starkbank_client.get_project()
    secretsmanager.delete_secret(SecretId=SECRET_NAME, ForceDeleteWithoutRecovery=True)
    second = starkbank_client.get_project()

    assert first is second


@mock_aws
def test_get_project_defaults_environment_when_missing():
    starkbank_client.get_project.cache_clear()
    secretsmanager = boto3.client("secretsmanager", region_name="us-east-1")
    payload = {"project_id": "123456", "private_key": PRIVATE_KEY}
    secretsmanager.create_secret(Name=SECRET_NAME, SecretString=json.dumps(payload))

    project = starkbank_client.get_project()

    assert project.environment == "sandbox"
