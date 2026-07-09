---
name: connector-release-triage
description: >-
  Triage a new upstream exoscale-connector release for the exoscale-mcp-advisor:
  decide what (if anything) the advisor must adopt, then ship it. Use when a
  `connector-release` issue is filed by the weekly watcher, when asked to "check
  the upstream connector", or after any new exoscale-connector version is
  published. Encodes the read-only/catalogue-only decision framework and the
  release flow.
---

# Connector release triage

The `exoscale-mcp-advisor` is a **read-only** MCP server that stands on
`exoscale-connector`. This skill turns "a new connector was released" into a
decision and a shipped advisor release. It is the repeatable form of the manual
0.6.0 triage.

Optional argument: the upstream tag to triage (e.g. `v0.7.0`). If omitted, use
the latest upstream release.

## The two things that matter (internalise these first)

1. **Docs are auto-forward-compatible.** `docs.py` reads the connector's
   packaged `_skill/reference.md` from the *installed* connector at runtime, so
   `search_docs` / `get_asset_page` / `list_asset_types` gain any new asset-type
   pages the moment a newer connector is installed — **no advisor code change**.
   Raising the declared floor in `pyproject.toml` is what turns "surfaces if a
   new enough connector happens to be installed" into a guarantee for every
   consumer.
2. **Live tools are catalogue-only, list-verb-only.** They answer "what does the
   platform offer" (zones, instance types, templates, DBaaS plans, SKS versions)
   — decisions **D1** (advisor, not operator) and **D2** (catalogue discovered,
   never hardcoded) in `docs/mcp-advisor-design.md` §1/§3. A new connector client
   becomes a new live tool **only if** it is catalogue-shaped. It does **not** if
   it lists the account's own resources, is an audit/event log, or is a `get`
   verb rather than `list`.

## Step 1 — establish the delta

- Current floor: parse `pyproject.toml` (`grep -oE '"exoscale-connector>=[0-9.]+'`).
- New version + notes: `gh release view <tag> --repo ralle-lang/exoscale-python-connector`
  (omit `<tag>` for latest). Read the CHANGELOG section, note **breaking
  changes** especially.

## Step 2 — reconnaissance (delegate for depth)

Investigate the upstream repo at the release tag (via `gh api .../contents?ref=<tag>`
— do **not** clone). A subagent is worth it. Answer:

- **New client classes** and, for each, their public **read-only** methods
  (`list`, `list_*`, `get`) and signatures (watch for non-standard ones, e.g. an
  `EventClient.list(from_, to, zone)` with no `labels`).
- **New read-only methods/fields** on clients the advisor already wraps
  (SKS, DBaaS, compute, zone/template/instance-type).
- **The packaged bundle**: which asset-type pages does `_skill/reference.md`
  contain at this tag? (This is what the docs tools will surface.)
- **Breaking / renamed / removed** public symbols the advisor could wrap.

## Step 3 — decide, per addition

| Addition kind | Decision |
|---|---|
| New asset-type doc page(s) in the bundle | **Adopt for free** via the floor bump — no code. |
| New read-only client that lists **platform catalogue** options | Candidate live tool — weigh utility (is it non-empty for typical accounts?). |
| New read-only client that lists the **account's own resources** (VPCs, keys, instances…) | **Decline** — resource inventory, not catalogue (D2). |
| Audit/event log client | **Decline** — telemetry, not catalogue. |
| New `get`-verb / instance-scoped method | **Decline** — breaks the list-only rule (§3). |
| Enriched fields on already-wrapped models | Usually **no change** — `_dump` passes new fields through. |
| Breaking change to a symbol the advisor wraps | **Must** address before bumping the floor. |

When unsure whether to add a live tool, prefer **declining with the doc page**
as the coverage, and record the rationale — an org-scoped/mostly-empty `list`
adds less value than its doc page (this is exactly why `list_deploy_targets` was
declined in 0.6.0). Surface genuinely ambiguous scope calls to the user.

## Step 4 — implement the chosen path

**Always (any adoption):**
- `pyproject.toml`: raise the `exoscale-connector` floor + extend the dependency
  comment block explaining what the new floor buys.
- `src/exoscale_mcp_advisor/__init__.py`: bump `__version__`. A floor raise is a
  **MINOR** (design §16).
- `CHANGELOG.md`: new version entry (Changed: floor bump; add a "not adopted"
  note listing declined clients and why) + update the link refs at the bottom.
- `docs/mcp-advisor-design.md`: add the next `§N` addendum (floor bump, the
  newly-surfaced pages, and a table of reviewed-but-declined clients). If the
  tool surface is unchanged, say so — the doc-parsing guard (§6) keys off the
  tool tables, so an addendum with no tool table is safe.

**Only if adding a live tool** (also):
- `server.py`: add the name to `READ_ONLY_TOOL_NAMES` and register the tool with
  `_LIVE_ANNOTATIONS`.
- `catalogue.py`: add the `list_*` wrapper over the connector `list` method.
- `docs/mcp-advisor-design.md`: add the tool to the addendum's tool **table**
  (the structural test asserts the doc tables' union equals the registered set).
- Tests: extend `tests/unit` (catalogue mock, protocol) to cover it.

## Step 5 — verify (mandatory before shipping)

- Upgrade the connector in the venv (needs the user's OK — it's a `pip install`):
  `.venv/bin/pip install --upgrade "exoscale-connector>=<newfloor>"`.
- Confirm the new pages surface:
  `.venv/bin/python -c "from exoscale_mcp_advisor.docs import default_bundle as b; print(b().asset_types)"`.
- `.venv/bin/python -m pytest tests/unit -q` → all green.
- `.venv/bin/ruff check src tests` and `.venv/bin/mypy src` → clean.

## Step 6 — ship

The advisor releases via a branch → PR → GitHub Release → PyPI (OIDC) flow.
**Merging a PR does not publish; publishing a GitHub Release does.**

1. `git checkout -b release/vX.Y.Z`, commit atomically (Conventional Commits,
   **no `Co-Authored-By` trailer** per the user's rules). Ask before pushing.
2. Push, open a PR to `main`, wait for CI green, squash-merge.
3. Sync `main` (`git pull --ff-only`), then
   `gh release create vX.Y.Z --title "vX.Y.Z" --generate-notes`.
4. The published Release triggers `.github/workflows/release.yml`
   (`pypa/gh-action-pypi-publish` via OIDC trusted publishing) — confirm the run
   succeeds and the version is live on PyPI.
5. Close the triage issue with a pointer to the release.

## Notes

- Pricing is permanently out of scope (Exoscale has no pricing API) — never add
  a pricing tool or imply a price.
- The auto-memory file `connector-followups-from-advisor.md` tracks the running
  history of connector↔advisor decisions — update it with each triage outcome
  (especially *why* a client was declined, since that recurs every release).
