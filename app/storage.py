"""Counter backends. AWS access is lazy and uses the SDK credential chain."""

import os
from threading import Lock
from typing import Any, Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError


class StorageUnavailable(Exception):
    """The counter could not be updated safely."""


class HitStore(Protocol):
    def hit(self) -> int: ...


class MemoryStore:
    """Process-local demo storage; resets on restart and is not shared by workers."""

    def __init__(self) -> None:
        self._count = 0
        self._lock = Lock()

    def hit(self) -> int:
        with self._lock:
            self._count += 1
            return self._count


class DynamoStore:
    def __init__(self, table_name: str, client: Any = None) -> None:
        if not table_name.strip():
            raise ValueError("TABLE_NAME must not be blank")
        self._table_name = table_name
        self._client = client
        self._client_lock = Lock()

    def _get_client(self) -> Any:
        with self._client_lock:
            if self._client is None:
                self._client = boto3.client(
                    "dynamodb",
                    config=Config(
                        connect_timeout=2,
                        read_timeout=3,
                        # ADD is not idempotent: do not automatically retry writes.
                        retries={"total_max_attempts": 1, "mode": "standard"},
                    ),
                )
            return self._client

    def hit(self) -> int:
        try:
            response = self._get_client().update_item(
                TableName=self._table_name,
                Key={"pk": {"S": "hits"}},
                UpdateExpression="ADD #h :one",
                ExpressionAttributeNames={"#h": "hit_count"},
                ExpressionAttributeValues={":one": {"N": "1"}},
                ReturnValues="UPDATED_NEW",
            )
            count = int(response["Attributes"]["hit_count"]["N"])
            if count < 1:
                raise ValueError("Invalid counter value")
            return count
        except (BotoCoreError, ClientError, KeyError, TypeError, ValueError) as error:
            raise StorageUnavailable("Counter storage is unavailable") from error


def store_from_environment() -> HitStore:
    table_name = os.environ.get("TABLE_NAME")
    return DynamoStore(table_name) if table_name else MemoryStore()
