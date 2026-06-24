---
name: framework-guidance
description: "Fetch organization-specific guidance for a web framework (Django, Flask, FastAPI, Express, Rails, Spring, etc.) from the Armis Knowledge PROD environment. Use when generating or reviewing code that uses a specific framework. Triggers: /framework-guidance, how do we use Django, Flask conventions, our patterns for Express, framework standards."
allowed-tools:
  - Bash(curl *)
  - Bash(jq *)
  - Bash(source *)
---

# /framework-guidance

Fetch Armis-specific guidance for a web framework from the **prod** Knowledge backend.

```bash
source "$CLAUDE_PLUGIN_ROOT/lib/armis-knowledge.sh"
TENANT_ID=$(ak_tenant_id)
NAME="${ARGUMENTS:?usage: /framework-guidance <framework>  (e.g. django, flask, fastapi, express, rails, spring)}"

ak_get /api/knowledge/content-pack \
  --data-urlencode "tenant_id=$TENANT_ID" \
  --data-urlencode "pack=frameworks" \
  --data-urlencode "name=$NAME"
```

## How to apply

1. Apply the returned guidance to the code you write or review. If guidance
   contradicts a pattern in the existing codebase, surface the conflict —
   don't silently override.
2. If the response is `404 not_found`, the org has no specific guidance for
   that framework; continue with general best practices and tell the user.
3. Cite: "Applied Armis Knowledge prod framework-guidance: <name>."

## Notes

- Use the canonical lowercase framework name (`django`, `flask`, `fastapi`,
  `express`, `rails`, `spring`).
- Auth errors → see the `knowledge` skill's "Errors" section.
