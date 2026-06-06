---
name: tech-guidance-dev
description: "Fetch organization-specific guidance for a programming language or runtime (Python, Go, TypeScript, Java, Rust, Node, etc.) from the Armis Knowledge DEV environment. Use when generating or reviewing code in a specific language so language idioms, banned APIs, and required patterns are applied. Triggers: /tech-guidance-dev, how do we write Python, Go conventions, our TypeScript patterns, language standards."
---

# /tech-guidance-dev

Get tenant-specific guidance for a language or runtime from the **dev** environment (`knowledge-mcp.moose-dev.armis.com`). Covers idioms, banned APIs, required libraries, and conventions specific to the organization.

## When to use

- The user runs `/tech-guidance-dev python` → call `mcp__armis_knowledge_dev__get_technology_guidance("python")`.
- You're writing or reviewing non-trivial code in a language → call `get_technology_guidance` for that language before proposing code.
- The user asks "how do we write <language> here?" or "what's our convention for <language>?" → same tool.

## How to apply

1. Apply the returned guidance to the code you write or review. If guidance contradicts a pattern in the existing codebase, surface the conflict — don't silently override.
2. Mention you applied "Armis Knowledge (dev) tech-guidance: <name>" so the user can audit.

## Notes

- Use the canonical lowercase language name (`python`, `go`, `typescript`, `javascript`, `java`, `rust`, `ruby`).
- If the tool returns "no guidance", continue with general best practices and tell the user the org has no specific guidance for that language.
- Auth errors → check `ARMIS_CLIENT_ID` / `ARMIS_CLIENT_SECRET` / `ARMIS_TENANT_SLUG` are set; rotate at `knowledge.moose-dev.armis.com/settings/integrations` if needed.
