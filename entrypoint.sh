#!/bin/sh
set -eu

python - <<'PY'
import os
import socket
import sys
import time
from urllib.parse import urlparse

database_url = os.environ.get("DATABASE_URL", "")
parsed = urlparse(database_url)
if not parsed.hostname or not parsed.port:
    print("DATABASE_URL must include a database host and port", file=sys.stderr)
    sys.exit(1)

for attempt in range(30):
    try:
        with socket.create_connection((parsed.hostname, parsed.port), timeout=2):
            break
    except OSError:
        if attempt == 29:
            print("Database was not reachable after 60 seconds", file=sys.stderr)
            sys.exit(1)
        time.sleep(2)
PY

alembic upgrade head
exec uvicorn app.main:app \
    --host "${HOST:-0.0.0.0}" \
    --port "${PORT:-8000}" \
    --proxy-headers
