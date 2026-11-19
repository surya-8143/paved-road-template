from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.storage import DynamoStore, MemoryStore, StorageUnavailable, store_from_environment


def test_health_and_greeting_do_not_touch_storage():
    store = Mock()
    with TestClient(create_app(store)) as client:
        health = client.get("/healthz")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"
        assert health.json()["uptime_s"] >= 0
        assert client.get("/hello/world").json() == {"message": "Hello, world!"}
    store.hit.assert_not_called()


def test_hits_increment_and_instances_are_isolated():
    with TestClient(create_app(MemoryStore())) as first:
        assert first.post("/hits").json() == {"hits": 1}
        assert first.post("/hits").json() == {"hits": 2}
    with TestClient(create_app(MemoryStore())) as second:
        assert second.post("/hits").json() == {"hits": 1}


def test_memory_counter_is_atomic_under_concurrent_calls():
    store = MemoryStore()
    with ThreadPoolExecutor(max_workers=16) as pool:
        counts = list(pool.map(lambda _: store.hit(), range(500)))
    assert sorted(counts) == list(range(1, 501))


def test_counter_uses_post_only():
    with TestClient(create_app(MemoryStore())) as client:
        assert client.get("/hits").status_code == 405
        assert client.get("/missing").status_code == 404


def test_backend_failure_returns_generic_503():
    store = Mock()
    store.hit.side_effect = StorageUnavailable("internal account information")
    with TestClient(create_app(store)) as client:
        response = client.post("/hits")
    assert response.status_code == 503
    assert response.json() == {"detail": "Counter storage is unavailable"}
    assert "internal" not in response.text


def test_environment_defaults_to_memory(monkeypatch):
    monkeypatch.delenv("TABLE_NAME", raising=False)
    assert isinstance(store_from_environment(), MemoryStore)
    with TestClient(create_app()) as client:
        assert client.post("/hits").json() == {"hits": 1}


def test_dynamo_configuration_does_not_contact_aws_for_health(monkeypatch):
    monkeypatch.setenv("TABLE_NAME", "svc-demo-prod")
    create_client = Mock(side_effect=AssertionError("Unexpected AWS client creation"))
    monkeypatch.setattr("app.storage.boto3.client", create_client)
    assert isinstance(store_from_environment(), DynamoStore)
    with TestClient(create_app()) as client:
        assert client.get("/healthz").status_code == 200
    create_client.assert_not_called()


def test_blank_table_name_is_rejected():
    with pytest.raises(ValueError, match="must not be blank"):
        DynamoStore("   ")
