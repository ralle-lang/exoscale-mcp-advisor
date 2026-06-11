"""Opt-in live smoke test — lists the real catalogue, read-only (design §9.4).

Default-skipped (see ``conftest.py``); run with::

    EXOSCALE_RUN_LIVE_TESTS=1 \\
      infisical run --domain http://localhost:8080 -- \\
      pytest tests/integration -q

Every call here is a ``list`` — nothing is created, changed, or deleted, so the
test is safe to run against any account. It exercises both the catalogue layer
and one full pass through the MCP server over the in-memory transport.
"""
from __future__ import annotations

import anyio
import pytest
from mcp.shared.memory import create_connected_server_and_client_session as connect

from exoscale_mcp_advisor.catalogue import Catalogue
from exoscale_mcp_advisor.server import build_server

pytestmark = pytest.mark.live


def test_live_list_zones_includes_target_zone(live_zone: str) -> None:
    zones = Catalogue().list_zones()
    assert zones, "expected at least one zone"
    names = {z.get("name") for z in zones}
    assert live_zone in names, f"{live_zone} not in {sorted(n for n in names if n)}"


def test_live_list_instance_types_are_well_formed(live_zone: str) -> None:
    types = Catalogue().list_instance_types(live_zone)
    assert types, "expected at least one instance type"
    # Every offering should carry its human family.size slug.
    assert all("slug" in t for t in types)


def test_live_list_public_templates_present(live_zone: str) -> None:
    templates = Catalogue().list_templates(live_zone, "public")
    assert templates, "expected at least one public template"
    assert all(t.get("visibility") in (None, "public") for t in templates)


def test_live_through_mcp_server(live_zone: str) -> None:
    """One end-to-end pass: drive the real catalogue through the MCP server."""

    async def scenario() -> None:
        server = build_server(catalogue=Catalogue())
        async with connect(server) as session:
            await session.initialize()
            zones = await session.call_tool("list_zones", {})
            assert zones.isError is False
            assert zones.structuredContent["result"], "no zones returned via MCP"

            types = await session.call_tool("list_instance_types", {"zone": live_zone})
            assert types.isError is False
            assert types.structuredContent["result"], "no instance types via MCP"

    anyio.run(scenario)
