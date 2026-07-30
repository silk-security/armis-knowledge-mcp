---
name: remediate-with-knowledge-stage
description: "Batch-fix a repo from a findings file (CSV/JSON/txt) against the Armis Knowledge STAGE environment: ingest findings, plan one-or-many PRs, generate fixes server-side, apply + re-scan to verify, and deliver via GitHub/other/local. The backend owns all remediation intelligence; this skill is the hands that read files, apply diffs, and run git. Triggers: /remediate-with-knowledge-stage, remediate findings, fix vulnerabilities from a spreadsheet, batch remediation, fix these scan results."
allowed-tools:
  - Bash(git *)
  - Bash(gh *)
  - Bash(base64 *)
  - Bash(jq *)
---

# /remediate-with-knowledge-stage

Fix a batch of vulnerabilities in the current repo from a findings file, in one
or many PRs, then re-scan to confirm each fix. The backend does the thinking
(parsing, PR planning, patch generation, false-positive suppression); this skill
reads files, applies diffs, runs the scanner, and drives git/GitHub.

## Usage

- `/remediate-with-knowledge-stage <path-to-findings.{csv,json,txt}>`

The findings file is whatever a scanner or spreadsheet exported: CSV, JSON, or
free-form text. Native Excel (`.xls`/`.xlsx`) is not supported — export to CSV
first.

## How it works

You never assemble a fix, decide which findings group into which PR, or judge a
false positive. Those live behind the API and are reached through three MCP
tools: `ingest_findings`, `plan_remediation`, `generate_remediation_patch`. The
API sees only uploaded strings (file contents in, a unified diff out); it never
touches your disk or GitHub. You do.

## Procedure

1. **Ingest.** Base64-encode the findings file and call
   `ingest_findings(content_b64, filename)`. Print "N findings across M files"
   and list any parse errors it returned. **Stop if zero findings.**

   ```bash
   B64=$(base64 < "$FINDINGS_PATH" | tr -d '\n')
   ```

   Then call the MCP tool with `content_b64=$B64` and `filename` set to the
   file's basename. A 409 (`model_not_configured`) on a `.txt` file means the
   tenant has no LLM model configured — tell the user and stop.

2. **Plan.** Call `plan_remediation(findings, strategy)` (default `by_cwe`;
   `by_dir` and `single` are the other strategies). Print the proposed groups —
   each group becomes one PR, with its `pr_label`, `rationale`, `finding_ids`,
   and `files`.

   **HARD GATE: get explicit user approval (or an override strategy) before
   creating any branch.** Do not proceed to step 4 until the user confirms.

3. **Delivery workflow — ask ONCE.** Inspect the repo: `git remote -v`,
   `gh auth status`, and the remote host. Ask the user which delivery they want,
   and remember the answer for the whole run:
   - **(a) GitHub PRs** — push each branch and open a PR.
   - **(b) other provider** — push each branch and print the compare/MR URL.
   - **(c) local branches only** — leave the branches unpushed.

4. **Per group** (repeat for each approved group):
   a. Branch off the base: `git checkout <base> && git checkout -b remediate/<label>`
      (base is `origin/main` unless the user said otherwise; `<label>` is the
      group's `pr_label`, lowercased and slugified).
   b. Read the group's files from the working tree. Skip and record any file
      that is missing or larger than 200 KB — the API caps total uploaded
      content at 200 KB.
   c. Call `generate_remediation_patch(findings, file_contents)` where
      `file_contents` is `{path: current file text}` for the group's files.
      Handle each entry in the returned `per_finding` log:
      - `action: patch` — the diff edits the code; apply it (step d).
      - `action: suppress` — a known false positive. Do NOT edit logic; add an
        `armis:ignore cwe:<n> reason: <the rationale>` comment on the flagged
        line instead.
      - `action: skip` — the file wasn't uploaded or wasn't touched; record it
        for the report.
   d. Apply the diff with `git apply`. If it doesn't apply cleanly, do NOT
      force it — record the group as a residual needing manual review and move
      on to the next group.
   e. Stage and commit: `git add -A && git commit`. The appsec PreToolUse hook
      intercepts the commit and forces a `scan_diff` on the staged changes
      first — that IS the verify step; let it run. If it reports HIGH/CRITICAL
      findings, present them to the user; never approve findings on their
      behalf.
   f. **Verify loop (max 2 retries).** Run `scan_diff` on the branch. If
      residual findings remain for this group, pass them as the `feedback`
      argument to `generate_remediation_patch`, re-apply, re-commit, and
      re-scan. After 2 retries, stop and record the remaining findings as
      residuals.
   g. **Deliver** per the workflow chosen in step 3:
      - GitHub: `git push -u origin remediate/<label>`, then open the PR with
        `gh api repos/OWNER/REPO/pulls` (see Notes).
      - other provider: `git push -u origin remediate/<label>` and print the
        compare URL.
      - local: leave the branch in place and tell the user its name.

5. **Report.** For each PR, collect the pre-fix and post-fix scanner findings
   per file and call `assemble_cwe_fix_report(files, run_label, base)`. Print
   the aggregated summary and every residual (skipped files, un-appliable
   patches, findings still open after the verify loop).

## Notes

- **Never** force-apply a patch or suppress a real vulnerability. A `suppress`
  action is only for findings the API judged to be false positives.
- Open PRs with `gh api repos/OWNER/REPO/pulls` — **not** `gh pr create`. From a
  worktree, `gh pr create` trips the appsec gate; the raw API call does not.

  ```bash
  gh api repos/OWNER/REPO/pulls -f title="Remediate <label>" \
    -f head="remediate/<label>" -f base="main" -f body="$PR_BODY"
  ```

- If the tenant has no model configured, the patch and txt-ingest steps return
  409 `model_not_configured`. Tell the user and stop those steps.
- Everything crosses the API as strings: you upload file contents and receive a
  unified diff. The API never reads your disk or writes to GitHub — that is
  entirely this skill's job.
