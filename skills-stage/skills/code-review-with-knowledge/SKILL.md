---
name: code-review-with-knowledge-stage
description: "Review a GitHub PR (or local branch) against the Armis Knowledge STAGE org standards, optionally scanning it for security issues. Fetches the PR with your own gh/git auth, checks each changed file for conformance server-side, and prints one read-only verdict. Optionally posts comments or hands off to remediation — only on confirmation. Triggers: /code-review-with-knowledge-stage, review this PR, code review with knowledge, check this PR against our standards, is this PR secure and conformant."
allowed-tools:
  - Bash(git *)
  - Bash(gh *)
  - Bash(base64 *)
  - Bash(jq *)
---

# /code-review-with-knowledge-stage

Review a GitHub PR's changed files against your org's knowledge (standards +
framework/technology guidance) and, optionally, scan them for security issues.
Read-only: it reports a verdict; it never blocks or merges.

The backend does the thinking (per-file conformance check, PR-level synthesis,
false-positive judgment); this skill is the hands — it fetches the PR with your
own `gh`/`git` auth, uploads file contents, prints the verdict, and (only on
explicit confirmation) posts comments or hands off to remediation. The API sees
only uploaded strings; it never touches your disk or GitHub.

## When to use

- The user pastes a GitHub PR URL they have access to and asks to review it.
- Triggers: "review this PR," "check this PR against our standards," "is this PR
  secure and conformant."

## Usage

- `/code-review-with-knowledge-stage <github-pr-url> [--scan]`
- Also accepts a local branch: `/code-review-with-knowledge-stage --local <ref>`

## Procedure

1. **Parse the input.** From the PR URL extract `owner/repo` and PR number
   (`https://github.com/OWNER/REPO/pull/N`). For `--local <ref>`, diff against
   the merge-base with the default branch
   (`git merge-base origin/HEAD <ref>`).

2. **Fetch (your own auth, local).**
   - Changed files:
     ```bash
     gh pr view N --repo OWNER/REPO --json files,title,baseRefName,headRefName,headRefOid
     ```
   - Per-file post-change content:
     ```bash
     gh api "repos/OWNER/REPO/contents/<path>?ref=<head-sha>" --jq '.content' | base64 -d
     ```
     (or `git show <head>:<path>` for `--local`). Skip and record any file
     larger than 200 KB — the API caps each file's content at 200 KB and the
     whole set at 50 files.
   - PR metadata: title, base, head for the report header.
   - If fetch fails (bad URL / no access / `gh` unauthed): stop with a clear
     message naming the cause — this is the mandatory input.

3. **(optional) Scan — only if `--scan`.**
   a. Fail-fast probe: run `scan_code` on a tiny snippet to confirm the appsec
      scanner is present AND authed. If it fails, tell the user and offer to
      continue knowledge-only — do not hard-fail over an optional dependency.
   b. If the probe passes: run `scan_diff` on the PR diff and collect
      `{path, cwe, severity, title, line, description}` per finding.

4. **Review.** Call the `review_pr` MCP tool:
   `review_pr(files=[{path, content, language}], pr_meta, scan_findings?)`.
   Infer `language` from the extension (`.py`→python, `.ts`→typescript,
   `.go`→go, `.java`→java, …); use `any` when unknown. `pr_meta` is
   `{title, base, head, url}`. Pass `scan_findings` only if you scanned.

5. **Report (terminal, read-only).** Print `overall` (secure? conforms?
   summary), then per-file violations / uncertain with their cited standards,
   then the security findings if you scanned. Files sort violations-first.
   **If `coverage.state` is `empty` or `no_applicable_content`, say plainly
   that no org standards applied — do NOT imply a clean bill of health.**
   Report any file you skipped for size (`not_reviewed: file_too_large`); never
   drop one silently.

6. **Post-review action — ask ONCE, confirm before any write.** The review is
   read-only; the only writes happen here, and only after the user chooses:
   a. **Nothing** (default) — terminal report only.
   b. **Post to the PR** — inline comments via
      `gh api repos/OWNER/REPO/pulls/N/comments` and a summary via
      `gh pr comment N --repo OWNER/REPO`. Confirm the exact comments first.
   c. **Hand off to `/remediate-with-knowledge-stage`** — pass the findings
      into the fix flow. Confirm first.

## Notes

- If the tenant has no model configured, `review_pr` returns 409
  (`model_not_configured`). Tell the user the conformance review can't run and
  stop the review step.
- The appsec scan is opt-in (`--scan`); knowledge conformance always runs.
- **Never** post comments, open a PR, or hand off without explicit
  confirmation. Verdicts are advisory — this skill never gates or merges.
- Everything crosses the API as strings: you upload file contents and receive a
  verdict. The API never reads your disk or writes to GitHub — that is entirely
  this skill's job.
