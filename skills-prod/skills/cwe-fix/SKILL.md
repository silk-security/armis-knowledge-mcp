---
name: cwe-fix
description: "Fetch organization-specific remediation guidance for a given CWE from the Armis Knowledge PROD environment. Use when fixing a vulnerability identified by CWE ID, when triaging scanner findings, or when the user asks how to remediate a specific weakness. Triggers: /cwe-fix, how do we fix CWE-, remediation for CWE, false positive CWE, cwe guidance."
allowed-tools:
  - Bash(security *)
  - Bash(secret-tool *)
  - Bash(curl *)
  - Bash(jq *)
  - Bash(source *)
---

# /cwe-fix

Fetch Armis-specific remediation for a CWE from the **prod** Knowledge backend.

```bash
source "$CLAUDE_PLUGIN_ROOT/lib/armis-knowledge.sh"
TENANT_ID=$(ak_tenant_id)
CWE="${ARGUMENTS:?usage: /cwe-fix CWE-89}"

ak_get /api/knowledge/content-pack \
  --data-urlencode "tenant_id=$TENANT_ID" \
  --data-urlencode "pack=cwes" \
  --data-urlencode "name=$CWE"
```

Response shape: `{id, title, content_pack, path, body_text}`.

## How to apply

1. Read `body_text` end-to-end before writing fix code — the org may prescribe
   a specific helper, library, or pattern.
2. If the response is `404 not_found`, the org has no specific doc for that
   CWE. Tell the user, then proceed with general best practices.
3. Cite the doc in your response: "Applied Armis Knowledge prod CWE-89 guidance."

## Notes

- Canonical CWE format is `CWE-<number>` (e.g. `CWE-89`, `CWE-79`).
- Auth errors → see the `knowledge` skill's "Errors" section.
