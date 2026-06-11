# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
