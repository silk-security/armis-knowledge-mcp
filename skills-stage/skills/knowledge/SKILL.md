---
name: knowledge-stage
description: "Query the Armis Knowledge base (STAGE) for organizational standards, policies, and tenant-specific guidance. Use when generating, reviewing, or remediating code so the work matches the organization's standards. Triggers: /knowledge-stage, what are our standards for, what does our org say about, search knowledge, list standards."
allowed-tools:
  - Bash(security *)
  - Bash(secret-tool *)
  - Bash(curl *)
  - Bash(jq *)
  - Bash(source *)
---

# /knowledge-stage

Query the Armis Knowledge backend in the **stage** environment
(`knowledge-api.moose-stg.armis.com`) directly via HTTPS — no MCP server
in the loop.

## Auth model

- `client_id` and `tenant_slug` are env vars (`ARMIS_KNOWLEDGE_CLIENT_ID`,
  `ARMIS_KNOWLEDGE_TENANT_SLUG`).
- `client_secret` lives in the OS keychain (service `armis-knowledge-stage`,
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

`/knowledge-stage <query>` — full-text search over enabled docs:

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

`/knowledge-stage list <scope>` — `scope` ∈ `organization`, `department`, `team`, `project`:

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
  `/settings/integrations` on `knowledge.moose-stg.armis.com`, then update the
  keychain entry: `security add-generic-password -U -s armis-knowledge-stage
  -a "$ARMIS_KNOWLEDGE_CLIENT_ID" -w`.
- `401 missing_bearer_token` — env vars not set. Tell the user to export
  `ARMIS_KNOWLEDGE_CLIENT_ID` and `ARMIS_KNOWLEDGE_TENANT_SLUG`.
- `404 tenant_not_found` — slug typo or tenant not provisioned in stage.
