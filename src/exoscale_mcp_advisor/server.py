"""MCP server wiring — registers the read-only tool set over stdio (design §8).

This module is the single place tools are registered. The set is deliberately
small and auditable; the structural no-mutation test (design §6) enumerates the
tools built here and fails the build if the set is ever anything but the
approved read-only tools below. Every tool is annotated ``readOnlyHint=True`` /
``destructiveHint=False`` so MCP clients also see the guarantee.

``build_server`` accepts an injected :class:`~exoscale_mcp_advisor.catalogue.Catalogue`
and :class:`~exoscale_mcp_advisor.docs.DocsBundle` so the server can be driven in
tests without credentials or the installed bundle; in production both default to
the real implementations. Constructing the server touches no credentials — the
catalogue builds its HTTP client lazily, only when a live tool is first called.
"""
from __future__ import annotations

from typing import Callable, TypeVar

from exoscale_connector.errors import APIError, ConfigError
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .catalogue import Catalogue
from .docs import DocsBundle, default_bundle

T = TypeVar("T")

SERVER_NAME = "exoscale-mcp-advisor"

# The complete, approved tool surface (design §3). The structural test asserts
# the server registers exactly this set — adding any tool, mutation or not, fails
# the build until this set is consciously changed.
READ_ONLY_TOOL_NAMES = frozenset(
    {
        "search_docs",
        "get_asset_page",
        "list_asset_types",
        "list_zones",
        "list_instance_types",
        "list_templates",
        "list_dbaas_plans",
        "list_sks_versions",
    }
)

_INSTRUCTIONS = (
    "Read-only Exoscale advisor. Search the connector's verified documentation "
    "and run list-only live catalogue queries (zones, instance types, templates, "
    "managed-database plans, SKS Kubernetes versions). This server cannot create, "
    "change, or delete any "
    "cloud resource — infrastructure changes remain the human's job, performed "
    "with reviewed connector code.\n\n"
    "Credentials: the docs tools (search_docs, get_asset_page, list_asset_types) "
    "need none. The live tools (list_zones, list_instance_types, list_templates, "
    "list_dbaas_plans, list_sks_versions) need EXOSCALE_API_KEY, "
    "EXOSCALE_API_SECRET and "
    "EXOSCALE_ZONE in the server's environment; without them they return a clear "
    "error while the docs tools keep working. Use a least-privilege, read-only "
    "key.\n\n"
    "The live tools build on the exoscale-connector package "
    "(https://github.com/ralle-lang/exoscale-python-connector, "
    "'pip install exoscale-connector'). The catalogue exposes no pricing — for "
    "cost estimates use Exoscale's online calculator; never imply a price."
)

# Shared, actionable guidance returned when a live tool can't authenticate.
_CREDENTIALS_HINT = (
    "the live catalogue needs Exoscale credentials in the server's environment "
    "(EXOSCALE_API_KEY, EXOSCALE_API_SECRET, EXOSCALE_ZONE) — the docs tools "
    "(search_docs, get_asset_page, list_asset_types) work without any credentials"
)


def _live_call(call: Callable[[], T]) -> T:
    """Run a live-tool body, turning missing/invalid credentials into clear errors.

    Connector ``ConfigError`` (no credentials resolved) and an auth ``APIError``
    (401/403) become a friendly, actionable message instead of a raw traceback;
    any other error propagates unchanged so genuine failures stay visible.
    """
    try:
        return call()
    except ConfigError as exc:
        raise ValueError(f"{_CREDENTIALS_HINT}. ({exc})") from exc
    except APIError as exc:
        if exc.status_code in (401, 403):
            raise ValueError(
                f"Exoscale rejected the credentials ({exc.status_code}); "
                f"{_CREDENTIALS_HINT}."
            ) from exc
        raise

# Docs tools are read-only over a fixed local bundle (closed world). Live tools
# are read-only but query the external API (open world). Neither ever mutates.
_DOCS_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
)
_LIVE_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True
)


def build_server(
    *, catalogue: Catalogue | None = None, bundle: DocsBundle | None = None
) -> FastMCP:
    """Build and return the configured advisor MCP server (not yet running).

    ``catalogue`` and ``bundle`` default to the production implementations; pass
    fakes to drive the server in tests without credentials or the real bundle.
    """
    cat = catalogue or Catalogue()
    docs = bundle if bundle is not None else default_bundle()
    mcp: FastMCP = FastMCP(SERVER_NAME, instructions=_INSTRUCTIONS)

    @mcp.tool(name="search_docs", annotations=_DOCS_ANNOTATIONS)
    def search_docs(query: str, limit: int = 5) -> list[dict[str, object]]:
        """Search the Exoscale connector documentation for sections matching a query.

        Returns up to ``limit`` ranked sections, each with its heading, a stable
        section id, a context snippet, and a relevance score. Use this to find
        how to work with an asset type, then ``get_asset_page`` for the full page.
        """
        return docs.search(query, limit=limit)

    @mcp.tool(name="get_asset_page", annotations=_DOCS_ANNOTATIONS)
    def get_asset_page(asset_type: str) -> dict[str, object]:
        """Return the full connector reference page for one asset type.

        ``asset_type`` is a slug such as ``security-group``, ``dns``, ``dbaas``,
        ``template`` or ``zone`` (case- and separator-insensitive). On a miss the
        result lists the available asset types.
        """
        return docs.get_asset_page(asset_type)

    @mcp.tool(name="list_asset_types", annotations=_DOCS_ANNOTATIONS)
    def list_asset_types() -> list[dict[str, str]]:
        """List the Exoscale asset types that have a reference page.

        Returns each asset type's slug — pass one to ``get_asset_page`` — and its
        page heading. Call this first to discover the valid ``asset_type`` values
        instead of guessing a slug.
        """
        return docs.asset_type_index()

    @mcp.tool(name="list_zones", annotations=_LIVE_ANNOTATIONS)
    def list_zones() -> list[dict[str, object]]:
        """List the Exoscale zones available to the configured credentials (live)."""
        return _live_call(cat.list_zones)

    @mcp.tool(name="list_instance_types", annotations=_LIVE_ANNOTATIONS)
    def list_instance_types(zone: str) -> list[dict[str, object]]:
        """List the compute offerings (instance types) available in ``zone`` (live).

        ``zone`` is a zone name such as ``at-vie-1``.
        """
        return _live_call(lambda: cat.list_instance_types(zone))

    @mcp.tool(name="list_templates", annotations=_LIVE_ANNOTATIONS)
    def list_templates(
        zone: str, visibility: str = "public"
    ) -> list[dict[str, object]]:
        """List the compute templates (boot images) in ``zone`` (live).

        ``zone`` is a zone name such as ``at-vie-1``; ``visibility`` is
        ``"public"`` (Exoscale stock images, default) or ``"private"``.
        """
        return _live_call(lambda: cat.list_templates(zone, visibility))

    @mcp.tool(name="list_dbaas_plans", annotations=_LIVE_ANNOTATIONS)
    def list_dbaas_plans(zone: str | None = None) -> list[dict[str, object]]:
        """List the managed-database (DBaaS) service types and their plans (live).

        ``zone`` is optional — when omitted the server's default zone is used.
        Returns the raw service-type catalogue: each database engine with its
        available plans and node specifications.
        """
        return _live_call(lambda: cat.list_dbaas_plans(zone))

    @mcp.tool(name="list_sks_versions", annotations=_LIVE_ANNOTATIONS)
    def list_sks_versions(zone: str | None = None) -> list[str]:
        """List the Kubernetes versions a new SKS cluster may be created with (live).

        ``zone`` is optional — when omitted the server's default zone is used.
        Returns raw version strings, newest-first (e.g. ``["1.31.0", "1.30.4"]``);
        ground a cluster's ``version`` against this live list rather than
        hardcoding a literal that can be retired upstream.
        """
        return _live_call(lambda: cat.list_sks_versions(zone))

    return mcp


def main() -> None:
    """Console-script entry point: build the server and serve over stdio (design §8)."""
    build_server().run()


if __name__ == "__main__":
    main()
