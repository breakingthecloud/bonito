#!/usr/bin/env bash
# Push a sample collector snapshot to bonito-store (BON-002).
# Usage: BONITO_STORE_URL=http://localhost:8000 ./store-push.sh
set -euo pipefail

URL="${BONITO_STORE_URL:-http://localhost:8000}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

curl -sS -X POST "$URL/events" \
  -H 'Content-Type: application/json' \
  --data-binary @"$DIR/events.sample.json"
echo
curl -sS "$URL/baselines"
echo