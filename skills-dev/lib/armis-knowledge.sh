# Shared helpers for the armis-knowledge-skills (dev) plugin.
#
# Sourced by every SKILL.md. Sets `ak_*` functions that mint JWTs from the
# user's stored client_id/client_secret and call the backend API.
#
# Documented credentials: ARMIS_CLIENT_ID / ARMIS_CLIENT_SECRET (env).
#
# Optional env:
#   ARMIS_KNOWLEDGE_API   override backend URL (default: dev)

set -euo pipefail

ARMIS_KNOWLEDGE_ENV="${ARMIS_KNOWLEDGE_ENV:-dev}"
ARMIS_KNOWLEDGE_API="${ARMIS_KNOWLEDGE_API:-https://knowledge-api.moose-dev.armis.com}"

# Load $CLAUDE_PLUGIN_ROOT/.env, but only fill in vars not already set in
# the shell — same precedence as python-dotenv's override=False on the MCP
# side. Done before resolving creds so .env can supply either prefixed or
# bare names.
if [[ -n "${CLAUDE_PLUGIN_ROOT:-}" && -f "$CLAUDE_PLUGIN_ROOT/.env" ]]; then
  while IFS='=' read -r _ak_key _ak_val; do
    [[ -z $_ak_key || ${_ak_key:0:1} == '#' ]] && continue
    _ak_key="${_ak_key#export }"
    _ak_key="${_ak_key// /}"
    _ak_val="${_ak_val%\"}"; _ak_val="${_ak_val#\"}"
    _ak_val="${_ak_val%\'}"; _ak_val="${_ak_val#\'}"
    [[ -z ${!_ak_key:-} ]] && export "$_ak_key=$_ak_val"
  done < "$CLAUDE_PLUGIN_ROOT/.env"
  unset _ak_key _ak_val
fi

# Resolve creds: knowledge-specific override wins over the shared default.
_ak_client_id="${ARMIS_KNOWLEDGE_CLIENT_ID:-${ARMIS_CLIENT_ID:-}}"
_ak_client_secret="${ARMIS_KNOWLEDGE_CLIENT_SECRET:-${ARMIS_CLIENT_SECRET:-}}"

if [[ -z $_ak_client_id ]]; then
  echo "set ARMIS_CLIENT_ID; copy from /settings/integrations on the knowledge webapp" >&2
  return 1 2>/dev/null || exit 1
fi
if [[ -z $_ak_client_secret ]]; then
  echo "set ARMIS_CLIENT_SECRET; copy from /settings/integrations on the knowledge webapp" >&2
  return 1 2>/dev/null || exit 1
fi

for _bin in curl jq; do
  command -v "$_bin" >/dev/null || { echo "missing required binary: $_bin" >&2; return 1 2>/dev/null || exit 1; }
done

_ak_token_cache="${TMPDIR:-/tmp}/armis-knowledge-${ARMIS_KNOWLEDGE_ENV}.${_ak_client_id}.jwt"

_ak_mtime() {
  stat -f %m "$1" 2>/dev/null || stat -c %Y "$1" 2>/dev/null
}

# Mint or return a cached JWT. Tokens TTL 1h server-side; we refresh at 55m
# to avoid edge-of-expiry failures mid-call.
ak_token() {
  if [[ -f $_ak_token_cache ]]; then
    local age=$(( $(date +%s) - $(_ak_mtime "$_ak_token_cache") ))
    if (( age < 3300 )); then
      cat "$_ak_token_cache"; return
    fi
  fi
  local body; body=$(jq -nc \
    --arg id "$_ak_client_id" \
    --arg s "$_ak_client_secret" \
    '{client_id:$id,client_secret:$s}')
  # mktemp gives an unpredictable path with mode 600, so a local attacker
  # can't pre-create a symlink at the response path and divert curl's
  # output (CWE-377). Trap ensures the file is removed on any exit path.
  local resp_file; resp_file=$(mktemp "${TMPDIR:-/tmp}/_ak_resp.XXXXXX") || return 1
  trap 'rm -f "$resp_file"' RETURN
  local http
  http=$(curl -sS -o "$resp_file" -w '%{http_code}' \
    -X POST "$ARMIS_KNOWLEDGE_API/api/v1/auth/token" \
    -H 'content-type: application/json' \
    -d "$body") || return 1
  if [[ $http != 2* ]]; then
    echo "token exchange failed (HTTP $http): $(cat "$resp_file")" >&2
    return 1
  fi
  jq -r .token < "$resp_file" > "$_ak_token_cache"
  chmod 600 "$_ak_token_cache"
  cat "$_ak_token_cache"
}

# Tenant UUID is in the JWT claims. Backend routes take it as a query param
# (`tenant_id=...`) and validate it matches the bearer claim — so passing it
# from the client doesn't widen trust, it just keeps the URL self-describing.
ak_tenant_id() {
  local claims; claims=$(ak_token | awk -F. '{print $2}')
  # JWT uses base64url + omits padding — restore both before decoding.
  local pad=$(( 4 - ${#claims} % 4 ))
  (( pad < 4 )) && claims+=$(printf '=%.0s' $(seq 1 $pad))
  claims=${claims//-/+}
  claims=${claims//_//}
  printf '%s' "$claims" | base64 -d 2>/dev/null | jq -r '.tenant_id // empty'
}

# Wrap curl with the bearer header. Pass the path as $1; the rest goes to curl
# verbatim (use --data-urlencode for query params).
ak_get() {
  local path=$1; shift
  curl -fsS -G \
    -H "authorization: Bearer $(ak_token)" \
    "$ARMIS_KNOWLEDGE_API$path" "$@"
}

ak_post() {
  local path=$1; shift
  curl -fsS \
    -H "authorization: Bearer $(ak_token)" \
    -H 'content-type: application/json' \
    -X POST -d "$1" "$ARMIS_KNOWLEDGE_API$path"
}
