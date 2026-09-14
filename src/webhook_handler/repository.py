import os
import time
from typing import Optional

import boto3
from botocore.exceptions import ClientError

TABLE_NAME_ENV_VAR = "PROCESSED_EVENTS_TABLE"
DEFAULT_TABLE_NAME = "processed-events"
PROCESSED_EVENT_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days, matches the table's TTL attribute

STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"


class ProcessedEventRepository:
    """Tracks which webhook events have already been settled.

    Backed by a DynamoDB table keyed by event_id, chosen specifically because
    single-item writes there give us the ACID guarantees this idempotency
    check depends on:
      - Atomicity: try_claim's put_item either fully succeeds or fully fails,
        never leaves a half-written record.
      - Consistency: the conditional expression enforces the invariant "an
        event already completed can never be claimed again", regardless of
        how many callers race for it.
      - Isolation: DynamoDB serializes concurrent writes to the same item, so
        two overlapping webhook redeliveries for the same event can't both
        win try_claim.
      - Durability: once acknowledged, a record survives past this Lambda's
        ephemeral execution environment.
    """

    def __init__(self, table_name: Optional[str] = None):
        self._table_name = table_name or os.environ.get(TABLE_NAME_ENV_VAR, DEFAULT_TABLE_NAME)

    def try_claim(self, event_id: str) -> bool:
        """Marks an event as being processed. Returns False if already completed."""
        try:
            self._table().put_item(
                Item={
                    "event_id": event_id,
                    "status": STATUS_PROCESSING,
                    "ttl": int(time.time()) + PROCESSED_EVENT_TTL_SECONDS,
                },
                ConditionExpression="attribute_not_exists(event_id) OR #status <> :completed",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":completed": STATUS_COMPLETED},
            )
            return True
        except ClientError as error:
            if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise

    def mark_completed(self, event_id: str, transfer_id: str) -> None:
        self._update(event_id, status=STATUS_COMPLETED, transfer_id=transfer_id)

    def mark_failed(self, event_id: str) -> None:
        self._update(event_id, status=STATUS_FAILED, transfer_id=None)

    def _update(self, event_id: str, status: str, transfer_id) -> None:
        self._table().update_item(
            Key={"event_id": event_id},
            UpdateExpression="SET #status = :status, transfer_id = :transfer_id",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":status": status, ":transfer_id": transfer_id},
        )

    def _table(self):
        return boto3.resource("dynamodb").Table(self._table_name)
