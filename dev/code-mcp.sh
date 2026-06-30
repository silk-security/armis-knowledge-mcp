#!/usr/bin/env bash
# Local stdio launcher for the codebase-memory-mcp code-intelligence server
# (github.com/DeusData/codebase-memory-mcp). Registered as `armis-code-mcp`
# so the /threat-model skill's mcp__armis_code_mcp__* tool calls resolve.
#
# Bootstraps a single static binary on first run: downloads the pinned
# release tarball for this OS/arch, verifies its sha256 against the digest
# baked in below, extracts the binary, then execs it as an MCP stdio server
# (no subcommand needed). Mirrors run.sh's cold-start UX so the two MCP
# servers in this plugin behave the same on first launch.
#
# The binary speaks MCP over stdio and indexes repos into a local graph
# under CBM_CACHE_DIR. No network calls to Armis infra, no credentials.
set -eu

# Pinned upstream release. Bump VERSION + the four sha256 digests together
# (from the release's checksums.txt) to upgrade.
# Linux digests are for the -portable assets (see detect_asset below); macOS
# digests are for the standard assets. All from the release checksums.txt.
VERSION="v0.8.1"
SHA256_DARWIN_ARM64="fbd047509852021b5446a11141bcb0a3d1dcaebf6e5112460960f29f052c1c58"
SHA256_DARWIN_AMD64="fb62da3016ea12b948351208759b5c083fb1446cf6e78d6db8b7cd28fe86fd54"
SHA256_LINUX_ARM64="13526acc2a6a0697dff3c763fb443a416589bc10ad8b12015b63d87e515dd72b"
SHA256_LINUX_AMD64="6ab87a6c05d049dde57700803ca0ab4199fcf25973a0606618af0fcee73f5abd"

PLUGIN_DIR="$(cd "$(dirname "$0")" && pwd)"
# Per-install cache for the downloaded binary + index graph. Lives under the
# plugin dir (gitignored, excluded from publish) so it never ships.
CACHE_ROOT="$PLUGIN_DIR/.code-mcp"
BIN_DIR="$CACHE_ROOT/$VERSION"
BIN="$BIN_DIR/codebase-memory-mcp"

# Keep the index graph alongside the binary unless the user points it
# elsewhere, so a plugin uninstall (rm -rf the plugin dir) cleans up fully.
export CBM_CACHE_DIR="${CBM_CACHE_DIR:-$CACHE_ROOT/graph}"

# --- platform detection (matches upstream install.sh asset naming) ---------
detect_asset() {
    os="$(uname -s)"
    arch="$(uname -m)"
    case "$os" in
        Darwin) os_tag="darwin" ;;
        Linux)  os_tag="linux" ;;
        *) echo "ERROR: unsupported OS '$os' for codebase-memory-mcp (need Darwin or Linux)." >&2; exit 1 ;;
    esac
    case "$arch" in
        arm64|aarch64) arch_tag="arm64" ;;
        x86_64|amd64)  arch_tag="amd64" ;;
        *) echo "ERROR: unsupported arch '$arch' for codebase-memory-mcp." >&2; exit 1 ;;
    esac
    # Linux ships a -portable variant built against an older glibc; prefer it
    # so the binary runs across distros without a libc version mismatch.
    if [ "$os_tag" = "linux" ]; then
        ASSET="codebase-memory-mcp-${os_tag}-${arch_tag}-portable.tar.gz"
    else
        ASSET="codebase-memory-mcp-${os_tag}-${arch_tag}.tar.gz"
    fi
    case "${os_tag}-${arch_tag}" in
        darwin-arm64) EXPECTED_SHA="$SHA256_DARWIN_ARM64" ;;
        darwin-amd64) EXPECTED_SHA="$SHA256_DARWIN_AMD64" ;;
        linux-arm64)  EXPECTED_SHA="$SHA256_LINUX_ARM64" ;;
        linux-amd64)  EXPECTED_SHA="$SHA256_LINUX_AMD64" ;;
    esac
}

sha256_of() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | cut -d ' ' -f1
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | cut -d ' ' -f1
    else
        echo "ERROR: need sha256sum or shasum to verify the download." >&2
        exit 1
    fi
}

if [ ! -x "$BIN" ]; then
    detect_asset
    URL="https://github.com/DeusData/codebase-memory-mcp/releases/download/${VERSION}/${ASSET}"
    TMP="$(mktemp -d "${TMPDIR:-/tmp}/code-mcp.XXXXXX")"
    trap 'rm -rf "$TMP"' EXIT

    command -v curl >/dev/null 2>&1 || { echo "ERROR: curl is required to bootstrap codebase-memory-mcp." >&2; exit 1; }
    echo "armis-code-mcp: downloading ${ASSET} (${VERSION})..." >&2
    curl -fsSL "$URL" -o "$TMP/asset.tar.gz" \
        || { echo "ERROR: download failed: $URL" >&2; exit 1; }

    GOT_SHA="$(sha256_of "$TMP/asset.tar.gz")"
    if [ "$GOT_SHA" != "$EXPECTED_SHA" ]; then
        echo "ERROR: sha256 mismatch for ${ASSET}." >&2
        echo "  expected: $EXPECTED_SHA" >&2
        echo "  got:      $GOT_SHA" >&2
        exit 1
    fi

    mkdir -p "$BIN_DIR"
    # The binary sits at the tarball root; extract just it.
    tar xzf "$TMP/asset.tar.gz" -C "$BIN_DIR" codebase-memory-mcp \
        || { echo "ERROR: failed to extract codebase-memory-mcp from archive." >&2; exit 1; }
    chmod +x "$BIN"
    rm -rf "$TMP"
    trap - EXIT
fi

exec "$BIN" "$@"
