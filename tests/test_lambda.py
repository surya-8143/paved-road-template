import asyncio
import json
from types import SimpleNamespace

import pytest
from mangum import Mangum

from app.main import create_app, handler
from app.storage import MemoryStore


@pytest.fixture(autouse=True)
def lambda_event_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield
    loop.close()
    asyncio.set_event_loop(None)


def function_url_event(method, path):
    return {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": path,
        "rawQueryString": "",
        "headers": {"host": "example.lambda-url.us-east-1.on.aws", "x-forwarded-proto": "https"},
        "requestContext": {
            "accountId": "anonymous",
            "apiId": "example",
            "domainName": "example.lambda-url.us-east-1.on.aws",
            "domainPrefix": "example",
            "requestId": "test-request",
            "routeKey": "$default",
            "stage": "$default",
            "time": "19/Nov/2026:00:00:00 +0000",
            "timeEpoch": 1795046400000,
            "http": {
                "method": method,
                "path": path,
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": "pytest",
            },
        },
        "body": "",
        "isBase64Encoded": False,
    }


@pytest.mark.parametrize(
    "method,path,status,expected",
    [
        ("GET", "/hello/lambda", 200, {"message": "Hello, lambda!"}),
        ("POST", "/hits", 200, {"hits": 1}),
        ("GET", "/missing", 404, {"detail": "Not Found"}),
    ],
)
def test_function_url_events(method, path, status, expected):
    adapter = Mangum(create_app(MemoryStore()), lifespan="off")
    result = adapter(function_url_event(method, path), SimpleNamespace(aws_request_id="test"))
    assert result["statusCode"] == status
    assert json.loads(result["body"]) == expected
    assert result["headers"]["content-type"] == "application/json"
    assert result["isBase64Encoded"] is False


def test_exported_lambda_handler_health():
    result = handler(function_url_event("GET", "/healthz"), SimpleNamespace(aws_request_id="test"))
    assert result["statusCode"] == 200
    assert json.loads(result["body"])["status"] == "ok"
