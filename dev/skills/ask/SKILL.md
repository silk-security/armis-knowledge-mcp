---
name: ask-dev
description: "Ask a free-form question about the Armis Knowledge base (DEV) and get a synthesized answer with citations. Use for explanatory questions about documents (\"what does X policy say?\", \"summarize our position on Y\"). Do NOT use for code generation or review — call /knowledge-dev for those so the calling agent stays in control of how standards are applied. Triggers: /ask-dev, /ask-knowledge-dev, ask the knowledge base, what does our knowledge say about, summarize what we have on."
---

# /ask-dev

Ask a free-form question about the documents in the Armis Knowledge base (dev). The MCP server runs the agent loop and returns a single synthesized answer — useful when the user wants prose, not raw search hits.

## When to use

- The user asks `/ask-dev <question>` or phrases the request as Q&A: "what does our knowledge base say about X?", "summarize what we have on Y", "which document covers Z?"
- → Call `mcp__armis_knowledge_dev__ask_knowledge(question)`.

## When NOT to use

- For code generation or review, prefer `/knowledge-dev` and the lower-level tools (`search_knowledge`, `get_cwe_remediation`, `list_standards`). They keep the calling agent in control of which standards apply, in what priority order, and how they shape the output.
- For a specific CWE, framework, or technology lookup, use the dedicated skill — `/cwe-fix-dev`, `/framework-guidance-dev`, `/tech-guidance-dev`.

## Output

The tool returns:
- `answer` — the synthesized prose. Surface this to the user verbatim or lightly paraphrased.
- `tools_used` — the search/lookup calls the server-side agent ran. Cite these so the user can audit.
- `stop_reason` — `end_turn` (normal), `max_turns` (loop hit the cap; partial answer).
- `error` — present only if the stream surfaced one.

## Notes

- Tenant resolution is server-side; never pass a customer/tenant parameter — the bearer token determines scope.
- The agent will not edit any document. If it suggests a change in prose, the user has to apply it manually through the editor or the proposals flow.
- If the server returns an auth error, the user's `ARMIS_CLIENT_ID` / `ARMIS_CLIENT_SECRET` / `ARMIS_KNOWLEDGE_TENANT_SLUG` env vars are missing or invalid — point them at `knowledge.moose-dev.armis.com/settings/integrations` to issue / rotate credentials.
