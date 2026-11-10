# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.7.0] — 2026-11-10

A knowledge-refresh release: the eight-tool read-only surface is unchanged. The
docs tools now serve `exoscale-connector` 0.8.0's reference bundle.

### Changed

- **Connector floor raised to `>=0.8.0`** (from `>=0.7.0`, skipping 0.7.1 and
  0.7.2). The bundle the docs tools serve gains the pages for everything added
  since 0.7.0: VPC subnet address pinning, about forty instance, snapshot,
  template, security-group, elastic-IP, pool, DNS, SKS and load-balancer
  operations, and DBaaS migration, PostgreSQL connection pools, the Kafka,
  OpenSearch and Valkey ACLs and the per-engine user options. The 0.8.0 DBaaS
  pages were verified live against the API on five engines, except for two
  operations (`check_migration`, `reveal_kafka_connect_password`) (design §20).
- **Breaking (`list_templates` output key):** `application-consistent-snapshot-enabled`
  is now returned as `application_consistent_snapshot_enabled`. Connector
  0.7.2 types it, `maintainer` and `zones` on its `Template` model; before, they
  passed through as untyped API fields under their API names. Advisor 0.6.0
  already showed the new key when run on connector 0.7.2 or later; the 0.8.0
  floor makes it the same for everyone. The snake_case key matches every other
  typed field (for example `password_enabled`).

### Not adopted

- No connector release since 0.7.0 adds a client, and the new methods are
  either writes or reads scoped to one of the account's own resources (such as
  the `get_*` and `reveal_*` methods, `check_upgrade`, `list_valkey_users`), so the
  catalogue-only, list-only rule (design §3) adds no tool.

## [0.6.0] — 2026-11-02

A maintenance release: the eight-tool read-only surface is unchanged. The docs
tools now serve `exoscale-connector` 0.7.0's reference bundle, whose VPC and KMS
pages were verified live against the API, and the toolchain is locked down. One
breaking change: the minimum supported Python is now **3.11**.

### Changed

- **Breaking:** the minimum supported Python is now **3.11** (was 3.10, which
  reached end-of-life in October 2026), matching `exoscale-connector`. CI tests
  3.11 and 3.14. Stay on 0.5.x for Python 3.10.
- **Connector floor raised to `>=0.7.0`** (via `>=0.6.2`). The docs tools serve
  the connector's packaged reference, and 0.7.0's VPC and KMS pages were
  verified live against the API. The 0.6.x pages showed a VPC route target the
  API rejects and KMS rotation and data-key calls that fail. 0.6.1 also lists
  zones without request signing, so `list_zones` no longer fails with 403 for
  API keys whose IAM role does not grant the zone endpoint. The catalogue
  clients the advisor wraps are unchanged, so tool output is unchanged
  (design §18, §19).
- **The lint gate is now a repo decision, not an upstream default.**
  `pyproject.toml` gained `[tool.ruff.lint] select` and the dev extra pins
  ruff (now `==0.17.3`). Previously neither existed: `ruff>=0.4` let CI install
  the newest release, so when 0.16 enabled pyupgrade rules 0.15 did not, the
  Lint step began failing on branches containing no Python at all. The selected
  set (`E4,E7,E9,F,UP,I,B,SIM,RUF`) is what the codebase already satisfies, and
  ruff upgrades now arrive as reviewable Dependabot PRs. Line length (E5) is
  deliberately not enforced — revisit alongside adopting `ruff format`.
- **`mypy` pinned** (now `==2.4.1`; was `>=1.8`) — the same floating-toolchain
  risk as ruff: CI was resolving mypy 2.x off a 1.8 floor, and a local venv had
  drifted from CI. Both checkers are now version-locked, so Lint and Type-check
  mean the same thing locally and in CI, and both move only via a reviewed
  Dependabot PR.

### Removed

- **`Live smoke` workflow (`.github/workflows/live-smoke.yml`)** — the
  manual-dispatch job that ran `tests/integration` against a real account was
  never executed once since it was added, and could not be: it reads
  `EXOSCALE_API_KEY` / `_SECRET` / `_ZONE` from repository secrets, and none are
  configured (the `pypi` environment holds no secrets either, and release
  publishing uses OIDC trusted publishing rather than a token). A workflow that
  cannot run implies coverage that does not exist, so it is gone. **The gated
  live smoke test itself is unchanged** — `tests/integration` still runs
  read-only behind `EXOSCALE_RUN_LIVE_TESTS=1` with credentials injected from
  the environment (README "Developer guide", design §9.4). Restore the workflow
  if and when a least-privilege read-only key is provisioned.

### Security

- **Dependabot now watches the SHA-pinned actions** (`.github/dependabot.yml`,
  weekly). Pinning every action to a full commit SHA (#13) makes the pins
  immutable, which also means they never pick up an upstream security fix on
  their own; Dependabot closes that loop by raising the SHA and its trailing
  version comment. The `pip` ecosystem is watched too, with
  **`exoscale-connector` explicitly ignored** — its floor is raised only through
  the triage flow (`connector-watch.yml` → `/connector-release-triage`), never as
  an automatic dependency bump (design §16). `mcp` 2.x is likewise ignored: its
  `<2` cap is deliberate, and Dependabot's attempts to widen it to `<3` (#25,
  #29) failed CI — mcp 2.x moves `FastMCP` and renames the `ToolAnnotations`
  fields that `test_no_mutation.py` asserts on, so adopting it is a migration to
  vet, not a bump to merge. The rule ignores `mcp >=2` by version, because
  Dependabot does not classify a range widening as a major update.

### Not adopted (deliberate scope)

- Connector 0.7.0's new clients were reviewed against the catalogue-only rule
  (design §3) and **left out**. DBaaS logs, metrics and databases, the SKS
  deprecated-resources check and the organization IAM policy all read or change
  *account* resources, not the platform catalogue, and several have write
  methods. The DBaaS CA certificate is account-wide, not a catalogue either.
  Their reference pages reach the docs tools anyway.

## [0.5.0] — 2026-07-09

A knowledge-refresh release: the eight-tool read-only surface is unchanged, but
the docs tools now serve the richer reference bundle shipped by
`exoscale-connector` 0.6.0. Because the bundle is read from the installed
connector at runtime (design §4), the four new asset-type pages appear through
`search_docs` / `get_asset_page` / `list_asset_types` with no advisor code change
— raising the floor is what guarantees them to every consumer.

### Changed

- **Connector floor raised to `>=0.6.0`** — 0.6.0 adds live-verified reference
  pages for **vpc**, **kms**, **deploy-target**, and **event** to the packaged
  `_skill/reference.md`, plus richer model detail (typed security-group rule
  references, a DBaaS `version` field, SKS `nvidia_mig_profiles`). The advisor's
  docs tools surface all of it automatically. 0.6.0 is purely additive with no
  breaking changes, so no live tool changed and the tool surface is unchanged
  (design §17).

### Not adopted (deliberate scope)

- 0.6.0's new read-only clients were reviewed against the catalogue-only rule
  (design §3, D2) and **left out**: `VpcClient` and `KmsKeyClient` list *account*
  resources (not the platform catalogue), `EventClient` is an audit log, and
  DBaaS `get_settings` / `get_acl_config` are `get`-verb / instance-scoped. A
  `list_deploy_targets` tool was considered and declined — deploy targets are
  org-scoped and empty for most accounts, so the new **deploy-target doc page**
  covers the topic better than a mostly-empty live tool.

## [0.4.0] — 2026-06-12

A maintenance and supply-chain hardening release: the eight-tool read-only
surface is unchanged. Adds a published stability policy, moves publishing to PyPI
Trusted Publishing with build attestations, SHA-pins every CI action, tests
against the dependency floor, and ships on the hardened `exoscale-connector`
0.5.0.

### Added

- **Stability & compatibility policy** (design §16, linked from the README):
  defines the public API as the tool surface (tool names + their contracts),
  everything else as internal, what `0.x` version bumps mean, the
  `exoscale-connector` floor guarantee, and a deprecate-then-remove procedure. It
  leans on the existing doc-parsing test rather than a parallel tool list (#15).

### Changed

- **Connector floor raised to `>=0.5.0`** — the live `list` tools now run on the
  connector's 0.5.0 HTTP resilience hardening (connection-level retries on
  idempotent requests). No advisor API changed; the tool surface is unchanged.
- **Publishing moved to PyPI Trusted Publishing (OIDC).** Releases now publish on
  a published GitHub Release via OIDC with no stored API token, and attach PEP 740
  build attestations (provenance). The tag → Release → publish flow is documented
  in the README (#13).
- **CI tests the dependency floor.** The suite now runs against both the declared
  `exoscale-connector` floor (parsed from `pyproject.toml`, not duplicated) and the
  latest release, so a floor set too low fails the build (#15).

### Security

- **All GitHub Actions are pinned to commit SHAs** across every workflow (CI,
  release, live-smoke), replacing mutable tag and branch refs (#13).

## [0.3.0] — 2026-06-12

Adds an eighth read-only tool surfacing live SKS Kubernetes versions, and makes
the design doc a mechanical record of the tool surface. Still read-only by
construction.

### Added

- `list_sks_versions(zone=None)` — live list of the Kubernetes versions a new SKS
  cluster may be created with, wrapping the connector's read-only
  `SksClusterClient.list_versions`. Lets an agent ground a cluster's `version`
  against what the API accepts instead of hardcoding a literal (#9).
- A structural test that parses the design doc's tool tables and asserts their
  union equals the registered tool set, so undocumented tool additions (or stale
  tables) fail the build.

### Changed

- Bumped the `exoscale-connector` floor to `>=0.4.0`, the release that first
  exposes `SksClusterClient.list_versions` (#9).
- Design doc records the post-v1 surface in per-release addenda (§14, §15) with a
  forward-pointer from §3; README documents the new tool and its wording was
  tightened.

## [0.2.0] — 2026-06-12

Grows the read-only tool surface from five to seven and smooths the live-tool
experience, all driven by findings from real-world advisor sessions. Still
read-only by construction.

### Added

- `list_asset_types()` — the asset-type index (each page's slug + heading) so
  agents can discover valid `asset_type` values up front instead of probing
  `get_asset_page` for a miss (#4).
- `list_dbaas_plans(zone=None)` — live managed-database service types and plans,
  wrapping the connector's read-only `DBaaSServiceClient.list_service_types` (#7).
- Derived human-readable sizes on live tools: `memory_gib` on instance types and
  `size_gib` on templates, alongside the raw byte fields (#6).
- README **Example use cases** section — a graduated ladder from a
  credential-free docs lookup to reviewable infrastructure-code generation (#10).

### Changed

- Live tools now translate missing/invalid credentials (connector `ConfigError`
  and auth `APIError`) into a clear, actionable message instead of a raw
  traceback; the docs tools keep working without credentials (#5).
- Richer server `instructions` (which tools need credentials, the connector
  install info, and an explicit no-pricing note) and an updated README tool
  table plus guidance for getting credentials into the MCP server launch env (#5).

## [0.1.0] — 2026-06-11

First public release: a read-only Exoscale advisor MCP server.

### Added

- **Docs tools** sourced from the packaged `exoscale-connector` reference bundle
  (zero duplication):
  - `search_docs(query)` — keyword-ranked sections from the reference.
  - `get_asset_page(asset_type)` — the full reference page for one asset type.
- **Live catalogue tools** (read-only, `list` verb only):
  - `list_zones()`, `list_instance_types(zone)`,
    `list_templates(zone, visibility="public")`.
- **stdio MCP server** registering exactly these five tools, each annotated
  read-only / non-destructive, with an `exoscale-mcp-advisor` console script
  (`uvx`-runnable).
- **Read-only by construction**: a structural test asserts the registered tool
  set is exactly the five read-only tools — adding any tool fails the build.
- **Four-layer test suite**: structural no-mutation, mocked-connector unit
  tests, protocol-level tests over the MCP in-memory transport, and an opt-in,
  read-only live smoke (`EXOSCALE_RUN_LIVE_TESTS=1`).

[Unreleased]: https://github.com/ralle-lang/exoscale-mcp-advisor/compare/v0.7.0...HEAD
[0.7.0]: https://github.com/ralle-lang/exoscale-mcp-advisor/releases/tag/v0.7.0
[0.6.0]: https://github.com/ralle-lang/exoscale-mcp-advisor/releases/tag/v0.6.0
[0.5.0]: https://github.com/ralle-lang/exoscale-mcp-advisor/releases/tag/v0.5.0
[0.4.0]: https://github.com/ralle-lang/exoscale-mcp-advisor/releases/tag/v0.4.0
[0.3.0]: https://github.com/ralle-lang/exoscale-mcp-advisor/releases/tag/v0.3.0
[0.2.0]: https://github.com/ralle-lang/exoscale-mcp-advisor/releases/tag/v0.2.0
[0.1.0]: https://github.com/ralle-lang/exoscale-mcp-advisor/releases/tag/v0.1.0
