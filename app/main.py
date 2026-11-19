"""One HTTP service for local containers and AWS Lambda Function URLs."""

import logging
import time

from fastapi import FastAPI, HTTPException
from mangum import Mangum

from app.storage import HitStore, StorageUnavailable, store_from_environment

log = logging.getLogger(__name__)


def create_app(store: HitStore | None = None) -> FastAPI:
    service = FastAPI(title="paved-road-service", version="0.1.0")
    counter = store if store is not None else store_from_environment()
    started = time.monotonic()

    @service.get("/healthz")
    def healthz() -> dict[str, str | float]:
        # Liveness only: intentionally does not read or write DynamoDB.
        return {"status": "ok", "uptime_s": round(time.monotonic() - started, 1)}

    @service.get("/hello/{name}")
    def hello(name: str) -> dict[str, str]:
        return {"message": f"Hello, {name}!"}

    @service.post("/hits")
    def hits() -> dict[str, int]:
        try:
            return {"hits": counter.hit()}
        except StorageUnavailable as error:
            log.warning("Counter storage is unavailable")
            raise HTTPException(status_code=503, detail="Counter storage is unavailable") from error

    return service


app = create_app()
handler = Mangum(app, lifespan="off")
