---
name: knowledge-dev
description: "Query the Armis Knowledge base (DEV environment) for organizational standards, policies, and tenant-specific guidance. Use when generating, reviewing, or remediating code so the work matches the organization's standards. Triggers: /knowledge-dev, what are our standards for, what does our org say about, search knowledge, list standards, knowledge base."
---

# /knowledge-dev

Query the Armis Knowledge base in the **dev** environment (`knowledge-mcp.moose-dev.armis.com`). The data lives server-side; this skill routes user intent to the right MCP tool.

## When to use

- Writing or reviewing security-sensitive code → call `mcp__armis_knowledge_dev__list_standards("project")`, then `mcp__armis_knowledge_dev__get_cwe_remediation` for any CWE relevant to the work.
- The user asks "what are our standards for X?" or "what does our org say about Y?" → `mcp__armis_knowledge_dev__search_knowledge(query)`.
- The user runs `/knowledge-dev <query>` → `mcp__armis_knowledge_dev__search_knowledge(query)`.
- The user runs `/knowledge-dev list <scope>` (scope ∈ org, dept, team, project) → `mcp__armis_knowledge_dev__list_standards(scope)`.

## Priority

The server returns standards already in priority order — apply them top-down. Briefly mention which standards you applied so the user can audit.

## Notes

- Tenant resolution is server-side; never pass a customer/tenant parameter — the bearer token determines scope.
- If the server returns an auth error, the user's `ARMIS_CLIENT_ID` / `ARMIS_CLIENT_SECRET` env vars are missing or invalid — point them at `knowledge.moose-dev.armis.com/settings/integrations` to issue / rotate credentials.
