# Armis Knowledge — Claude Code plugin bundle

Claude Code marketplace that ships **two plugins** — one for each environment of
the Armis Knowledge MCP server — so a single agent session can talk to dev and
stage independently:

| Plugin | Backend | Slash commands | Token env |
|---|---|---|---|
| `armis-knowledge-dev` | `knowledge-mcp.moose-dev.armis.com` | `/knowledge-dev`, `/cwe-fix-dev`, `/framework-guidance-dev`, `/tech-guidance-dev` | `ARMIS_KNOWLEDGE_TOKEN_DEV` |
| `armis-knowledge-stage` | `knowledge-mcp.moose-stg.armis.com` | `/knowledge-stage`, `/cwe-fix-stage`, `/framework-guidance-stage`, `/tech-guidance-stage` | `ARMIS_KNOWLEDGE_TOKEN_STAGE` |

The plugins use distinct MCP server names (`armis-knowledge-dev` vs
`armis-knowledge-stage`), so installing both produces two separate tool
namespaces (`mcp__armis_knowledge_dev__*` and `mcp__armis_knowledge_stage__*`)
that can be called in the same conversation.

This bundle contains **no knowledge data**. The data lives server-side
(per-tenant, in S3) and is queried over HTTPS with the user's bearer token.
That's the whole reason the plugin replaces the
[knowledge_driven](https://github.com/andrewgrealy/knowledge_driven) POC's
`~/.claude/skills/knowledge/` setup — see [ADR 0003](../../../docs/adr/0003-mcp-vs-skill.md).

> **Prod note:** stage is scaffolded ahead of the stage MCP being live; until
> `knowledge-mcp.moose-stg.armis.com` resolves, `/knowledge-stage` etc. will
> return connection errors. A prod variant will be added the same way once
> MooseProd is up.

## Layout

```
plugin/
├── .claude-plugin/marketplace.json   manifest listing both plugins
├── dev/
│   ├── .mcp.json                     server: armis-knowledge-dev → moose-dev
│   └── skills/                       /knowledge-dev, /cwe-fix-dev, …
│       ├── knowledge/SKILL.md
│       ├── cwe-remediation/SKILL.md
│       ├── framework-guidance/SKILL.md
│       └── tech-guidance/SKILL.md
├── stage/
│   ├── .mcp.json                     server: armis-knowledge-stage → moose-stg
│   └── skills/                       /knowledge-stage, /cwe-fix-stage, …
│       ├── knowledge/SKILL.md
│       ├── cwe-remediation/SKILL.md
│       ├── framework-guidance/SKILL.md
│       └── tech-guidance/SKILL.md
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

Then install the plugins:

```
/plugin install armis-knowledge-dev@armis-knowledge-mcp
/plugin install armis-knowledge-stage@armis-knowledge-mcp   # optional
```

Both URLs serve the same content — every push to `main` of this repo
publishes to both. New installs should use the `ArmisSecurity` URL.

…then export the token(s) you need (one-hour JWTs, exchanged from
`client_id` / `client_secret` per the integrations page):

```bash
export ARMIS_KNOWLEDGE_TOKEN_DEV=...
export ARMIS_KNOWLEDGE_TOKEN_STAGE=...
```

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
/plugin install armis-knowledge-dev@armis-knowledge-mcp
```
