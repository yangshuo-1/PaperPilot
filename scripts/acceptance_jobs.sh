#!/usr/bin/env bash
# M0 P0.4 acceptance: job lifecycle state lives in <data_dir>/db.sqlite (v3 tables
# jobs / job_checkpoints / job_events) instead of references/*_jobs/*.json, and a job
# left "running" by a restart is re-dispatched by `paperpilot serve`.
#
# Usage: scripts/acceptance_jobs.sh
#   Runs against a throwaway data root (mktemp -d); the frozen references/*_jobs
#   files are only ever read.  Exits non-zero on the first failed assertion.
set -euo pipefail

PY="${PY:-.venv/bin/python}"
PAPERPOILOT="${PAPERPOILOT:-.venv/bin/paperpilot}"
PORT="${PORT:-8129}"
ROOT="$(mktemp -d)"
PAPER_ID="2509.20354"
JOB_ID="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

SERVER_PID=""
cleanup() {
  [[ -n "$SERVER_PID" ]] && kill "$SERVER_PID" 2>/dev/null || true
  rm -rf "$ROOT"
}
trap cleanup EXIT

stop_server() {
  if [[ -n "$SERVER_PID" ]]; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
    SERVER_PID=""
  fi
}

start_server() {
  PAPERPOILOT_DATA_DIR="$ROOT" "$PAPERPOILOT" serve --port "$PORT" >"$ROOT/serve$1.log" 2>&1 &
  SERVER_PID=$!
  for _ in $(seq 1 60); do
    curl -fsS "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1 && return 0
    sleep 0.5
  done
  echo "FAIL: server did not become healthy" >&2
  tail -20 "$ROOT/serve$1.log" >&2
  return 1
}

echo "== throwaway data root: $ROOT"
mkdir -p "$ROOT/papers/$PAPER_ID/source"
printf '%%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%%%EOF\n' \
  >"$ROOT/papers/$PAPER_ID/source/paper.pdf"
PAPERPOILOT_DATA_DIR="$ROOT" "$PAPERPOILOT" reindex >"$ROOT/reindex.log" 2>&1 || {
  echo "FAIL: initial reindex failed" >&2; tail -20 "$ROOT/reindex.log" >&2; exit 1; }

echo "== seeding a legacy job directory (v2 layout, read-only import source)"
mkdir -p "$ROOT/references/translation_jobs"
"$PY" - "$ROOT" "$PAPER_ID" "$JOB_ID" <<'PY'
import json, sys
from pathlib import Path

root, paper_id, job_id = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
jobs = root / "references" / "translation_jobs"
record = {
    "job_id": job_id,
    "paper_id": paper_id,
    "document_version": "sha256:acceptance",
    "task_params": {"max_units": 3},
    "job_key": "acceptance-key",
    "status": "running",  # exactly what a killed process leaves behind
    "created_at": "2026-10-18T00:00:00+00:00",
    "updated_at": "2026-10-18T00:00:00+00:00",
    "attempts": 0,
    "cancel_requested": False,
    "checkpoint_path": None,
    "result": None,
}
(jobs / f"{job_id}.json").write_text(json.dumps(record), encoding="utf-8")
(jobs / f"{job_id}.checkpoint.json").write_text(
    json.dumps(
        {
            "job_id": job_id,
            "paper_id": paper_id,
            "status": "running",
            "payload": {"done": ["p1"]},
            "updated_at": "2026-10-18T00:00:05+00:00",
        }
    ),
    encoding="utf-8",
)
print("seeded", job_id)
PY
LEGACY_BEFORE="$ROOT/.legacy.sha256"
( cd "$ROOT/references" && sha256sum ./*_jobs/*.json | sort ) >"$LEGACY_BEFORE"

echo "== starting the server: the running job must be imported and re-dispatched"
start_server 1
STATUS=""
ATTEMPTS=""
for _ in $(seq 1 60); do
  BODY="$(curl -fsS "http://127.0.0.1:$PORT/api/papers/$PAPER_ID/translation/jobs/$JOB_ID" 2>/dev/null || true)"
  if [[ -n "$BODY" ]]; then
    STATUS="$("$PY" -c 'import json,sys; print(json.load(sys.stdin).get("status",""))' <<<"$BODY")"
    ATTEMPTS="$("$PY" -c 'import json,sys; print(json.load(sys.stdin).get("attempts",0))' <<<"$BODY")"
    [[ "$STATUS" != "queued" && "$STATUS" != "running" ]] && break
  fi
  sleep 1
done
echo "job status=$STATUS attempts=$ATTEMPTS"
[[ "$ATTEMPTS" -ge 1 ]] || { echo "FAIL: the restarted server never re-ran the job" >&2; exit 1; }
[[ "$STATUS" != "queued" && "$STATUS" != "running" ]] || {
  echo "FAIL: job still $STATUS after restart" >&2; exit 1; }
echo "OK: job left 'running' was recovered after restart (status=$STATUS, attempts=$ATTEMPTS)"

echo "== the legacy job directory must still be byte-identical"
( cd "$ROOT/references" && sha256sum ./*_jobs/*.json | sort ) >"$ROOT/.legacy.after.sha256"
diff -u "$LEGACY_BEFORE" "$ROOT/.legacy.after.sha256" >/dev/null || {
  echo "FAIL: references/*_jobs was rewritten" >&2; exit 1; }
echo "OK: references/translation_jobs untouched"

echo "== the checkpoint moved into db.sqlite"
PAPERPOILOT_DATA_DIR="$ROOT" "$PY" - "$ROOT" "$JOB_ID" <<'PY'
import sys
from pathlib import Path
from paperpilot.storage.db import Database

root, job_id = Path(sys.argv[1]), sys.argv[2]
with Database(data_root=root) as database:
    job = database.get_job(job_id)
    assert job is not None, "job row missing from db.sqlite"
    assert job["kind"] == "translation", job
    assert job["status"] not in {"queued", "running"}, job
    events = database.list_job_events(job_id)
    kinds = [event["event"] for event in events]
    assert [event["seq"] for event in events] == list(range(1, len(events) + 1)), kinds
    assert "status" in kinds, kinds
    print(f"kind={job['kind']} status={job['status']} attempts={job['attempts']} events={kinds}")
    print("counts:", database.count_jobs())
PY

echo "== restarting with a fresh database: the legacy job is importable again"
stop_server
rm -f "$ROOT/db.sqlite" "$ROOT/db.sqlite-wal" "$ROOT/db.sqlite-shm"
PAPERPOILOT_DATA_DIR="$ROOT" "$PAPERPOILOT" reindex >"$ROOT/reindex2.log" 2>&1 || {
  echo "FAIL: reindex after deleting db.sqlite failed" >&2; tail -20 "$ROOT/reindex2.log" >&2; exit 1; }
start_server 2
for _ in $(seq 1 60); do
  BODY="$(curl -fsS "http://127.0.0.1:$PORT/api/papers/$PAPER_ID/translation/jobs/$JOB_ID" 2>/dev/null || true)"
  [[ -n "$BODY" ]] && break
  sleep 1
done
[[ -n "${BODY:-}" ]] || { echo "FAIL: job not re-imported after db.sqlite was deleted" >&2; exit 1; }
REIMPORTED="$("$PY" -c 'import json,sys; data=json.load(sys.stdin); print(data["status"], data.get("attempts"))' <<<"$BODY")"
echo "OK: job re-imported from references/translation_jobs -> $REIMPORTED"
( cd "$ROOT/references" && sha256sum ./*_jobs/*.json | sort ) >"$ROOT/.legacy.final.sha256"
diff -u "$LEGACY_BEFORE" "$ROOT/.legacy.final.sha256" >/dev/null || {
  echo "FAIL: references/*_jobs was rewritten after the second start" >&2; exit 1; }

stop_server
echo "P0.4 acceptance PASSED"
