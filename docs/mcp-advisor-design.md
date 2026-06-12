# Design — read-only advisor MCP server

> **Status:** design proposal (issue #7, Advisor milestone, rung 3).
> This document is reviewed in the connector repo, then copied to the new
> `exoscale-mcp-advisor` repository as its founding design document.
> Implementation is tracked by issues in that new repo, not here.

This is a design + bootstrap-decision document. It settles *what* the server
is and *how* it is built before any code is written, so the structural
guarantees (read-only by construction, zero knowledge duplication) are
designed in rather than bolted on.

---

## 1. Purpose & framing

The advisor MCP server exposes the Exoscale knowledge bundle and *list-only*
live catalogue queries to an MCP-capable agent. It lets an agent answer
questions like _"what instance types exist in `at-vie-1` right now, and how do
I create a security group with the connector?"_ — combining the live
catalogue with the verified docs — **while being structurally incapable of
mutating any cloud resource.**

This is the direct application of the project's two standing decisions:

- **D1 (Advisor, not operator):** the AI layer targets the *learning* path,
  not the execution path. The server's job ends at the moment of
  understanding; it produces explanations and reviewable code, never
  side effects. Read-only is therefore a structural property, not a policy.
- **D2 (Catalogue knowledge is discovered, never hardcoded):** the live
  catalogue tools resolve against the API at call time. The server hardcodes
  no zones, instance types, or templates.

It lives in a **separate repository** because it adds an MCP-framework
dependency and a different risk/release profile, and the connector's
"requests + pydantic only" promise must hold. A concrete consequence: the
official `mcp` Python SDK requires Python ≥3.10, while the connector targets
≥3.9. Keeping the SDK out of the connector preserves that floor.

---

## 2. Repository

- **Name:** `exoscale-mcp-advisor` (PyPI distribution: `exoscale-mcp-advisor`).
- **Visibility:** public (intended for PyPI / `uvx` distribution).
- **Relationship to the connector:** depends on `exoscale-connector` as a
  normal PyPI dependency. It stands on rung 2 — it consumes the packaged
  knowledge bundle rather than re-deriving it.

```
exoscale-mcp-advisor  (new repo, public)
        │  depends on (PyPI)
        ▼
exoscale-connector    (this repo)
        ├── live catalogue clients  → list_zones / list_instance_types / list_templates
        └── _skill/reference.md     → search_docs / get_asset_page
```

---

## 3. Tool surface (v1)

> **Current surface:** v1 shipped five tools; the surface has grown since. The
> post-v1 additions are recorded in the per-release addenda — §14 (v0.2.0) and
> §15 (v0.3.0) — which carry their own tool tables. §3 below is kept as the
> frozen v1 record. The structural no-mutation test (§6) parses every tool table
> in this document and fails the build if their union drifts from the registered
> tool set, so "the docs reflect the code" is mechanical, not a promise.

Five tools, two groups. Nothing else in v1.

### Docs tools (offline, sourced from the connector bundle)

| Tool | Signature | Returns |
|------|-----------|---------|
| `search_docs` | `search_docs(query: str)` | Ranked matching sections from `reference.md` (heading + snippet + section id). |
| `get_asset_page` | `get_asset_page(asset_type: str)` | The full reference section for one asset type (e.g. `security-group`, `dns`, `dbaas`). |

### Live catalogue tools (read-only, list verb only)

| Tool | Signature | Backing connector call |
|------|-----------|------------------------|
| `list_zones` | `list_zones()` | `ZoneClient(...).list()` |
| `list_instance_types` | `list_instance_types(zone: str)` | `InstanceTypeClient(...).list()` |
| `list_templates` | `list_templates(zone: str, visibility: str = "public")` | `TemplateClient(...).list(...)` |

Every live tool calls a connector `list()` and nothing else. No `get`/`create`/
`update`/`delete` wrappers are exposed in v1 — `list` is sufficient to answer
"what exists" and keeps the read-only surface trivially auditable.

---

## 4. Knowledge source — zero duplication

The docs tools read the packaged bundle that the connector already ships:
`exoscale_connector/_skill/reference.md` (and its `SKILL.md` advisory header).
The server locates it via the installed package, e.g.
`importlib.resources.files("exoscale_connector") / "_skill" / "reference.md"`.

Consequences:

- **No copy of the docs lives in this repo.** The knowledge is exactly as
  current as the installed `exoscale-connector` version. Upgrading the
  dependency upgrades the advisor's knowledge — nothing to regenerate here.
- The connector's existing sync test (`tests/unit/test_llms_txt.py`)
  guarantees the bundle matches the code on every connector CI run, so the
  advisor inherits a verified, in-sync source for free.
- This is rung 3 standing on rung 2, exactly as the roadmap intends.

The `reference.md` headings (`#### client \`SecurityGroupClient\``, asset-type
pages, field tables) are the index `search_docs` and `get_asset_page` parse.

---

## 5. Search

Plain section / keyword search over the bundle. The bundle is split into
sections by its markdown headings; a query ranks sections by keyword overlap
(case-folded, simple term frequency, heading matches weighted higher) and
returns the top matches.

- **No embeddings, no vector store, no runtime AI.** The consumer *is* the
  LLM; the server's job is retrieval, not reasoning.
- Deterministic and dependency-light — pure-Python, testable without a model.
- If retrieval quality proves insufficient later, a smarter ranker is an
  internal change behind the same tool signatures (not a v1 concern).

---

## 6. Read-only by construction

Read-only is enforced *structurally*, reusing this project's proven
"enforcement-point test" trick — the same idea as the connector's
artifact-sync test that fails CI whenever the committed bundle drifts from the
code.

A unit test enumerates every tool registered on the MCP server and asserts the
set is exactly the five approved read-only tools (or, more strongly, that no
registered tool's backing call is anything other than a connector `list`).
**Registering any mutation tool fails the build.** The guarantee is mechanical
and survives refactors — a future contributor cannot add a `create_instance`
tool without a red test forcing the conversation.

This is defense in depth layer one (the code literally cannot mutate); §7 adds
layer two (the credentials cannot either).

---

## 7. Live-call safety — least privilege

The live catalogue tools need real credentials. Defense in depth:

1. **Structural (the code):** only `list` calls exist (§6).
2. **Credential (the key):** the README prescribes a least-privilege IAM key —
   default-deny, then allow only `list`/`get` operations. The policy is
   generated with the connector's own `iam_expr` / `IAMPolicy` helpers (see
   `docs/iam-policy-cookbook.md`), e.g. the existing
   `IAMPolicyRule.allow("operation in ['list-instances', 'get-instance']")`
   pattern extended to the catalogue operations. Even if a mutation call
   somehow reached the API, the key would reject it.
3. **Credential handling:** env-only
   (`EXOSCALE_API_KEY` / `EXOSCALE_API_SECRET` / `EXOSCALE_ZONE`), vault-
   injected at startup. Never hardcoded, never read from files, never passed
   as CLI args — same rule the connector skill already states.

---

## 8. Framework & distribution

- **Framework:** the official `mcp` Python SDK.
- **Transport:** stdio for v1. HTTP is a non-goal until a concrete consumer
  needs it (§9).
- **Distribution:** published to PyPI as `exoscale-mcp-advisor`, runnable with
  `uvx exoscale-mcp-advisor` — no clone/install step for consumers.
- **Python floor:** ≥3.10 (the `mcp` SDK requirement; the new repo is free to
  set this since it does not share the connector's ≥3.9 promise).

---

## 9. Testing — four layers

Mirrors this repo's tiered, opt-in live-test discipline.

1. **Structural no-mutation test** (§6): the set of registered tools is exactly
   the approved read-only set. Runs always, no credentials.
2. **Mocked-connector unit tests:** each tool against a mocked connector —
   `search_docs` ranking, `get_asset_page` lookup/not-found, the live tools'
   request-shaping and error handling. No network.
3. **Protocol-level tests:** drive the server through the `mcp` SDK's
   in-memory client transport — list tools, call each, assert schemas and
   results. Proves the MCP wiring, still no network.
4. **Gated live smoke (Tier-0 style):** one opt-in test that lists zones /
   instance types / templates against a real account, default-skipped behind
   an env flag (same `EXOSCALE_RUN_LIVE_TESTS=1` pattern as
   `tests/integration/conftest.py` here). Zone `at-vie-1`. Read-only, so safe
   anywhere.

---

## 10. Non-goals (written down)

- **No mutation tools, ever** — by construction (D1, §6).
- **No RAG / embeddings / runtime AI** — plain keyword search (§5).
- **No HTTP transport in v1** — stdio only until a concrete consumer exists.
- **No catalogue caching** beyond, at most, a simple optional TTL — staleness
  is the enemy of a "what exists right now" tool.
- **No re-derivation of connector knowledge** — the bundle is the single
  source (§4).

---

## 11. Bootstrap plan (Phase 2)

What issue #7 delivers once this design is approved:

- Create the public `exoscale-mcp-advisor` repository.
- Commit this design doc as the founding document.
- README skeleton with the four mandatory sections (general / user / admin /
  developer).
- CI skeleton (lint + test; the structural no-mutation test green from day one
  even before tools exist).
- MIT license.
- **Vault:** an Infisical project for the live-smoke credentials (the global
  "init vault" workflow) — pending user go-ahead at bootstrap time.

Issue #7 closes when the repo exists with design doc + README skeleton + CI
skeleton + license. **Implementation becomes new issues in the new repo.**

## 12. Connector-repo follow-ups (Phase 3, small)

- Link rung 3 in `docs/roadmap.md` to the new repo / its design doc.
- Extend the README "AI tooling" bullet to mention the advisor server.

---

## 13. Decisions for the user

Recommendations above are the agreed defaults; these remain explicit user
calls at bootstrap:

- **Repo name** — `exoscale-mcp-advisor` (agreed) vs. an alternative.
- **`uvx`/PyPI dist name** — defaulting to match the repo name.
- **Vault init** — whether to run the "init vault" workflow now or defer until
  the live smoke test is actually written.

---

## 14. Addendum — v0.2.0 tool surface

> Added 2026-06-12. Sections 1–13 above are the **founding v1 design** and are
> kept verbatim as the historical record; this addendum captures how the surface
> grew in 0.2.0. The design's invariants are unchanged: read-only by
> construction (§6), zero knowledge duplication (§4), `list`-verb-only live
> tools (§3). All changes were driven by findings from real-world advisor
> sessions.

The approved read-only set grew from **five to seven**. The structural
no-mutation test (§6) was updated consciously at each step — the guard goes red
until the approved set is changed on purpose — so the §6 guarantee still holds; it
now asserts "exactly these seven", not "exactly these five".

### New docs tool

| Tool | Signature | Returns |
|------|-----------|---------|
| `list_asset_types` | `list_asset_types()` | The asset-type index — each reference page's slug + heading — so valid `asset_type` values are discoverable without probing `get_asset_page` for a miss. |

### New live catalogue tool

| Tool | Signature | Backing connector call |
|------|-----------|------------------------|
| `list_dbaas_plans` | `list_dbaas_plans(zone: str \| None = None)` | `DBaaSServiceClient(...).list_service_types(...)` |

`list_service_types` is a read verb, consistent with the §3 "list verb only"
rule; `zone` is optional because the endpoint is zone-agnostic, validated like
the other live tools only when supplied.

### Live-tool ergonomics (no surface change)

- **Derived human-readable sizes:** `memory_gib` on instance types and
  `size_gib` on templates, alongside the raw byte fields (agents were
  re-deriving GiB by hand).
- **Credential UX:** missing/invalid credentials (connector `ConfigError`, auth
  `APIError` 401/403) are translated at the MCP boundary into a clear, actionable
  message instead of a raw traceback; the docs tools keep working without
  credentials. The translation lives at the server layer, so the catalogue layer
  still raises raw and its contract (§6 audit seam) is untouched.
- **No pricing, stated explicitly:** the server `instructions` now note the
  catalogue exposes no pricing (use Exoscale's calculator), so agents don't imply
  a cost.

---

## 15. Addendum — v0.3.0 tool surface

> Added 2026-06-12. Like §14, sections 1–13 stay verbatim as the v1 record; this
> captures how the surface grew in 0.3.0. The invariants are unchanged: read-only
> by construction (§6), zero knowledge duplication (§4), `list`-verb-only live
> tools (§3).

The approved read-only set grew from **seven to eight**. The structural
no-mutation test (§6) was updated consciously, and now also parses the tool
tables in this document and asserts their union equals the registered set — so a
new tool that is not documented here fails the build.

### New live catalogue tool

| Tool | Signature | Backing connector call |
|------|-----------|------------------------|
| `list_sks_versions` | `list_sks_versions(zone: str \| None = None)` | `SksClusterClient(...).list_versions(...)` |

`list_versions` is a read verb, consistent with the §3 "list verb only" rule. It
wraps `GET /sks-cluster-version` and returns the Kubernetes versions a new SKS
cluster may be created with, newest-first, as raw strings. The tool lets an agent
ground a cluster's `version` against what the API currently accepts instead of
hardcoding a literal that can be retired upstream. `zone` is optional because the
endpoint is zone-agnostic, validated like the other live tools only when supplied.

It requires `exoscale-connector>=0.4.0`, the release that first exposes
`SksClusterClient.list_versions` (previously only a test fixture resolved SKS
versions, so the connector's public API could not surface them).

## 16. Stability & compatibility policy

> Added 2026-06-12. This is the single source for what "compatible" means; the
> README points here. It introduces no new tool tables, so the doc-parsing guard
> (§6) is unaffected.

This project is pre-1.0 and follows [SemVer](https://semver.org/) with the 0.x
convention.

- **Public API = the tool surface.** The public contract is the set of registered
  MCP tools — their **names** and their **call contracts** (parameters, what each
  parameter means, and the documented shape each tool returns). That set lives in
  exactly one place, `READ_ONLY_TOOL_NAMES` in `server.py`, and is kept in lockstep
  with the tool tables in §3 / §14 / §15 by
  `test_design_doc_tool_tables_match_the_approved_set` (§6). There is no second,
  hand-maintained list to drift.
- **Everything else is internal** and may change in any release: module layout,
  helper functions, the `Catalogue` and `DocsBundle` classes, search-ranking
  internals, the exact wording of error messages, and which `exoscale-connector`
  method backs a given tool.
- **What a version bump means:**
  - **PATCH** (`0.4.x`): bug fixes only — no tool added or removed, no breaking
    change to an existing tool's contract.
  - **MINOR** (`0.x.0`): may add a tool, make a breaking change to an existing
    tool's name or contract, or raise the `exoscale-connector` floor. Pin the
    version if you depend on a specific surface. Pre-1.0 there is **no guarantee
    that minors are free of breaking changes** — that guarantee begins at 1.0.
- **Dependency floor.** The `exoscale-connector` lower bound declared in
  `pyproject.toml` is the single source of truth for the minimum supported
  connector. CI installs and runs the suite against **both** that floor and the
  latest connector (the floor is parsed out of `pyproject.toml`, not duplicated),
  so a floor set too low fails the build mechanically rather than silently.
- **Deprecation procedure.** A tool, or a tool parameter, is removed only after:
  (1) it is marked deprecated in its docstring and in the relevant tool table
  here, in a release where it still works; (2) the deprecation is recorded in
  `CHANGELOG.md`; (3) removal lands no earlier than the next MINOR after the one
  that announced it. A rename is a deprecate-then-remove, never an in-place change.
