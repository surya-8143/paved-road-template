# Local service verification

Date: 2026-11-19 (Asia/Kolkata).

## Scope

FastAPI application, memory/DynamoDB storage code, Function URL-shaped Lambda events, container execution and ZIP packaging. No live AWS requests or deployment were performed.

## Observed results

- Ruff lint: passed.
- Ruff formatting: 10 Python files passed.
- Behavioral tests: 20 passed in a fresh Python 3.12.3 virtual environment installed only from requirements-dev.txt with hash verification.
- Application coverage: 66 statements, 6 branches, no missed statements or branches (100%). This describes the small application module, not production reliability or complete platform coverage.
- One upstream warning: Mangum 0.22.0 uses asyncio.get_event_loop during adapter initialization when no event loop is set. Python 3.12 execution succeeds. The warning is not suppressed.
- Container HTTP checks: passed for health, greeting and two increment requests.
- Container restrictions used: UID/GID 10001, read-only root filesystem, all capabilities dropped, no-new-privileges, loopback-only published port. Temporary test container removed after the test.
- Lambda ZIP: imported and invoked in a clean Python 3.12 container with no network, non-root user and read-only root filesystem. Temporary extraction storage allowed executable mappings for native Python extensions.
- Lambda ZIP reproducibility: two builds from separate virtual environments, using pip 26.3 and pip 24.0, produced the same SHA-256:

```text
7fb797e3eb70d7b40a4bde8e40ef5687ce4f99194f63eab72cca65b5240684e7
```

The hash applies to the current source and dependency lock. Code or dependency changes will change it. This is not a claim that all toolchain versions produce identical compressed bytes.

## Covered behavior

Health and greeting avoid storage access; memory counters are isolated and thread-safe; GET /hits is rejected; storage failures return a generic 503; DynamoDB uses atomic UpdateItem with exact expected parameters; permission/throttling/connection errors are handled; malformed responses are rejected; the SDK client is lazy and reused; non-idempotent writes are not automatically retried; Mangum handles Function URL GET/POST and unknown paths.

## Reproduce

Activate a Python 3.12 virtual environment installed from the development lock, then:

```bash
make lint test
make smoke
make package
bash scripts/smoke_lambda.sh
```

For the reproducibility comparison, retain the first ZIP hash, rebuild with another Python 3.12 environment using the same inputs, and compare SHA-256 hashes.

## Not yet verified

Live DynamoDB access, IAM permissions, AWS-managed Lambda execution, vulnerability scan results, image signatures, GitHub CI, deployment gates, infrastructure policies, Kubernetes admission and complete project teardown. The new AWS project's OIDC restriction still blocks the intended cloud authentication setup.
