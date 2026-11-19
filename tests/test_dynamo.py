from unittest.mock import Mock

import boto3
import pytest
from botocore.exceptions import EndpointConnectionError
from botocore.stub import Stubber
from fastapi.testclient import TestClient

from app.main import create_app
from app.storage import DynamoStore, StorageUnavailable


@pytest.fixture
def client():
    # Explicit dummy credentials avoid the real credential chain and metadata lookup.
    sdk = boto3.client(
        "dynamodb",
        region_name="us-east-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
        aws_session_token="testing",
    )
    yield sdk
    sdk.close()


def expected_update():
    return {
        "TableName": "svc-demo-prod",
        "Key": {"pk": {"S": "hits"}},
        "UpdateExpression": "ADD #h :one",
        "ExpressionAttributeNames": {"#h": "hit_count"},
        "ExpressionAttributeValues": {":one": {"N": "1"}},
        "ReturnValues": "UPDATED_NEW",
    }


def test_dynamo_atomic_update_and_http_response(client):
    with Stubber(client) as stub:
        stub.add_response(
            "update_item",
            {"Attributes": {"hit_count": {"N": "42"}}},
            expected_update(),
        )
        with TestClient(create_app(DynamoStore("svc-demo-prod", client))) as http:
            assert http.post("/hits").json() == {"hits": 42}
        stub.assert_no_pending_responses()


@pytest.mark.parametrize(
    "code", ["AccessDeniedException", "ProvisionedThroughputExceededException"]
)
def test_dynamo_errors_become_503(client, code):
    with Stubber(client) as stub:
        stub.add_client_error(
            "update_item", service_error_code=code, expected_params=expected_update()
        )
        with TestClient(create_app(DynamoStore("svc-demo-prod", client))) as http:
            response = http.post("/hits")
        assert response.status_code == 503
        assert response.json() == {"detail": "Counter storage is unavailable"}
        stub.assert_no_pending_responses()


@pytest.mark.parametrize(
    "response",
    [{}, {"Attributes": {"hit_count": {"N": "oops"}}}, {"Attributes": {"hit_count": {"N": "0"}}}],
)
def test_malformed_counter_response_is_not_reported_as_success(response):
    sdk = Mock()
    sdk.update_item.return_value = response
    with pytest.raises(StorageUnavailable):
        DynamoStore("svc-demo-prod", sdk).hit()


def test_connection_failure_is_wrapped():
    sdk = Mock()
    sdk.update_item.side_effect = EndpointConnectionError(endpoint_url="https://example.invalid")
    with pytest.raises(StorageUnavailable):
        DynamoStore("svc-demo-prod", sdk).hit()


def test_client_is_lazy_cached_and_does_not_retry_atomic_increment(monkeypatch):
    sdk = Mock()
    sdk.update_item.return_value = {"Attributes": {"hit_count": {"N": "1"}}}
    factory = Mock(return_value=sdk)
    monkeypatch.setattr("app.storage.boto3.client", factory)
    store = DynamoStore("svc-demo-prod")
    factory.assert_not_called()
    store.hit()
    store.hit()
    factory.assert_called_once()
    config = factory.call_args.kwargs["config"]
    assert config.retries["total_max_attempts"] == 1
    assert config.connect_timeout == 2
    assert config.read_timeout == 3
