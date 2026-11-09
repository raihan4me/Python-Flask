#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export PATH="$PWD/.venv/bin:$PATH"
set -a
. ./prod.env
set +a
if [ "$#" -eq 0 ]; then
  set -- gunicorn -c gunicorn.conf.py wsgi:app
fi
exec "$@"
