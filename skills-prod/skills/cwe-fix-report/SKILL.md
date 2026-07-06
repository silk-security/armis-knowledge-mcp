---
name: cwe-fix-report
description: "Produce a structured before/after report after a CWE-fix run against the Armis Knowledge PROD environment (shell-skills variant). Uses git diff + a scanner-provided baseline to build the fix table, cites the org standards each fix used, lists residuals, and optionally opens a PR. Use after finishing a batch of CWE fixes when the user asks for a report / diff / PR body. Triggers: /cwe-fix-report, generate cwe fix report, report the fixes, cwe report, open a pr for the fixes."
allowed-tools:
  - Bash(curl *)
  - Bash(jq *)
  - Bash(source *)
  - Bash(git *)
  - Bash(gh *)
---

# /cwe-fix-report

Emit a structured markdown report summarizing a CWE-fix run — before/after findings per file, standards applied, residuals, notes — and optionally open a GitHub PR.

## When to use

- The user has just finished fixing scanner findings (typically via the CWE-fix skill) and wants a summary of what changed.
- Triggers include "report the fixes," "generate a diff summary," "open a PR with these fixes."
- Do NOT trigger this yourself mid-fix — only after edits are done.

## Inputs

- `--pr` (or "open a PR with these fixes") — also invoke the GitHub PR-create command at the end.
- `--base <branch>` — the pre-fix baseline branch (default: `origin/main`).
- `--diff` (or "just show me the diff") — emit a diff-only view: git diff summary + scanner before/after per file, without standards attribution, residuals, or notes. Useful for a quick paste-into-review or Slack. Compatible with `--pr` (the PR body is unaffected).
- No arguments — generate the full report to stdout only.

## How to build the report

### 1. Establish the baseline

Shell-skills variant has no MCP scanner tool. Two paths:

- **Preferred:** ask the user to paste (or point at a file with) the pre-fix scan output — the report generator anchors on that.
- **Fallback:** run whichever scanner CLI the user has installed against the pre-fix version of each changed file. Get the changed-file list via git diff against the base branch (default `origin/main`).

### 2. Rescan the post-fix state

Use the same scanner CLI against the current working-tree state of each changed file. That output is the "final findings" column.

### 3. Attribute each fix to a standard

For every CWE closed between initial and final, look up the org's remediation doc for that CWE via the prod Knowledge backend. The `cwe-fix` skill in this plugin already exposes the exact API call — reuse its pattern rather than re-implementing here (source the plugin's armis-knowledge shell helper library and call the content-pack GET with `pack=cwes` and `name=CWE-<n>`).

- 200 response → cite `cwes/remediation/CWE-<n>` as the standard applied.
- 404 not_found → cite `industry-standard (<language|framework>)` and note the missing org doc so a knowledge admin can register it.

### 4. Emit the report

Print this exact markdown structure. Include every section; write "None" or "clean" for empty ones.

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

Bullet list. Behavior changes (e.g. "pickle → JSON"), env-var requirements, migrations callers need to do, standards principles applied when a specific CWE doc was missing.

## Files in working tree

<F> files modified, no commits, no test files added.
````

### 5. If `--pr` was passed

- Skip the fix table in the PR body — it belongs in the commit message or a follow-up comment.
- PR body = Summary + Standards applied + Residual findings + Notes + Test plan checklist.
- Run the GitHub CLI's PR-create command with a title like "fix(cwe): batch remediation — <N> findings closed" and the body written to a tempfile.
- On failure, print the intended body and the CLI command for the user to run manually.

### 6. If `--diff` was passed

- Skip standards attribution, residuals, and notes.
- Emit `git diff --stat <base>...HEAD` as the header.
- For each changed file, print a two-column comparison: `Before:` (initial findings on the pre-fix version) → `After:` (findings on the current file). Same scanner both sides.
- If `--diff` is combined with `--pr`, the diff-only view goes to stdout AND the normal PR body (Summary + Standards + Residuals + Notes) still goes to the PR — the flag controls stdout only.

## Notes

- **Baseline detection:** if the git diff against the base branch returns nothing (no commits ahead), fall back to unstaged changes and warn that "initial findings" was captured from the pre-edit working tree.
- **Skip files with no findings before OR after** — they add no signal.
- **Residual specificity:** each residual should call out WHY it survived (WAF-layer concern, out of scope, apparent FP, downstream dep missing). Vague residuals defeat the purpose.
