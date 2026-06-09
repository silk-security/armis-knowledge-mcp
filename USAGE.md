# Using Armis Knowledge from your coding agent

Once installed, the plugin gives your agent four slash commands and four skills
that wrap the same backend. The slash command is what *you* type; the skill
description is what your agent reads to decide when to call it on its own.
This page is the operator's cheat sheet — what to type, when each command
fires, and what comes back.

For install + auth setup, see [README.md](README.md). The `-stage` and `-dev`
suffixes in the command names below match the variant you installed.

## At a glance

| Command (stage) | Command (dev) | What it does | Backing call |
|---|---|---|---|
| `/knowledge-stage` | `/knowledge-dev` | Search org standards, list by scope | search / by-scope / get doc |
| `/cwe-fix-stage` | `/cwe-fix-dev` | Org-specific remediation for a CWE | content-pack `cwes` |
| `/framework-guidance-stage` | `/framework-guidance-dev` | Org guidance for a web framework | content-pack `frameworks` |
| `/tech-guidance-stage` | `/tech-guidance-dev` | Org guidance for a language / runtime | content-pack `technologies` |

All four are tenant-scoped server-side — your bearer token determines which
docs you see. There is no `--tenant` flag; the agent never has to pass one.

## When the agent decides on its own

You don't have to type the slash command. Each skill description has triggers
the agent watches for. The intended firing pattern, by skill:

- **knowledge** — fires when you ask "what are our standards for X?", "what
  does our org say about Y?", or whenever the agent is about to write or
  review security-sensitive code. The agent should `list project` first to
  pull project-scope standards, then search for anything not covered.
- **cwe-remediation** — fires when a CWE id appears in the conversation
  ("how do we fix CWE-89?", "is this a real CWE-79?"), or when the agent is
  triaging scanner findings. Surfaces both fix guidance and known
  false-positive patterns.
- **framework-guidance** — fires when the agent is generating or reviewing
  code that uses a known web framework (Django, Flask, FastAPI, Express,
  Rails, Spring, …). "How do we use Django here?" is the canonical phrasing.
- **tech-guidance** — same shape, but for a language or runtime (Python, Go,
  TypeScript, Java, Rust, Node, Ruby, …).

If the agent isn't reaching for a skill you expected, type the slash command
explicitly — that always fires.

## What each command takes and returns

### `/knowledge-<env>` — search and list

```
/knowledge-stage <query>          # full-text search over enabled docs
/knowledge-stage list <scope>     # scope ∈ organization, department, team, project
```

Search returns hits as `{id, title, scope, scope_ref, content_pack, path,
snippet, score}`. The agent fetches the body of any hit it wants to apply.
List returns the standards in that scope without a query.

**Priority order** when multiple standards match: **project > team >
department > organization**. The agent should briefly cite which scope each
applied standard came from so you can audit.

### `/cwe-fix-<env> CWE-<n>` — org remediation for a weakness

```
/cwe-fix-stage CWE-89
```

Returns `{id, title, content_pack, path, body_text}`. The agent reads
`body_text` end-to-end before writing fix code — the org may prescribe a
specific helper, library, or pattern. `404 not_found` means the org has no
doc for that CWE; the agent should say so and fall back to general best
practice.

### `/framework-guidance-<env> <name>` — org guidance for a web framework

```
/framework-guidance-stage django
/framework-guidance-stage flask
/framework-guidance-stage fastapi
/framework-guidance-stage express
/framework-guidance-stage rails
/framework-guidance-stage spring
```

Use the canonical lowercase name. If guidance contradicts a pattern in the
existing codebase, the agent should surface the conflict — not silently
override.

### `/tech-guidance-<env> <name>` — org guidance for a language / runtime

```
/tech-guidance-stage python
/tech-guidance-stage go
/tech-guidance-stage typescript
/tech-guidance-stage javascript
/tech-guidance-stage java
/tech-guidance-stage rust
/tech-guidance-stage ruby
```

Same conflict-surfacing rule.

## Recipes

**Pre-flight before writing security-sensitive code.** Pull project-scope
standards before the first edit so the agent applies them as it goes.

```
/knowledge-stage list project
```

**Triaging a scanner finding.** Get the org's take on the CWE before
deciding whether the finding is actionable.

```
/cwe-fix-stage CWE-89
```

**Starting work in a new framework.** Pull both the language and the
framework guidance up front.

```
/tech-guidance-stage python
/framework-guidance-stage django
```

**Searching for a specific policy.** Free text — the search is full-text
over enabled docs.

```
/knowledge-stage password rotation
/knowledge-stage retention for audit logs
```

## Verifying it's working

The smoke test is `list project`. If you get back the project-scope
standards for your tenant, auth is good and the bundle is wired up:

```
/knowledge-stage list project
```

Or, from the shell:

```
claude --debug "use the armis-knowledge tool to list standards in scope project"
```

## When something is off

- **The agent isn't using these skills.** Type the slash command explicitly
  to confirm the bundle is installed; if the slash command works but the
  agent isn't picking it up on its own, the trigger phrasing in your prompt
  may not match the skill descriptions. The triggers above are the ones
  baked into each skill's frontmatter.
- **`401 invalid_client_credentials`** — the secret was rotated. Re-issue
  from the webapp's `/settings/integrations` page and update the keychain
  entry (shell-skills variant) or env (MCP variant).
- **`401 missing_bearer_token`** — env vars not exported. See README.md for
  the exact var names per variant.
- **`404 tenant_not_found`** — slug typo, or the tenant isn't provisioned in
  that environment. Stage and dev are separate; a slug that works in one may
  not exist in the other.
- **`404 not_found` from a content-pack call** — the org has no doc for that
  CWE / framework / language. Not an error; the agent should say so and use
  general best practice.

## Where the data lives

Nothing in this plugin contains knowledge data — the bundle ships only
glue. The actual docs live server-side in S3 under per-tenant prefixes,
and every call is authenticated with a short-lived JWT minted from your
client credentials. Editing happens in the webapp at
`knowledge.moose-stg.armis.com` (or `knowledge.moose-dev.armis.com` for
the dev backend).
