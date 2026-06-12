# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.3.0]: https://github.com/ralle-lang/exoscale-mcp-advisor/releases/tag/v0.3.0

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

[0.2.0]: https://github.com/ralle-lang/exoscale-mcp-advisor/releases/tag/v0.2.0

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

[0.1.0]: https://github.com/ralle-lang/exoscale-mcp-advisor/releases/tag/v0.1.0
