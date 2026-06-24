# Armis Knowledge — Claude Code plugin bundle

Claude Code marketplace that ships **two variants** of the Armis Knowledge
client — an MCP variant and a shell-skills variant — for each environment.
Pick the variant that fits your tooling; don't install both for the same
environment because they register the same slash commands.

> **Already installed?** [USAGE.md](USAGE.md) is the operator cheat sheet for
> the slash commands and the triggers that fire each skill on its own.

> **Use the `-prod` plugins.** Prod runs on `moose.armis.com` and is the env
> everyone uses today. The bare slash commands (`/knowledge`, `/cwe-fix`, …)
> belong to prod. Stage and dev each ship suffixed commands so they can be
> installed side-by-side without colliding with prod.

| Plugin | Variant | Backend | Slash commands |
|---|---|---|---|
| `armis-knowledge-prod` | MCP | `knowledge-mcp.moose.armis.com` | `/knowledge`, `/ask`, `/cwe-fix`, `/framework-guidance`, `/tech-guidance` |
| `armis-knowledge-skills-prod` | shell-skills | `knowledge-api.moose.armis.com` | same commands minus `/ask` (skills variant has no agentic Q&A) |
| `armis-knowledge-stage` | MCP | `knowledge-mcp.moose-stg.armis.com` | `/knowledge-stage`, `/ask-stage`, `/cwe-fix-stage`, `/framework-guidance-stage`, `/tech-guidance-stage` |
| `armis-knowledge-skills-stage` | shell-skills | `knowledge-api.moose-stg.armis.com` | same commands minus `/ask-stage` |
| `armis-knowledge-dev` | MCP (maintainers) | `knowledge-mcp.moose-dev.armis.com` | `/knowledge-dev`, `/ask-dev`, `/cwe-fix-dev`, `/framework-guidance-dev`, `/tech-guidance-dev` |
| `armis-knowledge-skills-dev` | shell-skills (maintainers) | `knowledge-api.moose-dev.armis.com` | same commands minus `/ask-dev` |

## Which variant?

- **MCP variant** — works with any MCP-aware client (Claude Code, Claude
  Desktop, Cursor, …). Requires Python on first launch (the bridge
  bootstraps a small venv). Reads `ARMIS_CLIENT_ID` /
  `ARMIS_CLIENT_SECRET` from env.
- **Shell-skills variant** — Claude Code only. No MCP runtime, no Python
  install — pure shell skills that hit the REST API directly via `curl`.
  Reads `ARMIS_CLIENT_ID` / `ARMIS_CLIENT_SECRET` from env (same as the
  MCP variant and `armis-appsec`).

Tool reach favors the MCP variant; install simplicity favors the shell
variant. See [ADR 0003](../../../docs/adr/0003-mcp-vs-skill.md) for the
original MCP-vs-skill split.

## How both variants share the wire

- MCP variant: `bridge.py` + `auth.py` + `run.sh` form a local stdio MCP
  server. The bridge exchanges client credentials for a short-lived JWT
  on startup and forwards every JSON-RPC message to the remote
  streamable-HTTP MCP endpoint with a fresh bearer attached. Tenant
  routing is resolved server-side from the global
  `admin.client_credentials` table — the user only needs `client_id` /
  `client_secret`, not a tenant identifier. Same auth lifecycle as
  [armis-appsec-mcp](https://github.com/ArmisSecurity/armis-appsec-mcp).
- Shell-skills variant: `lib/armis-knowledge.sh` does the same JWT
  exchange directly (`POST /api/v1/auth/token`), caches the token in
  `$TMPDIR` mode-600 for ~55min, and wraps `curl` with the bearer
  header. Each `SKILL.md` sources the lib and calls `ak_get` on a REST
  endpoint.

This bundle contains **no knowledge data**. The data lives server-side
(per-tenant, in S3) and is queried over HTTPS with the user's bearer token.

## Layout

```
plugin/
├── .claude-plugin/marketplace.json   manifest listing all six plugins
├── prod/                             MCP variant, prod (bare slash commands)
│   ├── .mcp.json                     server: armis-knowledge-prod → moose
│   ├── auth.py                       JWT exchange + cache + refresh
│   ├── bridge.py                     stdio↔streamable-HTTP MCP proxy
│   ├── run.sh                        venv bootstrap + entrypoint
│   ├── requirements.txt              mcp, httpx, anyio
│   └── skills/                       SKILL.md files routing to MCP tools
├── stage/                            MCP variant, stage (mirror of prod/, -stage commands)
├── dev/                              MCP variant, dev (mirror of prod/, -dev commands)
├── skills-prod/                      shell-skills variant, prod
│   ├── .claude-plugin/plugin.json
│   ├── lib/armis-knowledge.sh        JWT mint + ak_get / ak_post helpers
│   └── skills/                       SKILL.md files calling ak_get directly
├── skills-stage/                     shell-skills variant, stage (mirror of skills-prod/)
├── skills-dev/                       shell-skills variant, dev (mirror of skills-prod/)
└── README.md
```

## Install (end-user)

The webapp's `/settings/integrations` page renders the up-to-date instructions.
TL;DR — pick either marketplace URL:

```
# canonical
/plugin marketplace add ArmisSecurity/armis-knowledge-mcp

# legacy mirror
/plugin marketplace add silk-security/armis-knowledge-mcp
```

Then install **one** plugin. For Claude Desktop / Cursor / other MCP
clients, install the MCP variant. For Claude-Code-only setups where you'd
rather skip the Python venv, install the shell-skills variant:

```
# MCP variant (prod)
/plugin install armis-knowledge-prod@armis-knowledge

# OR shell-skills variant (Claude Code only)
/plugin install armis-knowledge-skills-prod@armis-knowledge
```

Maintainers pointing at stage or dev swap `-prod` → `-stage` / `-dev` in the
plugin name above. Stage and dev installs use suffixed slash commands
(`/knowledge-stage`, `/knowledge-dev`) so they don't collide with a prod
install on the same machine.

Both URLs serve the same content — every push to `main` of this repo
publishes to both. New installs should use the `ArmisSecurity` URL.

> **Repo name vs marketplace name.** The marketplace is named
> `armis-knowledge` (it now serves both MCP and shell-skills variants),
> but the publish target repo is still `armis-knowledge-mcp` for
> backwards-compat with existing customer installs. The mismatch is
> intentional and harmless — `marketplace add <repo-url>` doesn't care
> what the marketplace itself is named.

### Credentials (both variants)

```bash
export ARMIS_CLIENT_ID='<your-id>'
export ARMIS_CLIENT_SECRET='<your-secret>'
```

The backend resolves your tenant from `client_id` server-side — there's
no separate tenant identifier to set. The same env vars are used by
`armis-appsec`, so a single export covers both.

## Publishing

`apps/mcp/plugin/` is mirrored to **two** public marketplace repos by
[`.github/workflows/publish-plugin.yml`](../../../.github/workflows/publish-plugin.yml)
on every push to `main` that touches the bundle. The matrix fans out so
one target failing (token expired, org policy block) doesn't block the
other. Each leg authenticates differently — ArmisSecurity org policy
blocks classic PATs, so it uses a GitHub App; silk-security still uses
a PAT. Both need `contents: write` on the publish target.

| Target | Auth | Inputs | Notes |
|---|---|---|---|
| [`ArmisSecurity/armis-knowledge-mcp`](https://github.com/ArmisSecurity/armis-knowledge-mcp) | GitHub App | `vars.PLUGIN_PUSH_APP_CLIENT_ID` + `secrets.ARMIS_KNOWLEDGE_MCP_PUBLISHER` (App PEM private key) | Canonical home. App must be installed on the target repo. |
| [`silk-security/armis-knowledge-mcp`](https://github.com/silk-security/armis-knowledge-mcp) | PAT | `secrets.PLUGIN_PUSH_TOKEN_SILK` | Legacy mirror; kept so existing installs keep updating. |

## Local install (without publishing)

If you'd rather skip the published marketplace, point `marketplace add` at the
local path:

```
/plugin marketplace add /Users/<you>/work/armis/armis-knowledge/apps/mcp/plugin
/plugin install armis-knowledge-prod@armis-knowledge
```
