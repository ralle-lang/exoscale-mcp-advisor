# exoscale-mcp-advisor

A **read-only** [Model Context Protocol](https://modelcontextprotocol.io) server
that lets an MCP-capable agent learn about Exoscale: search the verified
connector documentation and run **list-only** live catalogue queries (zones,
instance types, templates). It is, by construction, incapable of mutating any
cloud resource.

> **Status: implemented, pre-publish.** All five tools, the stdio server, and the
> four-layer test suite (structural no-mutation, mocked-connector, protocol-level,
> gated live smoke) are in place and green. PyPI publication is the remaining
> step, so for now run it from a source checkout (see the user guide). The full
> design is in [`docs/mcp-advisor-design.md`](docs/mcp-advisor-design.md).

It builds on [`exoscale-connector`](https://github.com/ralle-lang/exoscale-python-connector):
the knowledge it serves is read from that package's bundled reference, and the
live queries reuse the connector's read-only `list` clients. Nothing about
Exoscale is hardcoded or duplicated here.

---

## General description

The advisor targets the **learning** path, not the execution path. An agent can
ask "what instance types exist in `at-vie-1` right now?" and "how do I create a
security group with the connector?" — and get live data plus verified docs —
while the server remains structurally unable to create, change, or delete
anything. Infrastructure changes stay the human's job, performed with reviewed,
idempotent code.

Tool surface (v1, see design §3):

| Tool | Purpose |
|------|---------|
| `search_docs(query)` | Ranked sections from the connector's reference bundle. |
| `get_asset_page(asset_type)` | Full reference page for one asset type. |
| `list_zones()` | Live list of zones. |
| `list_instance_types(zone)` | Live list of instance types. |
| `list_templates(zone, visibility)` | Live list of templates. |

No mutation tools — ever, by design.

## User guide

Once published to PyPI the server runs with no clone or install step:

```bash
uvx exoscale-mcp-advisor
```

Until then, run it from a source checkout:

```bash
pip install -e .
exoscale-mcp-advisor            # or: python -m exoscale_mcp_advisor
```

It speaks MCP over **stdio**, so it is configured like any other stdio MCP
server in your client. Live catalogue tools require Exoscale API credentials,
supplied **via environment variables only** — never on the command line, never
in a file:

```
EXOSCALE_API_KEY=...
EXOSCALE_API_SECRET=...
EXOSCALE_ZONE=at-vie-1
```

Use a **least-privilege, read-only** API key (see the Admin guide). The docs
tools work with no credentials at all.

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
