# exoscale-mcp-advisor

A **read-only** [Model Context Protocol](https://modelcontextprotocol.io) server
that lets an MCP-capable agent learn about Exoscale: search the verified
connector documentation and run **list-only** live catalogue queries (zones,
instance types, templates). It is, by construction, incapable of mutating any
cloud resource.

> **Status: released.** Eight read-only tools, the stdio server, and the
> four-layer test suite (structural no-mutation, mocked-connector,
> protocol-level, gated live smoke) are in place and green; published to PyPI as
> [`exoscale-mcp-advisor`](https://pypi.org/project/exoscale-mcp-advisor/). The
> full design is in [`docs/mcp-advisor-design.md`](docs/mcp-advisor-design.md);
> release history is in [`CHANGELOG.md`](CHANGELOG.md).

It builds on [`exoscale-connector`](https://github.com/ralle-lang/exoscale-python-connector):
the knowledge it serves is read from that package's bundled reference, and the
live queries reuse the connector's read-only `list` clients. Nothing about
Exoscale is hardcoded or duplicated here.

---

## General description

The advisor targets the learning path, not the execution path. An agent can ask
"what instance types exist in `at-vie-1` right now?" or "how do I create a
security group with the connector?" and get live data plus verified docs, while
the server stays structurally unable to create, change, or delete anything.
Infrastructure changes stay the human's job, performed with reviewed, idempotent
code.

Tool surface (see design §3):

| Tool | Credentials | Purpose |
|------|:-----------:|---------|
| `search_docs(query)` | — | Ranked sections from the connector's reference bundle. |
| `get_asset_page(asset_type)` | — | Full reference page for one asset type. |
| `list_asset_types()` | — | The asset-type index (slug + heading) for discovery. |
| `list_zones()` | ✔ | Live list of zones. |
| `list_instance_types(zone)` | ✔ | Live list of instance types (with derived `memory_gib`). |
| `list_templates(zone, visibility)` | ✔ | Live list of templates (with derived `size_gib`). |
| `list_dbaas_plans(zone=None)` | ✔ | Live managed-database (DBaaS) service types and plans. |
| `list_sks_versions(zone=None)` | ✔ | Live list of Kubernetes versions a new SKS cluster may use. |

The three docs tools need no credentials; the five live tools read Exoscale API
credentials from the server's environment (see the User guide). No mutation
tools — ever, by design.

## User guide

The server runs with no clone or install step:

```bash
uvx exoscale-mcp-advisor
```

Or from a source checkout (for development):

```bash
pip install -e .
exoscale-mcp-advisor            # or: python -m exoscale_mcp_advisor
```

It speaks MCP over **stdio**, so it is configured like any other stdio MCP
server in your client. The five live catalogue tools require Exoscale API
credentials in the server's launch environment. They are never passed on the
command line and never read from a file by the app:

```
EXOSCALE_API_KEY=...
EXOSCALE_API_SECRET=...
EXOSCALE_ZONE=at-vie-1
```

Getting them into the server's environment, two common ways:

```bash
# 1) Pass them to the MCP client as it launches the server (Claude Code shown):
claude mcp add exoscale-advisor \
  -e EXOSCALE_API_KEY=... -e EXOSCALE_API_SECRET=... -e EXOSCALE_ZONE=at-vie-1 \
  -- uvx exoscale-mcp-advisor

# 2) Inject from a vault at launch, so no secret is typed or stored in config:
claude mcp add exoscale-advisor -- \
  infisical run --domain http://localhost:8080 -- uvx exoscale-mcp-advisor
```

Use a least-privilege, read-only API key (see the Admin guide). The three docs
tools (`search_docs`, `get_asset_page`, `list_asset_types`) need no credentials;
if the live tools run without credentials they return a clear, actionable error
while the docs tools keep working. The catalogue exposes no pricing, so use
[Exoscale's calculator](https://www.exoscale.com/pricing/) for cost estimates.

## Example use cases

What the advisor is for, from trivial to advanced. Every example is read-only:
the server produces explanations and reviewable code, never a side effect
(design D1). Each rung notes the tools it uses and whether credentials are
needed.

1. **Docs lookup, no credentials.**
   *"Search the Exoscale docs for how to create a security group, then show me
   the full security-group reference page."*
   Uses `search_docs` and `get_asset_page`, with `list_asset_types` to discover
   slugs first.

2. **A single live query.**
   *"What instance types are available in `at-vie-1` right now?"*
   Uses one live tool such as `list_instance_types` or `list_templates`;
   `memory_gib` and `size_gib` come pre-derived, so no manual byte math.

3. **Live and docs synthesis.**
   *"Compare the instance types in `at-vie-1` and recommend one suitable as an
   SKS worker, citing the sizing constraints."*
   Combines a live tool with `get_asset_page` and reasoning; it has no pricing
   data, so cost questions defer to Exoscale's calculator.

4. **Multi-asset design, read-only.**
   *"Design an HA web-app stack in `at-vie-1` (load balancer, web tier, managed
   database), cite the docs for each asset, and don't provision anything."*
   Uses many `get_asset_page` calls plus `list_dbaas_plans` and `list_zones`,
   returning a design and citations rather than a side effect.

5. **Reviewable code generation.**
   *"Generate an `exoscale-connector` script that provisions the stack above,
   with secrets side-loaded from the environment, and I'll run it."*
   The advisor-not-operator pattern: read-only advice plus a script you review
   and run, with the server unable to apply changes itself.

The ladder is the point: a credential-free entry for learning at rung 1, and a
ceiling at rung 5 where the advisor writes the infrastructure code while a human
keeps the keys and the final apply.

## Admin guide

**Least-privilege credentials (defense in depth).** Although the server can only
issue `list` calls, the API key it runs with should also be restricted to
read-only operations, so the key itself cannot mutate anything. Build the IAM
policy with the connector's own `iam_expr` / `IAMPolicy` helpers (default-deny,
then allow only `list`/`get` catalogue operations) — see the connector's IAM
policy cookbook and design §7.

**Credential injection.** Credentials come from the environment, injected at
startup by a vault CLI (e.g. `infisical run -- uvx exoscale-mcp-advisor` in
development; a production vault agent in production). The application never reads
secrets from files and is not coupled to any specific vault provider.

**Security model.** Read-only is enforced on two independent layers: the code
registers only read-only tools (a CI test fails the build if a mutation tool is
ever added), and the credentials are scoped to read-only operations. See
design §6–§7.

## Developer guide

**Setup**

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
```

Requires **Python ≥3.10** (the `mcp` SDK floor).

**Checks**

```bash
ruff check src tests     # lint
mypy src                 # type-check
pytest tests/unit -q     # unit tests
```

The gated live smoke test (under `tests/integration`) talks to a real account
using only `list`, and is opt-in behind `EXOSCALE_RUN_LIVE_TESTS=1` — default-
skipped, and never run in CI. Run it with credentials injected from the
environment (never hardcoded):

```bash
EXOSCALE_RUN_LIVE_TESTS=1 \
  infisical run --domain http://localhost:8080 -- \
  pytest tests/integration -q
```

It is read-only, so safe to run against any account.

**Architecture & contribution.** Read
[`docs/mcp-advisor-design.md`](docs/mcp-advisor-design.md) first — it defines the
tool surface, the zero-duplication knowledge source, the read-only-by-
construction guarantee, and the four-layer test strategy. Conventional commits;
keep this README current with behavior changes in the same commit; no untested
code lands.

---

## License

[MIT](LICENSE) © 2026 Raphael Lang
