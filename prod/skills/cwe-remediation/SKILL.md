---
name: cwe-remediation
description: "Fetch organization-specific remediation guidance for a given CWE from the Armis Knowledge PROD environment. Use when fixing a vulnerability identified by CWE ID, when triaging scanner findings, or when the user asks how to remediate a specific weakness. Also surfaces false-positive patterns. Triggers: /cwe-fix, how do we fix CWE-, remediation for CWE, false positive CWE, cwe guidance."
---

# /cwe-fix

Get tenant-specific remediation and false-positive guidance for a CWE from the **prod** environment (`knowledge-mcp.moose.armis.com`).

## When to use

- The user runs `/cwe-fix CWE-89` (or any CWE id) → call `mcp__armis_knowledge_prod__get_cwe_remediation("CWE-89")`.
- The user is fixing a scanner finding tagged with a CWE → call `get_cwe_remediation` for that CWE before proposing code.
- The user asks "is this a real CWE-XX or false positive?" → call `mcp__armis_knowledge_prod__get_cwe_fp_reduction("CWE-XX")`.

## How to apply

1. Read the remediation content end-to-end before writing fix code; the org may prescribe a specific library, helper, or pattern.
2. If the FP-reduction tool returns matching patterns for the code in question, surface that to the user before recommending a code change — it may not be a real bug.
3. Mention you applied "Armis Knowledge (prod) CWE-XX guidance" so the user can audit.

## Notes

- CWE id format is `CWE-<number>` (e.g. `CWE-89`, `CWE-79`). The tool will normalize but prefer the canonical form.
- Auth errors → check `ARMIS_CLIENT_ID` / `ARMIS_CLIENT_SECRET` are set; rotate at `knowledge.moose.armis.com/settings/integrations` if needed.
