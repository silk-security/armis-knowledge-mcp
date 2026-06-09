# Armis Knowledge — Claude Code plugin bundle

Claude Code marketplace that ships **two variants** of the Armis Knowledge
client — an MCP variant and a shell-skills variant — for each environment.
Pick the variant that fits your tooling; don't install both for the same
environment because they register the same slash commands.

> **Already installed?** [USAGE.md](USAGE.md) is the operator cheat sheet for
> the four slash commands and the triggers that fire each skill on its own.

> **Use the `-stage` plugins.** Stage runs on `moose-stg.armis.com` and is
> the env everyone hits today. The `-dev` plugins are for maintainers
> only — they point at `moose-dev.armis.com`, which is not multi-user. A
> `-prod` variant will be added once MooseProd is live.

| Plugin | Variant | Backend | Slash commands |
|---|---|---|---|
| `armis-knowledge-stage` | MCP | `knowledge-mcp.moose-stg.armis.com` | `/knowledge`, `/cwe-fix`, `/framework-guidance`, `/tech-guidance` |
| `armis-knowledge-skills-stage` | shell-skills | `knowledge-api.moose-stg.armis.com` | same as MCP stage variant |
| `armis-knowledge-dev` | MCP (maintainers) | `knowledge-mcp.moose-dev.armis.com` | `/knowledge-dev`, `/cwe-fix-dev`, `/framework-guidance-dev`, `/tech-guidance-dev` |
| `armis-knowledge-skills-dev` | shell-skills (maintainers) | `knowledge-api.moose-dev.armis.com` | same as MCP dev variant |

## Which variant?

- **MCP variant** — works with any MCP-aware client (Claude Code, Claude
  Desktop, Cursor, …). Requires Python on first launch (the bridge
  bootstraps a small venv). Reads `ARMIS_CLIENT_ID` /
  `ARMIS_CLIENT_SECRET` / `ARMIS_TENANT_ID` from env.
- **Shell-skills variant** — Claude Code only. No MCP runtime, no Python
  install — pure shell skills that hit the REST API directly via `curl`.
  Reads `ARMIS_KNOWLEDGE_CLIENT_ID` / `ARMIS_KNOWLEDGE_TENANT_SLUG` from
  env; loads `client_secret` from the OS keychain (`security` on macOS,
  `secret-tool` on Linux), so the secret never lives in a shell rc.

Tool reach favors the MCP variant; install simplicity and tighter
secret-storage favor the shell variant. See [ADR 0003](../../../docs/adr/0003-mcp-vs-skill.md)
for the original MCP-vs-skill split.

## How both variants share the wire

- MCP variant: `bridge.py` + `auth.py` + `run.sh` form a local stdio MCP
  server. The bridge exchanges client credentials + tenant identifier
  (`ARMIS_TENANT_ID` or `ARMIS_TENANT_SLUG`) for a short-lived JWT on
  startup and forwards every JSON-RPC message to the remote
  streamable-HTTP MCP endpoint with a fresh bearer attached. Same auth
  lifecycle as [armis-appsec-mcp](https://github.com/ArmisSecurity/armis-appsec-mcp).
- Shell-skills variant: `lib/armis-knowledge.sh` does the same JWT
  exchange directly (`POST /api/v1/auth/token`), caches the token in
  `$TMPDIR` mode-600 for ~55min, and wraps `curl` with the bearer
  header. Each `SKILL.md` sources the lib and calls `ak_get` on a REST
  endpoint.

This bundle contains **no knowledge data**. The data lives server-side
(per-tenant, in S3) and is queried over HTTPS with the user's bearer token.

> **Prod note:** there is no prod variant yet. Stage on `moose-stg` is what
> everyone uses today. A prod variant will be added the same way once
> MooseProd is up.

## Layout

```
plugin/
├── .claude-plugin/marketplace.json   manifest listing all four plugins
├── dev/                              MCP variant, dev
│   ├── .mcp.json                     server: armis-knowledge-dev → moose-dev
│   ├── auth.py                       JWT exchange + cache + refresh
│   ├── bridge.py                     stdio↔streamable-HTTP MCP proxy
│   ├── run.sh                        venv bootstrap + entrypoint
│   ├── requirements.txt              mcp, httpx, anyio
│   └── skills/                       SKILL.md files routing to MCP tools
├── stage/                            MCP variant, stage (mirror of dev/)
├── skills-dev/                       shell-skills variant, dev
│   ├── .claude-plugin/plugin.json
│   ├── lib/armis-knowledge.sh        JWT mint + ak_get / ak_post helpers
│   └── skills/                       SKILL.md files calling ak_get directly
├── skills-stage/                     shell-skills variant, stage (mirror of skills-dev/)
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
# MCP variant
/plugin install armis-knowledge-stage@armis-knowledge

# OR shell-skills variant (Claude Code only)
/plugin install armis-knowledge-skills-stage@armis-knowledge
```

Maintainers pointing at the dev backend swap `-stage` → `-dev` in the
plugin name above.

Both URLs serve the same content — every push to `main` of this repo
publishes to both. New installs should use the `ArmisSecurity` URL.

> **Repo name vs marketplace name.** The marketplace is named
> `armis-knowledge` (it now serves both MCP and shell-skills variants),
> but the publish target repo is still `armis-knowledge-mcp` for
> backwards-compat with existing customer installs. The mismatch is
> intentional and harmless — `marketplace add <repo-url>` doesn't care
> what the marketplace itself is named.

### MCP variant — env

```bash
export ARMIS_CLIENT_ID='<your-id>'
export ARMIS_CLIENT_SECRET='<your-secret>'
# Prefer ARMIS_TENANT_ID — same Moose tenant id as armis-cli / armis-appsec.
export ARMIS_TENANT_ID='<your-moose-tenant-id>'
# Legacy: export ARMIS_TENANT_SLUG='<your-tenant>'
```

### Shell-skills variant — env + keychain

```bash
export ARMIS_KNOWLEDGE_CLIENT_ID='<your-id>'
export ARMIS_KNOWLEDGE_TENANT_SLUG='<your-tenant>'

# Store the secret once in the OS keychain (don't put it in your shell rc):
# macOS:
security add-generic-password -s armis-knowledge-stage -a "$ARMIS_KNOWLEDGE_CLIENT_ID" -w
# Linux:
secret-tool store --label='Armis Knowledge stage' service armis-knowledge-stage account "$ARMIS_KNOWLEDGE_CLIENT_ID"
```

Maintainers using the dev variant: keychain service is `armis-knowledge-dev`
instead of `armis-knowledge-stage`.

## Publishing

`apps/mcp/plugin/` is mirrored to **two** public marketplace repos by
[`.github/workflows/publish-plugin.yml`](../../../.github/workflows/publish-plugin.yml)
on every push to `main` that touches the bundle. The matrix fans out so
one target failing (token expired, org policy block) doesn't block the
other. Each leg needs its own repo secret with `contents: write`:

| Target | Secret | Notes |
|---|---|---|
| [`ArmisSecurity/armis-knowledge-mcp`](https://github.com/ArmisSecurity/armis-knowledge-mcp) | `PLUGIN_PUSH_TOKEN_ARMIS` | Canonical home. ArmisSecurity org blocks classic PATs — use a fine-grained PAT or GitHub App. |
| [`silk-security/armis-knowledge-mcp`](https://github.com/silk-security/armis-knowledge-mcp) | `PLUGIN_PUSH_TOKEN_SILK` | Legacy mirror; kept so existing installs keep updating. |

## Local install (without publishing)

If you'd rather skip the published marketplace, point `marketplace add` at the
local path:

```
/plugin marketplace add /Users/<you>/work/armis/armis-knowledge/apps/mcp/plugin
/plugin install armis-knowledge-stage@armis-knowledge
```
