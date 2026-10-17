#!/usr/bin/env bash
# M0 acceptance helper: start the installed `paperpilot serve` on a throwaway data
# root and require /api/health to answer. Used by `make smoke` and CI (P0.9).
#
# Requires the `paperpilot` console script on PATH.
set -u -o pipefail

PORT="${SMOKE_PORT:-8123}"
DATA_DIR="${SMOKE_DATA_DIR:-$(mktemp -d)}"
LOG="$(mktemp)"
PID=""

cleanup() {
	if [[ -n "$PID" ]]; then
		kill "$PID" 2>/dev/null || true
		wait "$PID" 2>/dev/null || true
	fi
}
trap cleanup EXIT

if ! command -v paperpilot >/dev/null 2>&1; then
	printf '%s\n' "smoke FAILED: paperpilot is not on PATH" >&2
	exit 1
fi

PAPERPOILOT_DATA_DIR="$DATA_DIR" paperpilot serve --port "$PORT" >"$LOG" 2>&1 &
PID=$!

HEALTH=""
for _ in $(seq 1 40); do
	if HEALTH="$(curl -fsS "http://127.0.0.1:$PORT/api/health" 2>/dev/null)"; then
		break
	fi
	HEALTH=""
	sleep 0.5
done

if [[ -z "$HEALTH" ]]; then
	printf '%s\n' "smoke FAILED: /api/health did not answer on port $PORT" >&2
	tail -20 "$LOG" >&2
	exit 1
fi

printf '/api/health -> %s\n' "$HEALTH"
if [[ "$HEALTH" != *'"ok":true'* ]]; then
	printf '%s\n' "smoke FAILED: /api/health did not report ok" >&2
	tail -20 "$LOG" >&2
	exit 1
fi

echo "smoke OK: paperpilot serve -> /api/health (data_root=$DATA_DIR)"
