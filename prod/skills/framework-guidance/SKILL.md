---
name: framework-guidance
description: "Fetch organization-specific guidance for a web framework (Django, Flask, FastAPI, Express, Rails, Spring, etc.) from the Armis Knowledge PROD environment. Use when generating or reviewing code that uses a specific framework, so framework-specific patterns and pitfalls are applied. Triggers: /framework-guidance, how do we use Django, Flask conventions, our patterns for Express, framework standards."
---

# /framework-guidance

Get tenant-specific guidance for a web framework from the **prod** environment (`knowledge-mcp.moose.armis.com`). Covers preferred patterns, banned APIs, security middleware, and conventions specific to the organization.

## When to use

- The user runs `/framework-guidance django` → call `mcp__armis_knowledge_prod__get_framework_guidance("django")`.
- You're writing or reviewing code that imports/uses a framework → call `get_framework_guidance` for that framework's name before making non-trivial changes.
- The user asks "how do we use <framework> here?" or "what's our convention for <framework>?" → same tool.

## How to apply

1. Apply the returned guidance to the code you write or review. If guidance contradicts a pattern in the existing codebase, surface the conflict — don't silently override.
2. Mention you applied "Armis Knowledge (prod) framework-guidance: <name>" so the user can audit.

## Notes

- Use the canonical lowercase framework name (`django`, `flask`, `fastapi`, `express`, `rails`, `spring`).
- If the tool returns "no guidance", continue with general best practices and tell the user the org has no specific guidance for that framework.
- Auth errors → check `ARMIS_CLIENT_ID` / `ARMIS_CLIENT_SECRET` are set; rotate at `knowledge.moose.armis.com/settings/integrations` if needed.
