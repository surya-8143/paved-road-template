#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
image="${1:-paved-road-service:local}"
container_id=$(docker run --detach --read-only --cap-drop ALL \
  --security-opt no-new-privileges --publish 127.0.0.1::8080 "$image")
cleanup() { local status=$?; if [ "$status" -ne 0 ]; then docker logs "$container_id" >&2 || true; fi; docker rm --force "$container_id" >/dev/null || true; }
trap cleanup EXIT
if [ "$(docker exec "$container_id" id -u)" != "10001" ]; then
  echo 'Container is not running as the expected non-root UID' >&2
  exit 1
fi
test "$(docker inspect --format '{{.HostConfig.ReadonlyRootfs}}' "$container_id")" = true
address=$(docker port "$container_id" 8080/tcp)
python3 - "$address" <<'PY'
import http.client
import json
import sys
import time
import urllib.error
import urllib.request

base = 'http://' + sys.argv[1].strip()
for attempt in range(40):
    try:
        with urllib.request.urlopen(base + '/healthz', timeout=2) as response:
            assert json.load(response)['status'] == 'ok'
        break
    except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.RemoteDisconnected):
        time.sleep(0.25)
else:
    raise SystemExit('Container failed to become ready')
with urllib.request.urlopen(base + '/hello/container', timeout=2) as response:
    assert json.load(response) == {'message': 'Hello, container!'}
for expected in (1, 2):
    request = urllib.request.Request(base + '/hits', method='POST')
    with urllib.request.urlopen(request, timeout=2) as response:
        assert json.load(response) == {'hits': expected}
print('Container HTTP smoke test: PASS (UID 10001, read-only rootfs, capabilities dropped)')
PY
