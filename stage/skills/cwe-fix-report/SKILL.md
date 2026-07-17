---
name: cwe-fix-report-stage
description: "Produce a structured before/after report after a CWE-fix run against the Armis Knowledge STAGE environment. You collect the scanner findings; the server assembles the report — attribution, summary, residuals — and returns finished markdown. Optionally opens a PR. Use after finishing a batch of CWE fixes when the user asks for a report / diff / PR body. Triggers: /cwe-fix-report-stage, generate cwe fix report, report the fixes, cwe report, open a pr for the fixes."
---

# /cwe-fix-report-stage

Emit a structured markdown report summarizing a CWE-fix run — before/after findings per file, standards applied, residuals, notes — and optionally open a GitHub PR with the same content.

## When to use

- The user has just finished fixing scanner findings (typically via the CWE-fix skill) and wants to see a summary of what changed.
- The user says "report the fixes," "generate a diff summary," "open a PR with these fixes," or similar.
- Do NOT trigger this yourself mid-fix — only after edits are done and the working tree is stable.

## Inputs

- `--pr` (or "open a PR with these fixes") — also open a GitHub PR at the end.
- `--base <branch>` — the pre-fix baseline branch (default: `origin/main`).
- `--diff` (or "just show me the diff") — show the diff-only view instead of the full report. Compatible with `--pr`.
- No arguments — print the full report to stdout only.
- `--check-first` (or "check the code before running the report") — run `check_code` against each changed file BEFORE assembling the report. The results (violations flagged by the tenant's standards) are included in the report as a new "Pre-fix compliance check" section. Compatible with `--pr` and `--diff`. Requires the tenant to have machine-checkable standards (formal requirements or CWE / framework / technology guidance docs); a tenant with none returns an empty check section and continues with the normal report.

## How it works

You collect the raw materials locally; the server builds the report. You do not
assemble the fix table, attribute standards to CWEs, or compute the summary —
`mcp__armis_knowledge_stage__assemble_cwe_fix_report` does all of that and returns
finished markdown.

### 1. Collect before/after findings

- List the files changed against the base branch (`git diff --name-only <base>...`; base defaults to `origin/main`, or `--base`).
- For each changed file, capture the scanner findings on the **pre-fix** version: stash local edits, run the Armis appsec scanner's per-file scan, then restore the stash. If commits already exist on the branch, `git show <base>:<path>` to a temp file and scan that.
- Run the scanner again on each file **as it sits now** for the post-fix findings.
- If a file scan errors, pass `scan_failed: true` for that file rather than aborting the whole report.

### 2. Assemble the report

Call `mcp__armis_knowledge_stage__assemble_cwe_fix_report` with one entry per
changed file:

```
assemble_cwe_fix_report(
  files=[
    {path, initial_findings: [CWE ids], final_findings: [CWE ids],
     language?, scan_failed?},
    ...
  ],
  run_label="<YYYY-MM-DD or run label>",
  base="<base branch>",
)
```

CWE ids may be `CWE-89` or bare `89`. It returns
`{report_markdown, pr_body_markdown, diff_view_markdown, summary}`.


### 2b. If `--check-first`: verify code against tenant standards

Before emitting, for each file in the working tree, call the `check_code`
MCP tool with the file's post-fix content and the file's language. The
tool returns per-standard verdicts drawn from the tenant's own
requirements and content-pack documents. Bucket the verdicts by verdict
type (`violation`, `uncertain`, `compliant`, `not_applicable`) and hand
them to the report as a "Pre-fix compliance check" section.

If the tenant has no standards (`coverage.state = "empty"`) or nothing
applies (`coverage.state = "no_applicable_content"`), skip the section
quietly — the customer still gets the standard report.

`--check-first` is compatible with `--pr` and `--diff`.

### 3. Emit

- Default: print `report_markdown`.
- `--diff`: print `diff_view_markdown`.
- `--pr`: additionally run the GitHub CLI's PR-create command with a title like
  "fix(cwe): batch remediation — <N> findings closed" and `pr_body_markdown`
  written to a tempfile. If the CLI fails, print the intended body and the exact
  command the user can run manually. `--pr --diff` prints the diff view to
  stdout but still opens the PR with `pr_body_markdown`.

## Notes

- **Residuals.** The report lists each residual (file + CWE). If you know *why* a
  given residual survived (WAF-layer concern, out of scope, apparent FP,
  downstream dep missing), add that context when you present the report — it's
  the most useful part for the user.
- **Baseline detection.** If the git diff against the base returns nothing (no
  commits ahead), fall back to unstaged changes and warn the user that "initial
  findings" was captured from the working-tree state before your edits.
