---
name: knowledge-dev
description: "Query the Armis Knowledge base (DEV) for organizational standards, policies, and tenant-specific guidance. Use when generating, reviewing, or remediating code so the work matches the organization's standards. Triggers: /knowledge-dev, what are our standards for, what does our org say about, search knowledge, list standards."
allowed-tools:
  - Bash(security *)
  - Bash(secret-tool *)
  - Bash(curl *)
  - Bash(jq *)
  - Bash(source *)
---

# /knowledge-dev

Query the Armis Knowledge backend in the **dev** environment
(`knowledge-api.moose-dev.armis.com`) directly via HTTPS — no MCP server
in the loop.

## Auth model

- `client_id` is an env var (`ARMIS_KNOWLEDGE_CLIENT_ID`); the backend
  routes the token exchange to the right tenant by looking the
  client_id up in the global `admin.client_credentials` table.
- `client_secret` lives in the OS keychain (service `armis-knowledge-dev`,
  account = `$ARMIS_KNOWLEDGE_CLIENT_ID`).
- The shared lib mints a fresh JWT on demand and caches it for ~55min in
  `$TMPDIR` with mode `600`. The user never copies a JWT.

## Usage

Source the helper, then call the API:

```bash
source "$CLAUDE_PLUGIN_ROOT/lib/armis-knowledge.sh"
TENANT_ID=$(ak_tenant_id)
```

### Search

`/knowledge-dev <query>` — full-text search over enabled docs:

```bash
ak_get /api/knowledge/search \
  --data-urlencode "tenant_id=$TENANT_ID" \
  --data-urlencode "q=$ARGUMENTS" \
  --data-urlencode "limit=10"
```

Returns `[{id, title, scope, scope_ref, content_pack, path, snippet, score}, ...]`.
For each hit you want to apply, fetch the body:

```bash
ak_get "/api/knowledge/$DOC_ID" --data-urlencode "tenant_id=$TENANT_ID"
```

### List by scope

`/knowledge-dev list <scope>` — `scope` ∈ `organization`, `department`, `team`, `project`:

```bash
ak_get /api/knowledge/by-scope \
  --data-urlencode "tenant_id=$TENANT_ID" \
  --data-urlencode "scope=$SCOPE"
```

## How to apply

Apply standards in priority order: **project > team > department > organization**.
Briefly cite which scope each applied standard came from so the user can audit.

## Errors

- `401 invalid_client_credentials` — secret rotated. Refresh from
  `/settings/integrations` on `knowledge.moose-dev.armis.com`, then update the
  keychain entry: `security add-generic-password -U -s armis-knowledge-dev
  -a "$ARMIS_KNOWLEDGE_CLIENT_ID" -w`.
- `401 missing_bearer_token` — env var not set. Tell the user to export
  `ARMIS_KNOWLEDGE_CLIENT_ID`.
- `401 invalid_client_credentials` — client_id has no admin routing row
  (no tenant claims this credential), or secret didn't bcrypt-verify.
