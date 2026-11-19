#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
test -f build/lambda.zip || { echo 'Build the Lambda ZIP first.' >&2; exit 1; }
# Native Python extensions need executable mappings in the extraction directory.
docker run --rm --network none --read-only --user 10001:10001 \
  --cap-drop ALL --security-opt no-new-privileges \
  --tmpfs /tmp:rw,exec,nosuid,size=512m --env PYTHONDONTWRITEBYTECODE=1 \
  --mount "type=bind,src=$PWD/build,dst=/artifact,readonly" \
  --mount "type=bind,src=$PWD/scripts,dst=/checks,readonly" \
  python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df \
  python /checks/verify_lambda_package.py /artifact/lambda.zip
