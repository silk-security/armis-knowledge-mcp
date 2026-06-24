---
name: tech-guidance-stage
description: "Fetch organization-specific guidance for a programming language or runtime (Python, Go, TypeScript, Java, Rust, Node, etc.) from the Armis Knowledge STAGE environment. Use when generating or reviewing code in a specific language. Triggers: /tech-guidance-stage, how do we write Python, Go conventions, our TypeScript patterns, language standards."
allowed-tools:
  - Bash(curl *)
  - Bash(jq *)
  - Bash(source *)
---

# /tech-guidance-stage

Fetch Armis-specific guidance for a language or runtime from the **stage**
Knowledge backend.

```bash
source "$CLAUDE_PLUGIN_ROOT/lib/armis-knowledge.sh"
TENANT_ID=$(ak_tenant_id)
NAME="${ARGUMENTS:?usage: /tech-guidance-stage <language>  (e.g. python, go, typescript, java, rust, ruby)}"

ak_get /api/knowledge/content-pack \
  --data-urlencode "tenant_id=$TENANT_ID" \
  --data-urlencode "pack=technologies" \
  --data-urlencode "name=$NAME"
```

## How to apply

1. Apply the returned guidance to the code you write or review. If guidance
   contradicts a pattern in the existing codebase, surface the conflict —
   don't silently override.
2. If the response is `404 not_found`, the org has no specific guidance for
   that language; continue with general best practices and tell the user.
3. Cite: "Applied Armis Knowledge stage tech-guidance: <name>."

## Notes

- Use the canonical lowercase language name (`python`, `go`, `typescript`,
  `javascript`, `java`, `rust`, `ruby`).
- Auth errors → see the `knowledge-stage` skill's "Errors" section.
