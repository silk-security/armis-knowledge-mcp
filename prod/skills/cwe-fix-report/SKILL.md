---
name: cwe-fix-report
description: "Produce a structured before/after report after a CWE-fix run against the Armis Knowledge PROD environment. Rescans changed files, cites the org standards each fix used, lists residuals with product-decision flags, and optionally opens a PR. Use after finishing a batch of CWE fixes when the user asks for a report / diff / PR body. Triggers: /cwe-fix-report, generate cwe fix report, report the fixes, cwe report, open a pr for the fixes."
---

# /cwe-fix-report

Emit a structured markdown report summarizing a CWE-fix run — before/after findings per file, standards applied, residuals, notes — and optionally open a GitHub PR with the same content.

## When to use

- The user has just finished fixing scanner findings (typically via the CWE-fix skill) and wants to see a summary of what changed.
- The user says "report the fixes," "generate a diff summary," "open a PR with these fixes," or similar.
- Do NOT trigger this yourself mid-fix — only after edits are done and the working tree is stable.

## Inputs

- `--pr` (or "open a PR with these fixes") — also invoke the GitHub PR-create step at the end.
- `--base <branch>` — the pre-fix baseline branch (default: `origin/main`).
- `--diff` (or "just show me the diff") — emit a diff-only view: git diff summary + scanner before/after per file, without standards attribution, residuals, or notes. Useful for a quick paste-into-review or Slack. Compatible with `--pr` (the PR body is unaffected).
- No arguments — generate the full report to stdout only.

## How to build the report

Follow these steps in order. Do not skip the baseline scan — the whole point of the report is the before/after diff.

### 1. Establish the baseline

- Use git to list files changed against the base branch. Ask git for the changed-file list; the base defaults to origin's main branch unless the user passes a different one via `--base`.
- For each changed file, stash local edits temporarily, use the Armis appsec scanner's per-file scan tool on the pre-fix version, capture the findings, then restore the stashed edits.
- If stashing is not viable (commits already exist on the branch), use `git show <base>:<path>` to write the pre-fix content to a temp file and scan that instead.
- The scan output per file is the "initial findings" column.

### 2. Rescan the post-fix state

- Use the Armis appsec scanner's per-file scan tool on each changed file as it currently sits on disk.
- The result is the "final findings" column.

### 3. Attribute each fix to a standard

For every CWE that appeared in the initial set and is closed in the final set:

- Call the Armis Knowledge prod remediation lookup for that CWE (the tool that returns CWE-specific remediation guidance from the stage environment).
- If the response is a knowledge doc, cite `cwes/remediation/CWE-<n>` as the standard.
- If the response is 404 / not_found, cite `industry-standard (<language|framework>)`. Track these in the "Standards applied" section so the knowledge admin can register the missing docs.

### 4. Emit the report

Print this markdown structure. Include every section even if some are empty (write "None" or "clean" as appropriate).

````markdown
# CWE-fix report — <YYYY-MM-DD or run label>

## Summary
Closed **N of M** originally flagged findings across **F files**.
Surfaced **R residual findings** (all lower-severity than originals).
Standards applied: **<org_docs>** Armis Knowledge docs + **<fallback_count>** industry-standard fallbacks.

## Fix table

| File | Initial findings | Final findings | Standard applied |
|---|---|---|---|
| <path> | <cwe list or "clean"> | <cwe list or "clean"> | <cwes/remediation/CWE-N or industry-standard (lang)> |
| … | … | … | … |

**Legend:** `clean` = no findings; a CWE in "Final findings" is a new/residual, not the original.

## Standards applied

Bullet list. For each org doc used, cite it once with the files it backed. For industry-standard fallbacks, note the CWE ids so a knowledge admin knows what to register.

## Residual findings

Numbered list. One entry per finding that was NOT closed. Each entry: file — CWE — 1-2 sentences explaining why it wasn't auto-fixed and what the user needs to decide.

## Notes on the fix approach

Bullet list. Behavior changes (e.g. "pickle → JSON"), env-var requirements introduced, migrations callers need to do, standards principles applied when a specific CWE doc was missing.

## Files in working tree

<F> files modified, no commits, no test files added.
````

### 5. If `--pr` was passed

- Do NOT include the fix table in the PR body — keep it in stdout only for the user's local review. GitHub PRs get long fast; the table lives in the commit message body or a follow-up comment.
- PR body = Summary paragraph + Standards applied + Residual findings + Notes + Test plan checklist.
- Run the GitHub CLI's PR-create command with a title like "fix(cwe): batch remediation — <N> findings closed" and the body written to a tempfile.
- If the GitHub CLI fails, print the intended PR body and the exact command the user can run manually.

### 6. If `--diff` was passed

- Skip standards attribution, residuals, and notes.
- Emit `git diff --stat <base>...HEAD` as the header.
- For each changed file, print a two-column comparison: `Before:` (initial findings on the pre-fix version) → `After:` (findings on the current file). Same scanner both sides.
- If `--diff` is combined with `--pr`, the diff-only view goes to stdout AND the normal PR body (Summary + Standards + Residuals + Notes) still goes to the PR — the flag controls stdout only.

## Notes

- **Baseline detection:** if the git diff against the base branch returns nothing (no commits ahead), fall back to unstaged changes. Warn the user that "initial findings" was captured from the working-tree state before your edits, so results depend on the tree being clean before fixes started.
- **Scanner failures:** if a file scan errors, mark it "SCAN FAILED" in both columns and continue. Don't halt the whole report.
- **Skip files with no findings before OR after** — they add no signal.
- **Preserve the user's fix intent:** the residual section is the interesting part. Be specific about WHY each residual survived (WAF-layer concern, out of scope, apparent FP, downstream dep missing). Vague residuals defeat the point of the report.
