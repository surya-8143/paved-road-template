"""Import and invoke a generated ZIP in an otherwise clean Python container."""

import asyncio
import importlib
import json
import sys
import tempfile
import zipfile
from pathlib import Path
from types import SimpleNamespace

with tempfile.TemporaryDirectory(prefix="paved-road-zip-check-") as temporary:
    with zipfile.ZipFile(sys.argv[1]) as archive:
        for name in archive.namelist():
            path = Path(name)
            if path.is_absolute() or ".." in path.parts:
                raise SystemExit("Unsafe archive path")
        archive.extractall(temporary)
    sys.path.insert(0, temporary)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        service = importlib.import_module("app.main")
        event = {
            "version": "2.0",
            "routeKey": "$default",
            "rawPath": "/healthz",
            "rawQueryString": "",
            "headers": {"host": "example.lambda-url.us-east-1.on.aws"},
            "requestContext": {
                "http": {
                    "method": "GET",
                    "path": "/healthz",
                    "sourceIp": "127.0.0.1",
                    "protocol": "HTTP/1.1",
                }
            },
            "body": "",
            "isBase64Encoded": False,
        }
        result = service.handler(event, SimpleNamespace(aws_request_id="zip-smoke"))
        assert result["statusCode"] == 200
        assert json.loads(result["body"])["status"] == "ok"
        event["rawPath"] = "/hits"
        event["requestContext"]["http"].update(method="POST", path="/hits")
        result = service.handler(event, SimpleNamespace(aws_request_id="zip-smoke"))
        assert result["statusCode"] == 200
        assert json.loads(result["body"]) == {"hits": 1}
        print("Packaged Lambda handler: PASS (isolated Python, network disabled)")
    finally:
        loop.close()
        asyncio.set_event_loop(None)
