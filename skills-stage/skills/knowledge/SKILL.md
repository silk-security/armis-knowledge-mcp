---
name: knowledge-stage
description: "Query the Armis Knowledge base (STAGE) for organizational standards, policies, and tenant-specific guidance. Use when generating, reviewing, or remediating code so the work matches the organization's standards. Triggers: /knowledge-stage, what are our standards for, what does our org say about, search knowledge, list standards."
allowed-tools:
  - Bash(curl *)
  - Bash(jq *)
  - Bash(source *)
---

# /knowledge-stage

Query the Armis Knowledge backend in the **stage** environment
(`knowledge-api.moose-stg.armis.com`) directly via HTTPS — no MCP server
in the loop.

## Auth model

- `ARMIS_CLIENT_ID` and `ARMIS_CLIENT_SECRET` are env vars (set in your
  shell rc); the backend resolves your tenant from these credentials
  server-side. You never pass a tenant.
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

Results come back in priority order already — apply them top-down. Briefly
cite which scope each applied standard came from so the user can audit.

## Errors

- `401 invalid_client_credentials` — secret rotated. Refresh from
  `/settings/integrations` on `knowledge.moose-stg.armis.com` and re-export
  `ARMIS_CLIENT_SECRET`.
- `401 missing_bearer_token` — env vars not set. Tell the user to export
  `ARMIS_CLIENT_ID` and `ARMIS_CLIENT_SECRET`.
