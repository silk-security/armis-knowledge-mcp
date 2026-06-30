# `threat-model` — component discovery (monorepo)

Subagent brief for the monorepo path of [`SKILL.md`](SKILL.md) Step 1 item 5a.
Dispatch the fenced block below to one subagent (full code-mcp access). Pure
structural inventory — NO threats, assets, severity, or bug reasoning. The map
seeds the worklist; threat reasoning lives in the main skill.

Substitute `{project_id}` (from `index_repository`) and `{target}` (the target
dir) before dispatching.

```
Map the components of the indexed monorepo `{project_id}` (source at {target}).
A component = an independently-built/deployed module or submodule (a microservice,
library, or top-level service dir), NOT every package.

This is a STRUCTURAL inventory only. Do not look for vulnerabilities, assets, or
threats. Record what exists, not what could go wrong.

PROJECT ID — use this EXACT string as the `project` arg in every
mcp__armis_code_mcp_prod__* call (do not guess, do not call list_projects):
  {project_id}

Fuse these sources — do not assume a layout, read what is actually there:
  • top-level + nested dirs and their package roots;
  • build descriptors if any (pom.xml, build.gradle, package.json, go.mod);
  • graph: get_architecture (packages/layers), search_graph for Module/Folder nodes,
    and cross-component CALLS / INHERITS / IMPORTS edges (project={project_id});
  • module docs: README*/readme* and API specs (*.graphqls, *.wsdl, *.xsd,
    openapi*, swagger*, *.proto) found per component — these self-document purpose
    and surface. Read the ones that exist; do not invent paths.

A component need not have a build file or a README — a coherent source dir with its
own package root is a component.

Emit one line per component and one per inter-component dependency, EXACTLY:
<component>NAME | ROOT_DIR_REL_PATH | one-line purpose | docs:rel,paths,or,none</component>
<dep>FROM_NAME -> TO_NAME | why (calls/inherits/imports)</dep>

Cover every component — a remainder/uncategorized dir still gets a <component> line.
End with one line: <map_done>N components, M deps</map_done>.
```

Parse the `<component>`/`<dep>`/`<map_done>` lines from the subagent's final
message to build the component map that drives the per-component endpoint pass.
