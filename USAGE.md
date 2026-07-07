# Using Armis Knowledge from your coding agent

Once installed, the plugin gives your agent six slash commands and six
skills that wrap the same backend (the `/ask` skill is MCP-variant only).
The slash command is what *you* type; the skill description is what your
agent reads to decide when to call it on its own. This page is the operator's
cheat sheet — what to type, when each command fires, and what comes back.

For install + auth setup, see [README.md](README.md). The prod variants
register the unsuffixed commands below. Stage and dev variants register the
same commands with a `-stage` / `-dev` suffix (`/knowledge-stage`,
`/cwe-fix-dev`, …) so all three can be installed side-by-side without
colliding.

## At a glance

| Command (prod) | Command (stage) | Command (dev) | What it does | Backing call |
|---|---|---|---|---|
| `/knowledge` | `/knowledge-stage` | `/knowledge-dev` | Search org standards, list by scope | search / by-scope / get doc |
| `/cwe-fix` | `/cwe-fix-stage` | `/cwe-fix-dev` | Org-specific remediation for a CWE | content-pack `cwes` |
| `/cwe-fix-report` | `/cwe-fix-report-stage` | `/cwe-fix-report-dev` | Report a CWE-fix batch (before/after), optionally open a PR or emit a diff | local `git diff` + scanner → server assembles |
| `/framework-guidance` | `/framework-guidance-stage` | `/framework-guidance-dev` | Org guidance for a web framework | content-pack `frameworks` |
| `/tech-guidance` | `/tech-guidance-stage` | `/tech-guidance-dev` | Org guidance for a language / runtime | content-pack `technologies` |
| `/ask` (MCP only) | `/ask-stage` (MCP only) | `/ask-dev` (MCP only) | Free-form Q&A; agent loop returns prose | server-side ask agent |

All commands are tenant-scoped server-side — your bearer token determines which
docs you see. There is no `--tenant` flag; the agent never has to pass one.

## When the agent decides on its own

You don't have to type the slash command. Each skill description has triggers
the agent watches for. The intended firing pattern, by skill:

- **knowledge** — fires when you ask "what are our standards for X?", "what
  does our org say about Y?", or whenever the agent is about to write or
  review security-sensitive code. The agent should `list project` first to
  pull project-scope standards, then search for anything not covered.
- **cwe-fix** — fires when a CWE id appears in the conversation ("how do we
  fix CWE-89?", "is this a real CWE-79?"), or when the agent is triaging
  scanner findings. Surfaces both fix guidance and known false-positive
  patterns.
- **cwe-fix-report** — fires *after* a batch of CWE fixes is done, when the
  user says "report the fixes," "generate a diff summary," or "open a PR with
  these fixes." Never mid-fix. Collects the before/after scanner findings for
  the changed files, sends them to the backend, and emits the report the
  server returns — to stdout, as a `gh pr create` body, or as a diff-only view.
- **framework-guidance** — fires when the agent is generating or reviewing
  code that uses a known web framework (Django, Flask, FastAPI, Express,
  Rails, Spring, …). "How do we use Django here?" is the canonical phrasing.
- **tech-guidance** — same shape, but for a language or runtime (Python, Go,
  TypeScript, Java, Rust, Node, Ruby, …).
- **ask** (MCP only) — fires on Q&A phrasing: "ask the knowledge base about
  X", "summarize what we have on Y". Returns synthesized prose with citations.

If the agent isn't reaching for a skill you expected, type the slash command
explicitly — that always fires.

## What each command takes and returns

Examples below use the prod commands. Maintainers on the `-stage` / `-dev`
variants should append the appropriate suffix to each command name.

### `/knowledge` — search and list

```
/knowledge <query>          # full-text search over enabled docs
/knowledge list <scope>     # scope ∈ organization, department, team, project
```

Search returns hits as `{id, title, scope, scope_ref, content_pack, path,
snippet, score}`. The agent fetches the body of any hit it wants to apply.
List returns the standards in that scope without a query.

Results come back already ordered by priority — apply them top-down. The
agent should briefly cite which scope each applied standard came from so you
can audit.

### `/cwe-fix CWE-<n>` — org remediation for a weakness

```
/cwe-fix CWE-89
```

Returns `{id, title, content_pack, path, body_text}`. The agent reads
`body_text` end-to-end before writing fix code — the org may prescribe a
specific helper, library, or pattern. `404 not_found` means the org has no
doc for that CWE; the agent should say so and fall back to general best
practice.

### `/cwe-fix-report` — report a CWE-fix batch, optionally open a PR

```
/cwe-fix-report                    # full stdout report
/cwe-fix-report --pr               # also open a GitHub PR with the report as body
/cwe-fix-report --diff             # diff-only view (git diff + before/after scanner)
/cwe-fix-report --base develop     # override baseline (default: origin/main)
```

Runs *after* a fix batch — never mid-fix. The skill collects the before/after
scanner findings for the changed files (baselining the pre-fix state via git)
and sends them to the backend, which assembles the finished report and returns
it as markdown.

**Flags.** `--pr` additionally runs `gh pr create` with the server's condensed
PR body (the fix table stays in stdout). `--diff` emits the diff-only view. The
two flags compose: `--pr --diff` puts the diff-only view on stdout but still
opens the PR with the normal body.

**Baseline.** Defaults to `origin/main`; override with `--base <branch>`.
If git shows no commits ahead of the base, the skill falls back to unstaged
changes and warns that the "initial findings" were captured from the
pre-edit working tree.

### `/framework-guidance <name>` — org guidance for a web framework

```
/framework-guidance django
/framework-guidance flask
/framework-guidance fastapi
/framework-guidance express
/framework-guidance rails
/framework-guidance spring
```

Use the canonical lowercase name. If guidance contradicts a pattern in the
existing codebase, the agent should surface the conflict — not silently
override.

### `/tech-guidance <name>` — org guidance for a language / runtime

```
/tech-guidance python
/tech-guidance go
/tech-guidance typescript
/tech-guidance javascript
/tech-guidance java
/tech-guidance rust
/tech-guidance ruby
```

Same conflict-surfacing rule.

### `/ask <question>` — free-form Q&A (MCP variant only)

```
/ask what does our retention policy say about audit logs?
```

Server-side agent loop. Returns synthesized prose plus the search/lookup
calls it ran (cite these so the user can audit). Not in the shell-skills
variant — the agent loop runs on the MCP server.

## Recipes

**Pre-flight before writing security-sensitive code.** Pull project-scope
standards before the first edit so the agent applies them as it goes.

```
/knowledge list project
```

**Triaging a scanner finding.** Get the org's take on the CWE before
deciding whether the finding is actionable.

```
/cwe-fix CWE-89
```

**Reporting a CWE-fix batch.** After a round of fixes, produce a structured
before/after report — optionally open the PR in the same step.

```
/cwe-fix-report            # review locally first
/cwe-fix-report --pr       # once you're happy, ship the PR
```

**Starting work in a new framework.** Pull both the language and the
framework guidance up front.

```
/tech-guidance python
/framework-guidance django
```

**Searching for a specific policy.** Free text — the search is full-text
over enabled docs.

```
/knowledge password rotation
/knowledge retention for audit logs
```

## Verifying it's working

The smoke test is `list project`. If you get back the project-scope
standards for your tenant, auth is good and the bundle is wired up:

```
/knowledge list project
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
  from the webapp's `/settings/integrations` page and re-export
  `ARMIS_CLIENT_SECRET`.
- **`401 missing_bearer_token`** — env vars not exported. Set
  `ARMIS_CLIENT_ID` and `ARMIS_CLIENT_SECRET` in your shell rc.
- **`404 tenant_not_found`** — slug typo, or the tenant isn't provisioned in
  that environment. Prod, stage, and dev are separate; a slug that works in
  one may not exist in another.
- **`404 not_found` from a content-pack call** — the org has no doc for that
  CWE / framework / language. Not an error; the agent should say so and use
  general best practice.

## Where the data lives

Nothing in this plugin contains knowledge data — the bundle ships only
glue. The actual docs live server-side, isolated per tenant, and every call
is authenticated with a short-lived JWT minted from your client credentials.
Editing happens in the webapp at
`knowledge.moose.armis.com` (or `knowledge.moose-stg.armis.com` /
`knowledge.moose-dev.armis.com` for the non-prod backends).
