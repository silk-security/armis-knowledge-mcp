---
name: cwe-fix-report-stage
description: "Produce a structured before/after report after a CWE-fix run against the Armis Knowledge STAGE environment (shell-skills variant). You collect git + scanner findings; the backend assembles the report and returns finished markdown. Optionally opens a PR. Use after finishing a batch of CWE fixes when the user asks for a report / diff / PR body. Triggers: /cwe-fix-report-stage, generate cwe fix report, report the fixes, cwe report, open a pr for the fixes."
allowed-tools:
  - Bash(curl *)
  - Bash(jq *)
  - Bash(source *)
  - Bash(git *)
  - Bash(gh *)
---

# /cwe-fix-report-stage

Emit a structured markdown report summarizing a CWE-fix run — before/after findings per file, standards applied, residuals, notes — and optionally open a GitHub PR.

## When to use

- The user has just finished fixing scanner findings (typically via the CWE-fix skill) and wants a summary of what changed.
- Triggers include "report the fixes," "generate a diff summary," "open a PR with these fixes."
- Do NOT trigger this yourself mid-fix — only after edits are done.

## Inputs

- `--pr` (or "open a PR with these fixes") — also invoke the GitHub PR-create command at the end.
- `--base <branch>` — the pre-fix baseline branch (default: `origin/main`).
- `--diff` (or "just show me the diff") — show the diff-only view instead of the full report. Compatible with `--pr`.
- No arguments — print the full report to stdout only.

## How it works

You collect the raw materials locally; the backend builds the report. You do not
assemble the fix table, attribute standards, or compute the summary — the
`/api/knowledge/cwe-fix-report/assemble` endpoint does all of that and returns
finished markdown.

### 1. Collect before/after findings

- Get the changed-file list via `git diff --name-only <base>...` (base defaults to `origin/main`, or `--base`).
- For each changed file, capture the scanner findings on the **pre-fix** version. Preferred: ask the user to paste (or point at a file with) the pre-fix scan output. Fallback: run whichever scanner CLI the user has installed against the pre-fix version (`git show <base>:<path>` to a temp file, or stash + scan + restore).
- Run the same scanner CLI against the current working-tree state of each file for the post-fix findings.
- If a file scan errors, pass `scan_failed: true` for that file rather than aborting.

### 2. Assemble the report

Source the helper and POST the findings:

```bash
source "$CLAUDE_PLUGIN_ROOT/lib/armis-knowledge.sh"
TENANT_ID=$(ak_tenant_id)

ak_post /api/knowledge/cwe-fix-report/assemble "$(jq -n \
  --arg tid "$TENANT_ID" \
  --arg label "$(date +%F)" \
  --arg base "origin/main" \
  --argjson files "$FILES_JSON" \
  '{tenant_id: $tid, run_label: $label, base: $base, files: $files}')"
```

`$FILES_JSON` is a JSON array, one object per changed file:
`{path, initial_findings: ["CWE-89", ...], final_findings: [...], language?, scan_failed?}`.
CWE ids may be `CWE-89` or bare `89`. The response is
`{report_markdown, pr_body_markdown, diff_view_markdown, summary}`.

### 3. Emit

- Default: print `.report_markdown`.
- `--diff`: print `.diff_view_markdown`.
- `--pr`: additionally write `.pr_body_markdown` to a tempfile and run the GitHub
  CLI's PR-create command with a title like "fix(cwe): batch remediation — <N>
  findings closed". On failure, print the intended body and the exact command for
  the user to run manually. `--pr --diff` prints the diff view to stdout but still
  opens the PR with `.pr_body_markdown`.

## Notes

- **Residuals.** The report lists each residual (file + CWE). If you know *why* a
  residual survived (WAF-layer concern, out of scope, apparent FP, downstream dep
  missing), add that when you present the report — it's the most useful part.
- **Baseline detection.** If the git diff against the base returns nothing (no
  commits ahead), fall back to unstaged changes and warn the user that "initial
  findings" was captured from the pre-edit working tree.
