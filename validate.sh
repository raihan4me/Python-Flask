#!/usr/bin/env bash
# validate.sh - final checks for the Flask inventory lab
set -u
LAB="$HOME/flask-lab"
cd "$LAB" || { echo "FAIL  $LAB not found"; exit 1; }
PY="$LAB/.venv/bin/python"
BASE="http://localhost:8080"
PASS=0
FAIL=0

check() {
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then
    printf 'PASS  %s\n' "$desc"; PASS=$((PASS + 1))
  else
    printf 'FAIL  %s\n' "$desc"; FAIL=$((FAIL + 1))
  fi
}

t1_warmup_post() {
  "$PY" - <<'PY'
import sys
sys.path.insert(0, "warmup")
from hello import app
c = app.test_client()
assert c.post("/items", json={"name": "probe"}).status_code == 201
assert c.post("/items", json={}).status_code == 400
PY
}

t2_config() {
  "$PY" -c "from inventory import create_app; a = create_app('testing'); assert a.testing and a.config['SQLALCHEMY_DATABASE_URI'] == 'sqlite:///:memory:'"
}

t3_dev_db() {
  [ "$(sqlite3 instance/inventory.db 'SELECT count(*) FROM items;')" -ge 4 ]
}

t4_hooks() {
  "$PY" - <<'PY'
from inventory import create_app
c = create_app("testing").test_client()
assert c.get("/health/live", headers={"X-Request-ID": "chk-1"}).headers["X-Request-ID"] == "chk-1"
PY
}

t5_tests() {
  "$PY" -m pytest -q -p no:cacheprovider --cov=inventory --cov-fail-under=85 > /tmp/pytest-validate.log 2>&1 \
    && ! grep -qi 'skipped' /tmp/pytest-validate.log
}

t6_gunicorn() {
  test -x run-prod.sh && test -f wsgi.py \
    && APP_ENV=testing "$LAB/.venv/bin/gunicorn" --check-config -c gunicorn.conf.py wsgi:app
}

t7_image_user() {
  [ "$(docker image inspect -f '{{.Config.User}}' inventory-api:1.0.0)" = "app" ]
}

t8_api_healthy() {
  local cid
  cid=$(docker compose ps -q api | head -n1)
  [ -n "$cid" ] && [ "$(docker inspect -f '{{.State.Health.Status}}' "$cid")" = "healthy" ]
}

t8_proxy_ready() {
  [ "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/health/ready")" = "200" ]
}

t8_request_id() {
  curl -s -D - -o /dev/null "$BASE/health/live" | grep -qiE '^x-request-id: [0-9a-f]{32}'
}

t8_server_tokens() {
  curl -s -D - -o /dev/null "$BASE/health/live" | tr -d '\r' | grep -qx 'Server: nginx'
}

t8_json_404() {
  curl -s "$BASE/does-not-exist" | jq -e '.status == 404'
}

t8_patch_roundtrip() {
  local sku="VAL-$RANDOM$RANDOM" id
  id=$(curl -sf -X POST "$BASE/api/v1/items" -H 'Content-Type: application/json' \
       -d "{\"sku\":\"$sku\",\"name\":\"Validation probe\",\"quantity\":1}" | jq -r .id) || return 1
  [ -n "$id" ] && [ "$id" != "null" ] || return 1
  [ "$(curl -sf -X PATCH "$BASE/api/v1/items/$id" -H 'Content-Type: application/json' \
       -d '{"quantity":7}' | jq -r .quantity)" = "7" ] || return 1
  [ "$(curl -s -o /dev/null -w '%{http_code}' -X DELETE "$BASE/api/v1/items/$id")" = "204" ]
}

t8_nonroot() {
  [ "$(docker compose exec -T api id -u | tr -d '\r')" = "10001" ]
}

t8_volume() {
  docker volume inspect inventory_inventory-data
}

check "Task 1: warm-up POST /items returns 201/400"               t1_warmup_post
check "Task 2: factory builds testing config"                     t2_config
check "Task 3: development DB seeded (>= 4 items)"                t3_dev_db
check "Task 4: valid X-Request-ID is echoed"                      t4_hooks
check "Task 5: pytest passes, no skips, coverage >= 85%"          t5_tests
check "Task 6: gunicorn config and WSGI entry point load"         t6_gunicorn
check "Task 7: image inventory-api:1.0.0 runs as user 'app'"      t7_image_user
check "Task 8: api service is healthy"                            t8_api_healthy
check "Task 8: readiness 200 through nginx"                       t8_proxy_ready
check "Task 8: nginx-generated X-Request-ID returned"             t8_request_id
check "Task 8: nginx hides its version"                           t8_server_tokens
check "Task 8: unknown route returns JSON 404"                    t8_json_404
check "Task 8: create / PATCH / DELETE round trip via proxy"      t8_patch_roundtrip
check "Task 8: container process runs as UID 10001"               t8_nonroot
check "Task 8: named volume exists"                               t8_volume

echo "----------------------------------------"
echo "Passed: $PASS   Failed: $FAIL"
[ "$FAIL" -eq 0 ]
