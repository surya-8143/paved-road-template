# Paved Road Service Template

A small FastAPI service that runs as a non-root container or as a Python 3.12 AWS Lambda ZIP through Mangum. It is the application foundation for the Paved Road platform.

**Current status:** tested locally. CI, vulnerability scanning, signing, infrastructure deployment and Kubernetes integration are not implemented yet. No AWS deployment is claimed.

## Run locally (Ubuntu/WSL, Python 3.12)

Keep source in D:\CLOUD. Use native Linux storage for the virtual environment because Windows-mounted filesystem permission handling can disrupt Python tooling.

```bash
cd /mnt/d/CLOUD/paved-road-template
python3 -m venv ~/.cache/paved-road/service-dev
source ~/.cache/paved-road/service-dev/bin/activate
python -m pip install --require-hashes --only-binary=:all: -r requirements-dev.txt
make lint test
python -m uvicorn app.main:app --host 127.0.0.1 --port 8080
```

Open http://127.0.0.1:8080/docs for interactive API documentation. Stop the server with Ctrl+C.

| Endpoint | Behavior |
| --- | --- |
| GET /healthz | Process liveness and uptime; no database request |
| GET /hello/{name} | Greeting |
| POST /hits | Atomically increment and return the counter |

With TABLE_NAME unset, the counter is held in process memory. It resets when the process restarts and is not shared between replicas or workers. This is a demonstration counter, not durable analytics.

## Test the container

```bash
make smoke
```

This builds the image, starts a temporary container as UID 10001 with a read-only root filesystem, drops Linux capabilities, exercises the API over a randomly assigned loopback port, and removes that container. It does not restart other containers.

For an interactive local demo:

```bash
docker run --rm --read-only --cap-drop ALL --security-opt no-new-privileges \
  -p 127.0.0.1:8080:8080 paved-road-service:local
```

The official Python base image is pinned by digest. Runtime dependencies and transitive dependencies are pinned with hashes. Only application files and the runtime lock enter the Docker build context.

## Lambda packaging (no AWS account required)

```bash
make package
bash scripts/smoke_lambda.sh
```

The handler is `app.main.handler`, runtime Python 3.12, architecture x86_64. Packaging installs hash-verified binary wheels targeting manylinux2014_x86_64 and includes boto3 explicitly. ZIP member ordering, timestamps and permissions are normalized. Unused generated CLI scripts are excluded because their shebangs contain the builder's virtualenv path.

The smoke test imports the extracted ZIP in a clean Python container with networking disabled and invokes Function URL-shaped events. This proves local packaging/import behavior; it does not prove AWS IAM permissions, live DynamoDB access or compatibility with the managed Lambda runtime. Those require the later cloud deployment test.

## DynamoDB mode

Set TABLE_NAME to an existing table whose partition key is `pk` (String). Credentials and region come from the standard AWS SDK credential chain; credentials are never accepted in source files. On Lambda, the execution role supplies credentials.

AWS client creation is lazy: module import, health and greeting endpoints do not fetch credentials. The backend uses a thread-safe low-level client and an atomic UpdateItem ADD. SDK retries are disabled for this non-idempotent write. A timeout can still leave the outcome uncertain, and a caller retry can increment twice. Do not use this counter for billing or exactly-once accounting.

Storage failures return a generic HTTP 503. /healthz is liveness only; it does not assert database readiness. Tests use explicit dummy credentials and Botocore Stubber, never a live AWS account.

## Updating dependency locks

Use Python 3.12 in a separate tooling environment with `pip-tools==7.7.0`, then run:

```bash
python scripts/lock_dependencies.py
```

The helper resolves in a temporary native Linux directory and copies contents back to the repository to avoid pip-tools atomic-write errors on Windows-mounted storage. Review changes and rerun lint, tests, container smoke and package verification. To deliberately upgrade a dependency, update its constraint in the corresponding .in file before regenerating the locks.

## Verification and limitations

See [local verification evidence](docs/VERIFICATION.md). The test cache plugin is disabled to avoid DrvFS permission errors. Mangum 0.22.0 emits an upstream Python 3.12 event-loop deprecation warning when its adapter is initialized during test collection; the handler tests pass. The runtime remains pinned to Python 3.12 until newer runtime compatibility is verified.

GitHub publication, supply-chain gates and AWS deployment are separate acceptance steps. The complete project checklist lives in the sibling `paved-road-platform` repository.
