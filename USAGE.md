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
- **check_code** (agent-invoked; no slash command) — the agent calls this on
  its own when it wants to verify code against your tenant's standards. Fires
  on phrases like "check this code," "does this follow our standards,"
  "verify my diff." Returns per-standard verdicts (`violation`, `compliant`,
  `not_applicable`, or `uncertain`) with citations back to the source
  standard. See [check_code section below](#check_code--verify-code-against-your-standards)
  for details.
- **check_knowledge_coverage** (agent-invoked; no slash command) — the
  agent calls this after a scan produces CWE findings and before applying
  fixes. Given the list of unique CWEs from the scan, returns per-CWE
  coverage: which CWEs your tenant has Knowledge docs for and which will
  fall back to industry-standard fix guidance. The agent emits a one-line
  coverage summary to you before touching code (*"7/9 CWEs covered by
  Knowledge; falling back to industry-standard fixes for CWE-434, CWE-918"*)
  and passes the coverage report to `export_findings_report` so the
  artifact carries the same breakdown.
- **export_findings_report** (agent-invoked; no slash command) — the agent
  calls this when you ask for a report artifact — "give me a SARIF file,"
  "output as CSV," "human-readable summary." Turns any findings list (from
  `check_code`, the Armis AppSec scanner, or a mix) into a downloadable
  JSON / CSV / SARIF / Markdown report. Accepts an optional
  `knowledge_coverage` field from `check_knowledge_coverage` and surfaces
  it in every format.

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

### `check_code` — verify code against your standards

Agent-invoked; no slash command. The agent calls it on its own when you
ask it to check code — "does this follow our standards," "check my
diff," "verify this snippet against our policies." Available in the MCP
variant only.

Input:

```
check_code(
  code:          str,   # required — the source snippet to verify
  language:      str,   # optional — python / typescript / go / any / …
  standard_ids:  list,  # optional — scope to specific requirements or docs
)
```

Returns per-standard verdicts:

```
{
  "checked": [
    {
      "source":       "requirement" | "document",   // tier 1 vs tier 2
      "confidence":   "high" | "medium" | "low",
      "standard_id":  "ARM-DATA-PATH-001",
      "verdict":      "violation" | "compliant" | "not_applicable" | "uncertain",
      "line_hint":    12,
      "evidence":     "…",
      "recommended_fix": "…",
      "citation":     "cwes/remediation/CWE-22.md"
    }
  ],
  "coverage": { "state": "empty" | "checked" | "no_applicable_content", … },
  "elapsed_ms": 8340
}
```

Two paths behind one interface. **Tier 1** (requirement-backed) uses
your tenant's machine-checkable requirements with structured
`bad_example` / `good_example` anchors — high confidence. **Tier 2**
(document-backed) reads your raw content-pack documents when no formal
requirement applies — medium confidence, honest hedging via the
`uncertain` verdict.

Coverage states signal what actually ran:

| state | meaning |
|---|---|
| `empty` | Tenant has no standards yet — configure some to enable checks. |
| `no_applicable_content` | You have standards, but none apply to this code's language / context. |
| `checked` | The pipeline ran; `checked[]` populated. |

Nothing is persisted; check_code is read-only. Verdicts are best-effort;
`uncertain` means the model can't decide confidently — treat those as
concerns to review, not judgments.

### `check_knowledge_coverage` — which CWEs does your Knowledge cover?

Agent-invoked; no slash command. The agent calls it after a scan produces
CWE findings and before applying fixes. Answers a question no other tool
does: *"which of these CWEs does my tenant have authoritative Knowledge
for, and which will fall back to industry-standard fixes?"*

Input:

```
check_knowledge_coverage(
  cwes:  list[str],   # required — CWE ids (CWE-89, cwe_89, 89 all work)
  pack:  str,         # optional — content pack; default "cwes/remediation"
)
```

Returns:

```
{
  "checked": [
    {"cwe": "CWE-89",  "covered": true,  "doc_path": "cwes/remediation/CWE-89.md"},
    {"cwe": "CWE-434", "covered": false, "doc_path": null}
  ],
  "covered":     ["CWE-89", "CWE-22"],
  "not_covered": ["CWE-434", "CWE-918"],
  "summary":     {"total": 4, "covered": 2, "not_covered": 2}
}
```

**Why it matters.** Before this tool, you had no deterministic way to
know which of a scan's CWEs your Knowledge would drive vs which the
agent would silently fall back on. Now the agent tells you up front, and
the coverage picture also becomes an authoring priority signal — CWEs
that appear in real scan findings but aren't in Knowledge yet are the
highest-value docs to add next.

Duplicates and non-canonical forms are normalized silently. Unparseable
inputs are dropped. Max 200 CWEs per call.

### `export_findings_report` — format findings as JSON / CSV / SARIF / Markdown

Agent-invoked; no slash command. The agent calls it when you ask for a
report artifact — "give me a SARIF file," "export as CSV," "human
summary." Available in the MCP variant only.

Input:

```
export_findings_report(
  findings:            list,   # required — from check_code, AppSec, or a mix
  format:              str,    # "json" | "csv" | "sarif" | "human"; default "human"
  title:               str,    # optional — appears in the report header
  run_label:           str,    # optional — commit SHA, PR number, work item id
  base_ref:            str,    # optional — git ref the findings were computed against
  include_body:        bool,   # default true; false = summary counts only
  knowledge_coverage:  dict,   # optional — pass the check_knowledge_coverage
                               # response verbatim; surfaces in every format
)
```

Returns:

```
{
  "report":            "<serialized string>",
  "suggested_filename": "armis-findings-2026-07-21T15-04-11Z.sarif",
  "mime_type":         "application/sarif+json",
  "byte_count":        8421,
  "summary":           { "total": 12, "by_verdict": {…}, "by_severity": {…}, "by_source": {…} }
}
```

Format guide:

| format | Best for |
|---|---|
| `json` | Scripting, jq pipelines, custom internal tooling. Full-fidelity envelope. |
| `csv` | Spreadsheet review, ticket-import (Jira / ServiceNow), audit deliverables. UTF-8 BOM so Excel opens cleanly. |
| `sarif` | GitHub / GitLab code-scanning, VS Code SARIF viewer, SAST aggregators. Conforms to SARIF 2.1.0. Uploadable via `github/codeql-action/upload-sarif`. |
| `human` | Terminal viewing, chat responses, weekly reports. Markdown with severity sigils and citation links. |

The tool does NOT write files, does NOT open PRs, and does NOT persist
the report server-side. The caller (typically the agent) writes the
returned `report` string wherever you want it — a local file, a PR
comment, a chat message, an artifact upload.

Accepts findings from either Knowledge `check_code` shape or Armis
AppSec scanner shape (or a mix); the formatter normalizes internally.
Findings with `has_secret: true` have their evidence redacted before
the report body is generated.

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

**End-to-end: build → scan → remediate → report.** The agent orchestrates
all four steps in a single chat. Type a natural-language request:

```
Build a FastAPI endpoint for payments following our standards.
Then scan it, remediate any findings using our knowledge base,
and give me a SARIF report I can upload to GitHub code-scanning.
```

The agent walks these tools in order, on its own:

1. `list_standards`, `get_framework_guidance`, `search_knowledge` — pulls
   your team's applicable standards
2. Writes the code following those standards, citing which doc drove each
   decision
3. Calls the Armis AppSec scanner tool to find CWE-level issues in what it
   just wrote
4. Calls `check_knowledge_coverage` with the unique CWEs from the scan
   — batch check for which CWEs your tenant has Knowledge for. The
   agent emits a one-line coverage summary to you before touching code:
   *"Coverage: 7/9 CWEs covered by Knowledge. Falling back to
   industry-standard fixes for CWE-434 and CWE-918."*
5. For each finding: calls `get_cwe_remediation` — applies your tenant's
   pattern for covered CWEs, falls back to AppSec's default otherwise
6. Optionally re-runs `check_code` on the fixed code to verify it now
   passes your machine-checkable requirements
7. Calls `export_findings_report` with `format="sarif"` and the coverage
   report from step 4 — hands you back the file to save or upload,
   with the coverage breakdown surfaced in the report

Swap `format="sarif"` for `csv` (for compliance officers), `json` (for
scripting), or `human` (for a chat-native summary) based on what you'll
do with the report next.

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
