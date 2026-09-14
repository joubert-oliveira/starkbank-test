import json
import os
from functools import lru_cache

import boto3
import starkbank

SECRET_NAME_ENV_VAR = "STARKBANK_SECRET_NAME"
DEFAULT_SECRET_NAME = "starkbank/credentials"
DEFAULT_ENVIRONMENT = "sandbox"


@lru_cache(maxsize=1)
def get_project() -> starkbank.Project:
    """Builds the starkbank.Project used to authenticate SDK calls.

    Cached per Lambda execution environment so warm invocations reuse the
    same Project instead of hitting Secrets Manager again.
    """
    secret = _load_secret()
    return starkbank.Project(
        id=secret["project_id"],
        environment=secret.get("environment", DEFAULT_ENVIRONMENT),
        private_key=secret["private_key"],
    )


def _load_secret() -> dict:
    secret_name = os.environ.get(SECRET_NAME_ENV_VAR, DEFAULT_SECRET_NAME)
    client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response["SecretString"])
