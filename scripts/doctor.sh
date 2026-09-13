#!/usr/bin/env bash

set -u -o pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NODE_FALLBACK_DIR="${NODE_FALLBACK_DIR:-/home/yang/.nvm/versions/node/v22.22.0/bin}"
CHECK_COUNT=0
FAILURE_COUNT=0

pass() {
	CHECK_COUNT=$((CHECK_COUNT + 1))
	printf '✅ %s\n' "$1"
	printf '   修复建议: 无需修复。\n'
}

fail() {
	CHECK_COUNT=$((CHECK_COUNT + 1))
	FAILURE_COUNT=$((FAILURE_COUNT + 1))
	printf '❌ %s\n' "$1"
	printf '   修复建议: %s\n' "$2"
}

version_for() {
	local tool="$1"
	"$tool" --version 2>/dev/null | head -n 1
}

python_version_for() {
	local tool="$1"
	"$tool" -c 'import platform; print(platform.python_version())' 2>/dev/null
}

major_minor_ok() {
	local version="$1"
	local minimum_major="$2"
	local minimum_minor="$3"
	local major minor
	version="${version#v}"
	major="${version%%.*}"
	minor="${version#*.}"
	minor="${minor%%.*}"
	case "$major" in
		''|*[!0-9]*) return 1 ;;
	esac
	case "$minor" in
		''|*[!0-9]*) return 1 ;;
	esac
	if (( major > minimum_major || (major == minimum_major && minor >= minimum_minor) )); then
		return 0
	fi
	return 1
}

printf '%s\n' "paper_valt environment doctor"
printf '%s\n' "Repository: $REPO_ROOT"
printf '%s\n' ""

# Prefer the system interpreter for this independent version check, but use
# the project interpreter when no system python is available.
PYTHON_BIN=""
for candidate in "$(command -v python3 2>/dev/null || true)" "$(command -v python 2>/dev/null || true)" "$REPO_ROOT/.venv/bin/python"; do
	if [[ -n "$candidate" && -x "$candidate" ]]; then
		PYTHON_BIN="$candidate"
		break
	fi
done
if [[ -z "$PYTHON_BIN" ]]; then
	fail "python>=3.10: no usable Python interpreter found" "Install Python 3.10+ and ensure python3 is on PATH."
else
	PYTHON_VERSION="$(python_version_for "$PYTHON_BIN")"
	if major_minor_ok "$PYTHON_VERSION" 3 10; then
		pass "python>=3.10: $PYTHON_VERSION ($PYTHON_BIN)"
	else
		fail "python>=3.10: found ${PYTHON_VERSION:-an unknown version} ($PYTHON_BIN)" "Install Python 3.10+ and put its bin directory before older Python versions on PATH."
	fi
fi

if [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then
	pass ".venv: $REPO_ROOT/.venv/bin/python exists"
else
	fail ".venv: $REPO_ROOT/.venv/bin/python is missing" "Run: uv venv .venv && uv pip install -r requirements.txt"
fi

PATH_NODE="$(command -v node 2>/dev/null || true)"
PATH_NODE_VERSION=""
if [[ -n "$PATH_NODE" ]]; then
	PATH_NODE_VERSION="$(version_for "$PATH_NODE")"
fi
FALLBACK_NODE="$NODE_FALLBACK_DIR/node"
FALLBACK_NODE_VERSION=""
if [[ -x "$FALLBACK_NODE" ]]; then
	FALLBACK_NODE_VERSION="$(version_for "$FALLBACK_NODE")"
fi

if [[ -n "$PATH_NODE" ]] && major_minor_ok "$PATH_NODE_VERSION" 18 0; then
	pass "node>=18: ${PATH_NODE_VERSION:-unknown} ($PATH_NODE)"
elif [[ -n "$PATH_NODE" ]]; then
	if [[ -x "$FALLBACK_NODE" ]] && major_minor_ok "$FALLBACK_NODE_VERSION" 18 0; then
		fail "node>=18: PATH resolves to ${PATH_NODE_VERSION:-an unknown version} at $PATH_NODE" "Use Node >=18, for example: export PATH=\"$NODE_FALLBACK_DIR:\$PATH\" (or run nvm use 22). Make can fall back to $FALLBACK_NODE, but the shell PATH still needs repair."
	else
		fail "node>=18: PATH resolves to ${PATH_NODE_VERSION:-an unknown version} at $PATH_NODE" "Install Node >=18 and put it before the old system node on PATH; expected fallback: $FALLBACK_NODE."
	fi
elif [[ -x "$FALLBACK_NODE" ]] && major_minor_ok "$FALLBACK_NODE_VERSION" 18 0; then
	pass "node>=18: using fallback ${FALLBACK_NODE_VERSION:-unknown} ($FALLBACK_NODE)"
else
	fail "node>=18: no usable Node.js executable found" "Install Node >=18 or export PATH=\"$NODE_FALLBACK_DIR:\$PATH\" after installing the configured fallback."
fi

# Diagnose the known WSL system binary even when a valid nvm node is active.
SYSTEM_NODE="/usr/bin/node"
if [[ -x "$SYSTEM_NODE" ]]; then
	SYSTEM_NODE_VERSION="$(version_for "$SYSTEM_NODE")"
	if ! major_minor_ok "$SYSTEM_NODE_VERSION" 18 0 && [[ "$PATH_NODE" != "$SYSTEM_NODE" ]]; then
		printf '   Node path note: %s is %s; keep a Node >=18 directory before /usr/bin in PATH.\n' "$SYSTEM_NODE" "${SYSTEM_NODE_VERSION:-an unknown version}"
	fi
fi

UV_BIN="$(command -v uv 2>/dev/null || true)"
if [[ -n "$UV_BIN" ]]; then
	pass "uv: $UV_BIN ($(version_for "$UV_BIN"))"
else
	fail "uv: command not found" "Install uv and ensure its bin directory is on PATH."
fi

CODEX_BIN="$(command -v codex 2>/dev/null || true)"
if [[ -n "$CODEX_BIN" ]]; then
	pass "codex CLI: $CODEX_BIN"
else
	fail "codex CLI: command not found" "Install or enable the Codex CLI, then ensure codex is on PATH."
fi

if [[ -n "${PAPER_LLM_API_KEY:-}" ]]; then
	pass "LLM config: PAPER_LLM_API_KEY is set (value hidden)"
elif [[ -f "$REPO_ROOT/backend/llm_config.json" ]]; then
	pass "LLM config: backend/llm_config.json exists"
else
	fail "LLM config: no API key environment variable or backend/llm_config.json" "Set PAPER_LLM_API_KEY or create backend/llm_config.json; secrets must stay out of git and logs."
fi

GIT_BIN="$(command -v git 2>/dev/null || true)"
if [[ -n "$GIT_BIN" ]]; then
	pass "git: $GIT_BIN ($(version_for "$GIT_BIN"))"
else
	fail "git: command not found" "Install git and ensure it is on PATH."
fi

printf '%s\n' ""
if (( FAILURE_COUNT == 0 )); then
	printf 'Doctor summary: %d checks passed, 0 failed.\n' "$CHECK_COUNT"
	exit 0
fi
printf 'Doctor summary: %d checks run, %d failed.\n' "$CHECK_COUNT" "$FAILURE_COUNT"
exit 1
