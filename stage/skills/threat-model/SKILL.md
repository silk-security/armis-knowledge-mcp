---
name: threat-model-stage
description: "Generate a threat model for a target application using local code-intelligence (the bundled armis-code-mcp server). Produces armis-appsec-v2-results/<repo>/THREAT_MODEL.md with an 8-section, stable-ID schema (T1, T2, … threats; M1, M2, … mitigations) that downstream appsec skills can cite. Use when the user asks to create a threat model, security analysis, or risk assessment of a codebase. Triggers: /threat-model-stage, threat model this repo, security risk assessment, attack surface analysis."
---

# /threat-model-stage — Threat Model Generator

Produce `THREAT_MODEL.md` for the application at `<target-dir>` (defaults to the
current working directory when no argument is given).

This skill is **static analysis only**. It reads source, configs, and any
vulnerability reports the user supplies. It does not build, execute, fuzz, or
modify the target, and does not make network requests against the target's live
infrastructure.

It is grounded in the **`armis-code-mcp` code-intelligence server bundled with
this plugin** (the local `codebase-memory-mcp` binary). All graph queries below
use the `mcp__armis_code_mcp_stage__*` tools. The binary indexes the repo into a
local graph on disk; nothing is sent to Armis infrastructure and no credentials
are required for the code-intelligence side.

A litmus test for what belongs in the model: **if patching one line of code
makes an entry disappear, it was a vulnerability, not a threat.** A threat
("attacker achieves RCE via untrusted media parsing") still stands after every
known bug is fixed; a vulnerability does not. This skill produces threats.
Specific bugs appear only as **evidence** that raises a threat's likelihood.

## Output location

`<results> = <target-dir>/armis-appsec-v2-results/<repo>/`, where `<repo>` is the
basename of the target directory. Write the threat model to
**`<results>/THREAT_MODEL.md`** (directly under `<results>`, not a `docs/`
subdir). `mkdir -p <results>` first. If downstream appsec skills (`armis-discovery`,
`armis-verify`) are installed they read exactly this path, so the location and
the 8-section schema below are a contract — keep both stable.

## Progress

Print a `[threat-model] <stage> — <detail>` banner when you start indexing and
again when the file is written, so the user can follow along. (This skill is
phase 1 of the broader appsec pipeline; the stable IDs exist so later phases can
cite threats and mitigations by number.)

---

## Step 1 — Index and gather facts

1. **Index** the target if it is not already indexed:
   ```
   mcp__armis_code_mcp_stage__index_repository(repo_path=<target-dir>)
   ```
   Capture the returned `project` id; every subsequent call needs it. Use this
   EXACT id string as the `project` arg — do not guess it.

2. **Wait for indexing to finish** before querying:
   ```
   mcp__armis_code_mcp_stage__index_status(project=<project_id>)
   ```
   Proceed only when `status == "ready"`. Note the `nodes`/`edges` counts.

3. **Discover the schema** so you query labels that actually exist:
   ```
   mcp__armis_code_mcp_stage__get_graph_schema(project=<project_id>)
   ```

4. **Collect facts.** Run these queries against the graph; do not skip them —
   the threat model must be grounded in real code. **Watch for truncation.**
   `search_graph` caps at `limit` (default 200) and returns `total` plus
   `has_more`; if `has_more` is true, paginate. `search_code` caps at `limit`
   (default 10) and reports `total_results` / `total_grep_matches`; if those
   exceed what you received, raise `limit` or narrow with `file_pattern`.

   - `mcp__armis_code_mcp_stage__get_architecture(project=<project_id>, aspects=["all"])`
   - `mcp__armis_code_mcp_stage__search_graph(project=<project_id>, label="Route")`
   - `mcp__armis_code_mcp_stage__search_graph(project=<project_id>, label="Function")`
   - `mcp__armis_code_mcp_stage__search_graph(project=<project_id>, label="Class")`
   - `mcp__armis_code_mcp_stage__search_code(project=<project_id>, pattern="valid|sanitiz|auth|check|verify|hash|encrypt|token|csrf|password", regex=true, mode="full")`
   - `mcp__armis_code_mcp_stage__search_code(project=<project_id>, pattern="secret|key|password|credential|token|api_key|env|config", regex=true, mode="compact")`

   > **Why only these two sweeps (the controls sweep and the secrets/config
   > sweep), not DB-sink / filesystem-sink sweeps.** This skill produces
   > *threats*, not a vuln catalog — discovery (a later phase, if run) re-traces
   > every entry point to its sinks from scratch, so enumerating individual
   > `execute`/`query`/`open`/`upload` call-sites here is redundant work and
   > tempts the threat model to bake a premature bug-class guess into §3a/§4 that
   > then steers discovery's attention. The two sweeps kept carry threat-level
   > context: the **defensive posture** (what auth/validation/CSRF controls
   > exist, for §4 `controls`/`status`) and **secrets/assets/config at rest** (for
   > §2 and the at-rest threats — a committed key IS a threat). The
   > architecture-level signal ("this app has a SQL layer / file uploads") comes
   > from `get_architecture` and from reading the route handlers + DB models in
   > item 5.

5. **Read key files** directly to fill in context:
   - Entry-point file (`main.py`, `app.py`, `index.ts`, `server.go`, …)
   - `Dockerfile`, `docker-compose.yml`, `.env*`, `config/`
   - **Deployment IaC** — `*.tf`, `*.hcl` (incl. `terragrunt.hcl`), k8s/helm
     manifests, entrypoint `*.sh`: record §1 deployment facts that gate
     reachability (injected env vars, protocol/scheme allowlists, network
     boundaries, feature flags).
   - Database models / schema definitions
   - Auth/authorization modules
   - Route handlers (full source, not just signatures)
   - `README*`, `requirements.txt` / `package.json` / `go.mod` / `Cargo.toml`

5a. **Coarse subsystem pass (monorepo-safe; routing labels only).** From
   `get_architecture(aspects=["all"])` `packages`/`layers`, enumerate the
   subsystems, the trust boundary each sits behind, and tag each with its
   **dominant likely bug-class**. This is a **LIGHT** pass: no separate deep
   fact-gathering per subsystem — the whole-target queries in item 4 already
   gathered the facts; this step only *labels* what they surfaced. These labels
   feed the terse §3a table.

   **Monorepo note.** Never feed a whole monorepo to one deep model. For a large
   monorepo, fan out structural enumeration to subagents using the two briefs
   shipped alongside this skill: [`component-discovery.md`](component-discovery.md)
   (map the components) and [`component-endpoints.md`](component-endpoints.md)
   (per-component entry-point + worklist enumeration). Each brief is a pure
   structural inventory — no threat reasoning — whose output seeds §3 and §3a.
   The fix here is routing *labels*, not N per-submodule threat models, so the
   document stays roughly its current size.

6. **Determine context.** From the gathered data: what the application does, who
   uses it, what data it handles (sensitivity), how it deploys, what external
   services it talks to, what auth model it uses, where its trust boundaries are.

---

## Step 2 — Output schema

Write `<results>/THREAT_MODEL.md` with **exactly these eight sections, in this
order, with these table column orders.** A consumer that only needs the threat
table can regex for `^## 4\. Threats$` and read until the next `^## `.

### Diagrams (required — for human readers)

Every section that calls for a diagram below MUST include it. The diagrams are
what lets a developer who has never seen the codebase understand the system, its
data flows, and its attack paths at a glance. Ground each diagram in the §1–§4
facts; do not draw components or flows the graph queries did not surface.

**Diagrams must not break the schema.** Downstream consumers parse this file by
heading and pipe-table — they are oblivious to diagrams *as long as* you follow
two rules:

1. **Always inside a ` ```mermaid ` fence.** A fenced block is invisible to the
   table extractor (it scans for `| … |` rows) and is immune to the raw-HTML
   truncation hazard — so, unlike prose, diagram source does **not** need its
   angle brackets backticked or escaped.
2. **Never between a section heading and its table.** In §2, §3, §4, and §8 the
   pipe-table comes **first**, immediately under the heading; place any diagram
   **after** the table. (§1 has no table, so its diagram leads the section.)

Validate the mermaid before declaring the file written: each fence opens with a
known diagram type (`graph`/`flowchart`, `erDiagram`, `sequenceDiagram`,
`quadrantChart`) and node labels containing reserved characters are quoted.

```markdown
# Threat Model: <system name>

## 1. System context

## 2. Assets

## 3. Entry points & trust boundaries

## 3a. Subsystems & bug-class priors

## 4. Threats

## 5. Deprioritized

## 6. Open questions

## 7. Provenance

## 8. Recommended mitigations
```

Section 8 is **optional and additive** — older models may omit it; consumers
must tolerate its absence. When you do include it, downstream skills will use it
to downgrade severity on covered finding classes.

### 1. System context

One to three paragraphs of prose: what the system is, what it does, who uses it,
where it runs. No table.

Include a **high-level architecture diagram** (mermaid `graph`) showing all major
components, data stores, and external dependencies, and a
**component-interaction diagram** if the module structure is non-trivial. Place
the diagram(s) after the prose.

### 2. Assets

| asset | description | sensitivity |
|---|---|---|

`sensitivity` — {`low`, `medium`, `high`, `critical`}. Discovery uses this to
**lift severity** on findings whose data flow touches a critical/high asset.

After the table, if the system has a database, include a **data-model diagram**
(mermaid `erDiagram`) showing the stored entities and their relationships.

### 3. Entry points & trust boundaries

| entry_point | description | trust_boundary | reachable_assets |
|---|---|---|---|

`trust_boundary` is free text naming the crossing (e.g. "untrusted file →
process memory", "unauth network → authenticated session"). `reachable_assets`
is a comma-separated list of names from §2.

`entry_point` rows can be validated against the graph by downstream skills:
stale entries (no longer present) are flagged; routes the graph knows about that
are missing here are surfaced as **untracked entry points**.

After the table, include two diagrams:
- A **trust-boundary diagram** (mermaid `graph`) with each boundary drawn as a
  labeled `subgraph` and the entry points crossing into it.
- A **sequence diagram** (mermaid `sequenceDiagram`) for the most
  security-critical flow — at minimum authentication, plus whichever flow handles
  the most sensitive asset from §2.

### 3a. Subsystems & bug-class priors

A **terse routing table** — one row per subsystem from the Step 1 item-5a coarse
pass. Keep it small (a few rows, no prose blocks): this is *routing metadata* for
discovery, not a second threat enumeration.

| subsystem | scope (pkgs/dirs) | trust_boundary | bug_class_prior |
|---|---|---|---|

`bug_class_prior` is the dominant bug-class to hunt in that subsystem. Use this
shared value set (also used by §4's `bug_class_prior` column):

- `arithmetic-logic-state` — signed-compare / overflow / wraparound that flips a
  branch or corrupts logic state on attacker input (e.g. TCP/sequence handling).
- `oob-length-parsing` — out-of-bounds / length-driven memory bugs (e.g.
  demuxer / parser / media decode).
- `crypto-misuse` — nonce/IV/key reuse, weak or non-constant-time primitives.
- `injection-taint` — classic untrusted-input → sink (e.g. web/RPC handlers).
- `authz-logic` — wrong authorization decision (IDOR, confused deputy).
- `lifetime-uaf` — use-after-free / double-free driven by attacker input or
  protocol state (NOT a local-only race).
- `none` — no dominant prior; discovery runs all axes co-equal.

These are **routing PRIORS, not threats** — concrete threats still get their own
`T<n>` rows in §4. This table just tells discovery *how* to hunt each subsystem.

### 4. Threats

**This is the threat model proper.** One row per actor-wants-outcome pair, at the
abstraction level where it survives a patch.

| id | threat | actor | surface | bug_class_prior | asset | impact | likelihood | status | controls | evidence |
|---|---|---|---|---|---|---|---|---|---|---|

- `id`: `T1`, `T2`, … **Stable across edits; do not renumber when rows are
  removed.** Findings cite this id via `<threat_id>T<n></threat_id>`.
- `threat`: One sentence, active voice, names the outcome ("Remote code execution
  via untrusted audio file parsing", not "buffer overflow in dr_wav").
- `actor` — {`remote_unauth`, `remote_auth`, `adjacent_network`, `local_user`,
  `local_admin`, `supply_chain`, `insider`}.
- `surface`: Which entry point(s) from §3 this threat traverses — **or `at-rest`
  / `egress` / `config` when the threat has no request path**. Not every threat
  is an attacker walking in through an entry point: enumerate the whole surface.
  Include threats that are a **property of the code or its configuration** (a
  secret/credential/key committed in source, an unsafe default, weak or missing
  crypto/auth/access-control) and threats where **sensitive data leaves** the
  system (logs, error responses, telemetry, third parties). Give them a `T<n>`
  row anyway so discovery has something to anchor to.
  **Scope guardrail (do NOT over-enumerate).** This widens the surface to
  *concrete* code-property threats. It does **NOT** license speculative or
  best-practice threats: **no** denial-of-service / resource-exhaustion /
  "unbounded read", **no** missing audit logs / rate limits, **no** "a future
  caller might…" or "if someone later set `*`…", **no** missing-hardening rows
  with no concrete exploit. If you cannot name the concrete asset compromised and
  a realistic actor, it is not a threat row. Aim for the threats a competent
  engineer would triage, not an exhaustive checklist.
- `bug_class_prior`: the bug-class discovery should hunt for this threat —
  **same value set as §3a**. Inherit the §3a value for the subsystem this
  threat's `surface` lives in; use `none` for an ordinary taint threat with no
  special bug-class lens. **This is what discovery reads to select its detection
  lens** — get it right for arithmetic / logic-state threats.
- `asset`: Which asset(s) from §2 this threat compromises.
- `impact` — {`low`, `medium`, `high`, `critical`, `existential`}.
- `likelihood` — {`very_rare`, `rare`, `possible`, `likely`, `almost_certain`}.
- `status` — {`unmitigated`, `partially_mitigated`, `mitigated`, `risk_accepted`}.
- `controls`: Current mitigations, or `none`. **When a control is code- or
  config-based** (a feature flag, an internal-only IP check, a CSRF/auth guard, a
  framework escape default, a deploy/middleware setting), **cite its `file:line`**
  so a downstream verifier can confirm-or-refute it at that exact spot. If a
  recorded control has no locatable site, append `(unverified)`.
- `evidence`: CVE IDs, issue links, pentest finding IDs, or git commit hashes
  that **instantiate** this threat. May be empty. **Evidence raises likelihood;
  it is not the threat.**

Sort the table by (impact, likelihood) descending so the top rows are the
priorities.

After the table (and only after it — the `^## 4\. Threats$`-then-table contract
must hold), include three diagrams referencing threats by their stable `T<n>`
ids:
- A **threat-to-component map** (mermaid `graph`) linking each threat to the §1
  component(s) and §3 entry point(s) it traverses.
- A **risk matrix** (mermaid `quadrantChart`) plotting each threat by likelihood
  (x) and impact (y).
- An **attack tree** (mermaid `graph`) with at least three top-level attacker
  goals and the concrete exploit paths — chaining threats by id — beneath each.

#### STRIDE coverage

A **lens over the threats above, not a second enumeration.** Use the six STRIDE
categories as a completeness check: every threat in the table maps to at least
one category, and every category either maps to ≥1 threat or is explicitly marked
"no threat identified" with a one-line reason. **Do not introduce new threats
here** — if STRIDE surfaces a gap, add a `T<n>` row to the table above and
reference it. Reference threats by stable id only.

Map every category as a bullet:

- **S — Spoofing** (assuming another identity): `T<n>, …` | `no threat identified — <why>`
- **T — Tampering** (unauthorized modification of data): …
- **R — Repudiation** (denying an action; gaps in audit logging): …
- **I — Information disclosure** (leaking data across a boundary): …
- **D — Denial of service** (resource exhaustion, missing limits): …
- **E — Elevation of privilege** (gaining higher access): …

Follow the bullets with a **STRIDE overview diagram** (mermaid `graph`) mapping
each category to the §1 component(s) and threat id(s) it affects.

### 5. Deprioritized

| threat | reason |
|---|---|

Threats considered and explicitly parked. Common reasons: out of scope, actor not
in threat model, asset not present, risk accepted by owner. Discovery will
**suppress findings** matching deprioritized rows.

### 6. Open questions

Bullet list. Things this skill could not determine from the code alone —
candidates for owner interview, deeper code review, or a discovery partition
aimed at resolving the question.

### 7. Provenance

```markdown
- mode: bootstrap (derived from code only) | interview (owner-driven) | bootstrap-then-interview
- date: YYYY-MM-DD
- target: <path or repo url @ commit>
- inputs: <design doc path | --vulns path | "none">
- owner: <name, for interview> | <unset, for bootstrap>
```

### 8. Recommended mitigations (optional, additive)

| mitigation | threat_ids | closes_class | effort |
|---|---|---|---|

Each row is **one class-level control**, not a per-finding patch — a mitigation
that closes or materially shrinks an entire threat cluster regardless of which
instance is found next.

- `mitigation`: imperative, one line ("sandbox the decoder process",
  "parameterized queries everywhere", "drop pickle for json", "enable CSP
  default-src 'self'").
- `threat_ids`: comma-separated §4 ids (e.g., `T1,T3`) this mitigation covers.
- `closes_class` — {`yes`, `partial`}.
- `effort` — {`S`, `M`, `L`}.

**A ceiling constant is NOT a mitigation (BINDING).** A `closes_class:yes` row
must be an actual *control* — something that detects, blocks, or neutralizes the
attack (a sanitizer, a sandbox, parameterized queries, constant-time compare, a
real bounds *check* that rejects). A **limit constant** — `MAX_*`, a size cap, a
clamp, a buffer dimension — is an **attack parameter, not a defense**. **Never**
list a limit constant as a mitigation, and never let one set `status: mitigated`
on a §4 threat. A bounds *check that rejects* is a control; a bound the code
*trusts* is not.

Row IDs are implicit by position (`M1` = first row, `M2` = second, …) so that
findings may cite `<mitigation_referenced>M<n></mitigation_referenced>`. Like
threat IDs, **stable**: do not renumber when rows are removed; instead replace
the cell with `(retired)`.

---

## Step 3 — Scoring guide

### Impact

| value | means |
|---|---|
| `low` | Nuisance; no data or availability loss. |
| `medium` | Limited data exposure or degraded availability for some users. |
| `high` | Significant data exposure, integrity loss, or full availability loss. |
| `critical` | Full compromise of a primary asset (RCE, auth bypass, data exfil at scale). |
| `existential` | Compromise threatens the organization's continued operation. |

### Likelihood

| value | means |
|---|---|
| `very_rare` | Requires nation-state resources or an unlikely chain of preconditions. |
| `rare` | Requires significant skill and a non-default configuration. |
| `possible` | A motivated attacker with public tooling could plausibly do this. |
| `likely` | The attack surface is reachable and the technique is well known; prior evidence exists in this or similar systems. |
| `almost_certain` | Actively exploited in the wild, or trivially automatable against the default configuration. |

Evidence (past CVEs in the same surface, pentest findings, public exploit code)
moves likelihood **up**. Existing controls move it **down**. Score the
**residual** likelihood after current controls.

---

## Writing guidelines

- **Be specific, not generic.** Every §4 row that names a code surface must cite
  a real file, function, or endpoint discovered via the graph queries. "the
  `create_user` function at `api.py:21` interpolates user input into a raw SQL
  string" beats "the application may be vulnerable to SQLi".
- **Threats survive patches.** Don't write rows that disappear when one bug is
  fixed. "Buffer overflow in `parse_header()`" is a finding, not a threat; the
  threat is "RCE via malformed input parsing".
- **Stable IDs are load-bearing.** Once a row is assigned `T3`, do not reuse that
  ID for a new row even if `T3` is deleted.
- **Ground in the MCP data.** The route list, function inventory, and data model
  must come from `mcp__armis_code_mcp_stage__*` queries — not assumptions.
- **Backtick every code/payload fragment (markdown output safety, BINDING).**
  Backtick every code/payload/path/identifier — including inside the §2–§8 **table
  cells** — and escape a literal `|` in a cell as `\|`; an unescaped angle-bracket
  fragment renders as live HTML and can truncate the document. Diagrams are the
  one exception — they stay inside a ```mermaid fence. Before declaring the file
  written, scan for `<`+letter outside backticks and fix any hit.
- **No emojis** unless the user asks for them.

---

## Example §4 (excerpt)

```markdown
## 4. Threats

| id | threat | actor | surface | bug_class_prior | asset | impact | likelihood | status | controls | evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| T1 | Remote SQL injection leading to data exfiltration | remote_unauth | /user, /search HTTP routes | injection-taint | customer_data | high | likely | unmitigated | none | |
| T2 | Reflected XSS via comment rendering despite sanitizer | remote_unauth | /comment HTTP route | injection-taint | session_integrity | medium | likely | partially_mitigated | `sanitize_html` (broken) `utils.py:16`; CSP off `settings.py:44` | |
| T3 | OS command injection via thumbnail filename | remote_unauth | /thumb HTTP route | injection-taint | host_process | critical | possible | unmitigated | none | |
| T4 | Remote DoS/logic corruption via signed TCP-sequence overflow flipping an accept/reject branch | remote_unauth | TCP input path | arithmetic-logic-state | connection_state | high | possible | unmitigated | none | |
```

T1 stays in the model after every SQLi instance is patched: attackers will still
send untrusted input to the data layer. Each instance is **evidence** the surface
is fertile, not the threat itself.
