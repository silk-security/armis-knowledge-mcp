#!/usr/bin/env bash
# Local stdio bridge launcher.
#
# Bootstraps a venv on first run, installs pinned deps, then execs the
# Python bridge that proxies MCP traffic to the remote knowledge MCP with
# a fresh JWT attached. Mirrors armis-appsec-mcp/run.sh so the cold-start
# UX matches.
set -eu

PLUGIN_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PLUGIN_DIR/.venv"
REQS_FILE="$PLUGIN_DIR/requirements.txt"
DEPS_SENTINEL="$VENV_DIR/.deps-installed"

# Hash requirements.txt so we reinstall when it changes — same trick as
# armis-appsec-mcp. Falls back to a sentinel touch if neither sha256 tool
# is available; that just means upgrades require manual venv removal.
REQS_HASH=""
if command -v sha256sum >/dev/null 2>&1; then
    REQS_HASH="$(sha256sum "$REQS_FILE" 2>/dev/null | cut -d ' ' -f1)"
elif command -v shasum >/dev/null 2>&1; then
    REQS_HASH="$(shasum -a 256 "$REQS_FILE" 2>/dev/null | cut -d ' ' -f1)"
fi

NEEDS_INSTALL=0
if [ ! -f "$DEPS_SENTINEL" ]; then
    NEEDS_INSTALL=1
elif [ -n "$REQS_HASH" ]; then
    STORED_HASH="$(cat "$DEPS_SENTINEL" 2>/dev/null || true)"
    if [ "$STORED_HASH" != "$REQS_HASH" ]; then
        NEEDS_INSTALL=1
    fi
fi

if [ "$NEEDS_INSTALL" -eq 1 ]; then
    python3 -m venv "$VENV_DIR" \
        || { echo "ERROR: python3 -m venv failed. Is python3 installed?" >&2; exit 1; }
    "$VENV_DIR/bin/pip" install -r "$REQS_FILE" --quiet \
        || { echo "ERROR: pip install failed. Check requirements.txt and network connectivity." >&2; exit 1; }
    if [ -n "$REQS_HASH" ]; then
        printf '%s\n' "$REQS_HASH" > "$DEPS_SENTINEL"
    else
        touch "$DEPS_SENTINEL"
    fi
fi

# Credential validation happens in Python — bridge.py loads .env from the
# plugin dir before checking, which the shell can't see without parsing the
# file itself. Missing creds surface as a one-line RuntimeError on stderr.

exec "$VENV_DIR/bin/python" "$PLUGIN_DIR/bridge.py"
