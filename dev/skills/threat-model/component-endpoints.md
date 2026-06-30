# `threat-model` — per-component endpoint + worklist enumeration (monorepo)

Subagent brief for the monorepo path of [`SKILL.md`](SKILL.md) Step 1 item 5a.
Dispatch the fenced block below as one per-component subagent brief (full
code-mcp access), in waves — one per component found by
[`component-discovery.md`](component-discovery.md). Pure structural enumeration —
NO threats, assets, severity, or bug reasoning. Output seeds the §3 entry-point
inventory and §3a routing table.

Substitute `{component_name}`, `{project_id}`, `{scope}` (the component's paths),
`{docs}` (its module docs), and `{out_path}` (where to write the inventory)
before dispatching.

```
Enumerate EVERY entry point in scope `{component_name}` of the indexed monorepo
`{project_id}`, then trace each inward.
SCOPE — analyze ONLY within these paths: {scope}
Module docs to read first (purpose + declared surface): {docs}

PROJECT ID — use this EXACT string as the `project` arg in every
mcp__armis_code_mcp_dev__* call (do not guess, do not call list_projects):
  {project_id}

This is a STRUCTURAL inventory. Do not judge whether anything is vulnerable; record
what is reachable. Be exhaustive — under-enumeration here is the failure mode.

Find entry points by reading the module docs/specs, then MCP (search_graph,
search_code, trace_path inbound, get_code_snippet, get_architecture) AND reading
code for dispatch/registration the graph misses. Entry-point kinds: HTTP
processors, servlets, REST @Path methods, GraphQL data fetchers (+ *.graphqls),
OAuth requestors, SOAP (+ *.wsdl), AMB/message handlers, scheduled jobs,
listeners, route/dispatch-table registrations.

For each entry point, trace inward (trace_path outbound / read callees) and record
the functions worth a deep scan: the endpoint method PLUS the internal and library
functions it reaches that do real work (parse, decode, query, build, set, load,
crypto, file/path, reflection). Include clean-reading helpers — a missing guard is
invisible until read. Skip only sub-10-line branchless getters/setters.

ALSO record security-sensitive functions in scope that no endpoint trace reached
— plugin/class loaders, reflection, (de)serialization adapters, expression/EL/
script evaluators, SQL/DB function builders, crypto/key/keystore handling, path/
file/zip ops. They are reachable through dispatch the graph misses; a deep scan
needs them even when an inbound trace is empty. Mark these `<fn>… | not-traced | …`.

SIBLING COMPLETENESS: when you record a class, record its same-package same-prefix
siblings of the same shape too — e.g. if `GlideExpressionScript`/`...Wrapper` are
in, so are `GlideExpressionJexl`/`...Rhino`/`...InterpolatedJS`; if one `*Processor`
or `*DataFetcher` is in, so are its peers. Variant siblings share the bug surface;
never list one and drop another.

Write to {out_path}, one line each, EXACTLY:
<endpoint>QUALIFIED_NAME | file:line | kind</endpoint>
<fn>QUALIFIED_NAME | reached_from_endpoint | note</fn>
Write before you end the turn — an enumeration you did not Write does not exist.
A scope with no endpoints still gets a file: write
<endpoint>none | {component_name} | none</endpoint> plus the <fn> lines for any
library functions worth scanning. End with: <comp_done>{component_name}: E endpoints, F fns</comp_done>.
```

Parse each component's file for `<endpoint>`/`<fn>` lines to build the §3
entry-point inventory and the deep-scan worklist. Resume: a component with a
non-empty endpoint file is done.
