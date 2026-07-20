#!/usr/bin/env bash
# One-command RevWatch demo: data → train/validate → API + dashboard
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH=.
export REVWATCH_DB="${REVWATCH_DB:-data/revwatch.duckdb}"

echo "=== RevWatch demo ==="

if [[ ! -f "$REVWATCH_DB" ]]; then
  echo "[1/4] Generating US universe + estimates…"
  python scripts/phase3_demo.py --quick --db "$REVWATCH_DB"
  python scripts/phase4_demo.py --quick --db "$REVWATCH_DB"
  python scripts/phase5_demo.py --quick --db "$REVWATCH_DB"
else
  echo "[1/4] Using existing $REVWATCH_DB"
fi

echo "[2/4] Ensuring dashboard dependencies…"
if [[ ! -d dashboard/node_modules ]]; then
  (cd dashboard && npm install)
fi

echo "[3/4] Starting API on :8000…"
uvicorn api.main:app --host 127.0.0.1 --port 8000 &
API_PID=$!
cleanup() {
  kill "$API_PID" "$DASH_PID" 2>/dev/null || true
}
trap cleanup EXIT

for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8000/health >/dev/null; then
    break
  fi
  sleep 0.5
done

echo "[4/4] Starting dashboard on :3000…"
(cd dashboard && npm run dev -- -H 127.0.0.1 -p 3000) &
DASH_PID=$!

echo ""
echo "RevWatch is up:"
echo "  API:       http://127.0.0.1:8000/docs"
echo "  Dashboard: http://127.0.0.1:3000"
echo "Press Ctrl+C to stop."
wait
