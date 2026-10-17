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

# P0.2: the wheel must carry the prebuilt SPA, so the page has to come from this process.
PAGE="$(curl -fsS "http://127.0.0.1:$PORT/" 2>/dev/null || true)"
if [[ "$PAGE" != *'id="root"'* ]]; then
	printf '%s\n' "smoke FAILED: / did not return the SPA shell (missing src/paperpilot/web?)" >&2
	tail -20 "$LOG" >&2
	exit 1
fi

DEEP_LINK="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/projects" 2>/dev/null || true)"
UNKNOWN_API="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/api/definitely-missing" 2>/dev/null || true)"
if [[ "$DEEP_LINK" != "200" || "$UNKNOWN_API" != "404" ]]; then
	printf '%s\n' "smoke FAILED: SPA deep link (got $DEEP_LINK, want 200) or unknown API (got $UNKNOWN_API, want 404)" >&2
	tail -20 "$LOG" >&2
	exit 1
fi

echo "smoke OK: / (SPA shell) + /projects (deep link 200) + /api/health + unknown API 404"

# P0.3: runtime state must be <data_dir>/db.sqlite, never the repo or site-packages.
if [[ ! -f "$DATA_DIR/db.sqlite" ]]; then
	printf '%s\n' "smoke FAILED: $DATA_DIR/db.sqlite was not created (runtime state is not in the data root)" >&2
	find "$DATA_DIR" -maxdepth 2 >&2 || true
	exit 1
fi
echo "smoke OK: runtime database at $DATA_DIR/db.sqlite"
