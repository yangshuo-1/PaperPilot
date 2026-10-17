#!/usr/bin/env bash
# M0 P0.7 acceptance: deleting <data_dir>/db.sqlite must be recoverable with
# `paperpilot reindex`, and the rebuilt index must match the pre-delete state.
#
# Usage: scripts/acceptance_reindex.sh [data_root]
#   data_root defaults to $PAPERPOILOT_DATA_DIR or $XDG_DATA_HOME/paperpilot.
# Destructive by design (deletes db.sqlite) — it keeps a backup next to the DB as
# db.sqlite.reindex-acceptance.bak and restores it if the rebuild fails.
set -euo pipefail

ROOT="${1:-${PAPERPOILOT_DATA_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/paperpilot}}"
ROOT="$(cd "$ROOT" && pwd)"
PY="${PY:-.venv/bin/python}"
PAPERPOILOT="${PAPERPOILOT:-.venv/bin/paperpilot}"
STATE="$ROOT/.reindex-acceptance"
SEARCH_QUERIES='("注意力", "attention", "retrieval", "embedding")'
export SEARCH_QUERIES

echo "== data root: $ROOT"
[[ -f "$ROOT/db.sqlite" ]] || { echo "FAIL: no $ROOT/db.sqlite to delete" >&2; exit 1; }

echo "== capturing pre-delete state"
"$PY" - "$ROOT" "$STATE.pre.json" <<'PY'
import json, sys
from pathlib import Path
from paperpilot.storage.db import Database

root, out = Path(sys.argv[1]), Path(sys.argv[2])
with Database(data_root=root) as database:
    state = {
        "counts": database.table_counts(),
        "papers": database.list_papers(),
        "tags": sorted((r["paper_id"], r["tag"]) for r in database.list_tags()),
        "folders": database.list_folders(),
        "annotations": sorted(r["id"] for r in database.list_annotations()),
        "reading_list": database.list_reading_list(),
        "search": {
            query: sorted(item["paper_id"] for item in database.search(query, limit=10))
            for query in __import__("ast").literal_eval(__import__("os").environ["SEARCH_QUERIES"])
        },
    }
out.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
print("papers=%d tags=%d folders=%d" % (state["counts"]["papers"], state["counts"]["tags"], state["counts"]["folders"]))
PY

echo "== hashing the frozen legacy files (must not be rewritten)"
LEGACY_BEFORE="$STATE.references.sha256"
( cd "$ROOT/references" && sha256sum ./* 2>/dev/null | sort ) > "$LEGACY_BEFORE" || true

echo "== refreshing the live export (reindex over a healthy database)"
"$PAPERPOILOT" reindex >/tmp/reindex-acceptance-refresh.log 2>&1 || {
  echo "FAIL: reindex failed"; tail -20 /tmp/reindex-acceptance-refresh.log >&2; exit 1; }
ls "$ROOT/index" >/dev/null || { echo "FAIL: $ROOT/index was not written" >&2; exit 1; }

( cd "$ROOT/references" && sha256sum ./* 2>/dev/null | sort ) > "$STATE.references.after.sha256" || true
diff -u "$LEGACY_BEFORE" "$STATE.references.after.sha256" >/dev/null || {
  echo "FAIL: references/ was modified by the runtime" >&2; exit 1; }
echo "OK: references/ untouched; export written to index/"

echo "== deleting db.sqlite and rebuilding"
cp "$ROOT/db.sqlite" "$ROOT/db.sqlite.reindex-acceptance.bak"
rm -f "$ROOT/db.sqlite" "$ROOT/db.sqlite-wal" "$ROOT/db.sqlite-shm"
if ! "$PAPERPOILOT" reindex >/tmp/reindex-acceptance.log 2>&1; then
  echo "FAIL: reindex after delete failed" >&2; tail -20 /tmp/reindex-acceptance.log >&2
  cp "$ROOT/db.sqlite.reindex-acceptance.bak" "$ROOT/db.sqlite"; exit 1
fi
tail -12 /tmp/reindex-acceptance.log

echo "== comparing rebuilt state with the pre-delete state"
"$PY" - "$ROOT" "$STATE.pre.json" <<'PY'
import json, sys
from pathlib import Path
from paperpilot.storage.db import Database

root, snapshot = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
with Database(data_root=root) as database:
    after = {
        "counts": database.table_counts(),
        "papers": database.list_papers(),
        "tags": sorted((r["paper_id"], r["tag"]) for r in database.list_tags()),
        "folders": database.list_folders(),
        "annotations": sorted(r["id"] for r in database.list_annotations()),
        "reading_list": database.list_reading_list(),
        "search": {
            query: sorted(item["paper_id"] for item in database.search(query, limit=10))
            for query in __import__("ast").literal_eval(__import__("os").environ["SEARCH_QUERIES"])
        },
    }
failures = []
gained = []
for key in ("counts", "papers", "folders", "reading_list"):
    if after[key] != snapshot[key]:
        failures.append(f"{key} differs:\n  before={snapshot[key]!r}\n  after ={after[key]!r}")
for paper_id, tag in snapshot["tags"]:
    if (paper_id, tag) not in after["tags"]:
        failures.append(f"tag lost: {paper_id}:{tag}")
if set(after["annotations"]) != set(snapshot["annotations"]):
    failures.append(f"annotations differ: before={snapshot['annotations']} after={after['annotations']}")
# Rebuilding the FTS from on-disk text must not *lose* any hit; extra recall is fine
# (the on-disk analysis text is richer than what the old importer indexed).
for query, hits in snapshot["search"].items():
    lost = [item for item in hits if item not in after["search"][query]]
    if lost:
        failures.append(f"search({query!r}) lost hits {lost} (before={hits} after={after['search'][query]})")
    extra = [item for item in after["search"][query] if item not in hits]
    if extra:
        gained.append(f"search({query!r}) gained {extra}")
if failures:
    print("FAIL: rebuilt state differs from pre-delete state")
    for item in failures:
        print(" -", item)
    sys.exit(1)
print("OK: papers/tags/folders/annotations/reading-list/FTS preserved after delete + reindex")
for item in gained:
    print("note:", item)
print("counts:", after["counts"])
PY

echo "== restarting the server against the rebuilt database"
PORT="${PORT:-8128}"
PAPERPOILOT_DATA_DIR="$ROOT" "$PAPERPOILOT" serve --port "$PORT" >/tmp/reindex-acceptance-serve.log 2>&1 &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT
for _ in $(seq 1 40); do curl -fsS "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1 && break; sleep 0.5; done
HEALTH="$(curl -fsS "http://127.0.0.1:$PORT/api/health" 2>/dev/null || true)"
PAPERS="$(curl -fsS "http://127.0.0.1:$PORT/api/papers" 2>/dev/null || true)"
PAPER_COUNT="$("$PY" -c 'import json,sys; data=json.load(sys.stdin); print(data["total"] if isinstance(data, dict) else len(data))' <<<"$PAPERS")"
PAPER_ID="$("$PY" -c 'import json,sys; data=json.load(sys.stdin); items=data["papers"] if isinstance(data, dict) else data; print(items[0]["id"])' <<<"$PAPERS")"
echo "health=$HEALTH"
echo "papers=$PAPER_COUNT first=$PAPER_ID"
for path in "/api/papers/$PAPER_ID" "/api/papers/$PAPER_ID/documents" "/api/papers/$PAPER_ID/reader" "/api/papers/$PAPER_ID/reading/structured" "/api/papers/$PAPER_ID/assets/manifest" "/api/papers/$PAPER_ID/analysis" "/api/papers/$PAPER_ID/translation" "/api/papers/$PAPER_ID/search?q=attention"; do
  code="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT$path")"
  echo "  $code $path"
  [[ "$code" == "200" ]] || { echo "FAIL: $path -> $code" >&2; exit 1; }
done
[[ "$HEALTH" == *'"ok":true'* ]] || { echo "FAIL: health not ok" >&2; exit 1; }
echo "OK: server serves the rebuilt index (papers=$PAPER_COUNT)"
rm -f "$ROOT/db.sqlite.reindex-acceptance.bak"
echo "P0.7 acceptance PASSED"
