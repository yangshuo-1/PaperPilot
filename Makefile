SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.ONESHELL:
.DEFAULT_GOAL := doctor

ROOT_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
VENV_PYTHON := $(ROOT_DIR)/.venv/bin/python
NODE_FALLBACK_DIR ?= /home/yang/.nvm/versions/node/v22.22.0/bin

# Prefer a usable node from PATH. The fixed nvm installation is the fallback
# for shells that still expose an older system node first.
NODE_BIN := $(shell \
	path_node=`command -v node 2>/dev/null || true`; \
	for candidate in "$$path_node" "$(NODE_FALLBACK_DIR)/node"; do \
		[ -x "$$candidate" ] || continue; \
		version=`"$$candidate" --version 2>/dev/null || true`; \
		major=`printf '%s' "$$version" | sed 's/^v//' | cut -d. -f1`; \
		if [ -n "$$major" ] && [ "$$major" -ge 18 ] 2>/dev/null; then printf '%s' "$$candidate"; break; fi; \
	done)
NODE_DIR := $(if $(NODE_BIN),$(dir $(NODE_BIN)),)
NPM_BIN := $(if $(NODE_BIN),$(NODE_DIR)npm,)

.PHONY: dev doctor test build _check-venv _check-node

doctor:
	@bash "$(ROOT_DIR)/scripts/doctor.sh"

_check-venv:
	@if [[ ! -x "$(VENV_PYTHON)" ]]; then
		printf '%s\n' "ERROR: .venv/bin/python is missing. Run: uv venv .venv && uv pip install -r requirements.txt" >&2
		exit 1
	fi

_check-node:
	@if [[ -z "$(NODE_BIN)" || ! -x "$(NODE_BIN)" ]]; then
		printf '%s\n' "ERROR: Node.js >=18 is unavailable. Use nvm or export PATH=$(NODE_FALLBACK_DIR):\$${PATH}" >&2
		exit 1
	fi
	if [[ -z "$(NPM_BIN)" || ! -x "$(NPM_BIN)" ]]; then
		printf '%s\n' "ERROR: npm for $(NODE_BIN) is unavailable. Install npm with Node.js >=18." >&2
		exit 1
	fi

dev: _check-venv _check-node
	@cd "$(ROOT_DIR)"
	backend_pid=
	frontend_pid=

	cleanup() {
		status=$$?
		trap - INT TERM EXIT
		if [[ -n "$$frontend_pid" ]] && kill -0 "$$frontend_pid" 2>/dev/null; then
			kill -TERM "$$frontend_pid" 2>/dev/null || true
		fi
		if [[ -n "$$backend_pid" ]] && kill -0 "$$backend_pid" 2>/dev/null; then
			kill -TERM "$$backend_pid" 2>/dev/null || true
		fi
		if [[ -n "$$frontend_pid" ]]; then wait "$$frontend_pid" 2>/dev/null || true; fi
		if [[ -n "$$backend_pid" ]]; then wait "$$backend_pid" 2>/dev/null || true; fi
		exit "$$status"
	}
	trap cleanup INT TERM EXIT

	(
		cd "$(ROOT_DIR)"
		exec "$(VENV_PYTHON)" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8020
	) &
	backend_pid=$$!
	(
		cd "$(ROOT_DIR)/frontend"
		export PATH="$(NODE_DIR):$$PATH"
		exec "$(NPM_BIN)" run dev -- --port 5173
	) &
	frontend_pid=$$!

	health_url=http://127.0.0.1:8020/api/health
	ready=0
	attempt=1
	printf '%s\n' "Waiting for $$health_url ..."
	while (( attempt <= 60 )); do
		if "$(VENV_PYTHON)" -c 'import sys, urllib.request; response = urllib.request.urlopen(sys.argv[1], timeout=1); sys.exit(0 if 200 <= response.status < 300 else 1)' "$$health_url" >/dev/null 2>&1; then
			ready=1
			break
		fi
		if ! kill -0 "$$backend_pid" 2>/dev/null; then
			if wait "$$backend_pid"; then status=0; else status=$$?; fi
			printf '%s\n' "ERROR: backend exited before health check became ready." >&2
			exit "$$status"
		fi
		if ! kill -0 "$$frontend_pid" 2>/dev/null; then
			if wait "$$frontend_pid"; then status=0; else status=$$?; fi
			printf '%s\n' "ERROR: frontend exited before the backend health check became ready." >&2
			exit "$$status"
		fi
		sleep 1
		attempt=$$((attempt + 1))
	done
	if (( ready != 1 )); then
		printf '%s\n' "ERROR: backend health check timed out after 60 seconds." >&2
		exit 1
	fi
	printf '%s\n' "paper_valt is ready: http://127.0.0.1:5173"
	printf '%s\n' "Backend health: $$health_url"

	while :; do
		if ! kill -0 "$$backend_pid" 2>/dev/null; then
			if wait "$$backend_pid"; then status=0; else status=$$?; fi
			printf '%s\n' "Backend stopped." >&2
			exit "$$status"
		fi
		if ! kill -0 "$$frontend_pid" 2>/dev/null; then
			if wait "$$frontend_pid"; then status=0; else status=$$?; fi
			printf '%s\n' "Frontend stopped." >&2
			exit "$$status"
		fi
		sleep 1
	done

test: _check-venv _check-node
	@cd "$(ROOT_DIR)"
	"$(VENV_PYTHON)" -m compileall backend/app && \
	"$(VENV_PYTHON)" -m unittest discover -s tests -p 'test*.py' && \
	cd frontend && PATH="$(NODE_DIR):$$PATH" "$(NPM_BIN)" run build

build: _check-node
	@cd "$(ROOT_DIR)/frontend"
	PATH="$(NODE_DIR):$$PATH" "$(NPM_BIN)" run build
