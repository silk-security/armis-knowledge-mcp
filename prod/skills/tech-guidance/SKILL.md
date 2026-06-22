---
name: tech-guidance
description: "Fetch organization-specific guidance for a programming language or runtime (Python, Go, TypeScript, Java, Rust, Node, etc.) from the Armis Knowledge PROD environment. Use when generating or reviewing code in a specific language so language idioms, banned APIs, and required patterns are applied. Triggers: /tech-guidance, how do we write Python, Go conventions, our TypeScript patterns, language standards."
---

# /tech-guidance

Get tenant-specific guidance for a language or runtime from the **prod** environment (`knowledge-mcp.moose.armis.com`). Covers idioms, banned APIs, required libraries, and conventions specific to the organization.

## When to use

- The user runs `/tech-guidance python` → call `mcp__armis_knowledge_prod__get_technology_guidance("python")`.
- You're writing or reviewing non-trivial code in a language → call `get_technology_guidance` for that language before proposing code.
- The user asks "how do we write <language> here?" or "what's our convention for <language>?" → same tool.

## How to apply

1. Apply the returned guidance to the code you write or review. If guidance contradicts a pattern in the existing codebase, surface the conflict — don't silently override.
2. Mention you applied "Armis Knowledge (prod) tech-guidance: <name>" so the user can audit.

## Notes

- Use the canonical lowercase language name (`python`, `go`, `typescript`, `javascript`, `java`, `rust`, `ruby`).
- If the tool returns "no guidance", continue with general best practices and tell the user the org has no specific guidance for that language.
- Auth errors → check `ARMIS_CLIENT_ID` / `ARMIS_CLIENT_SECRET` are set; rotate at `knowledge.moose.armis.com/settings/integrations` if needed.
