"""Protocol-level tests via the MCP SDK's in-memory transport (design §9.3).

Drive the actual server through a real :class:`ClientSession` over in-memory
streams — listing tools and calling each — to prove the MCP wiring: tool names,
read-only annotations, input schemas, and result shapes. Still no network (the
catalogue runs against a fake HTTP client); async sessions are driven with
``anyio.run`` so the suite needs no extra pytest plugin.
"""
from __future__ import annotations

from collections.abc import Awaitable
from contextlib import asynccontextmanager
from typing import AsyncIterator, Callable, TypeVar

import anyio
from exoscale_connector.errors import APIError
from mcp.client.session import ClientSession
from mcp.shared.memory import create_connected_server_and_client_session as connect

import exoscale_mcp_advisor.server as server_module
from exoscale_mcp_advisor.catalogue import Catalogue
from exoscale_mcp_advisor.docs import DocsBundle
from exoscale_mcp_advisor.server import build_server

T = TypeVar("T")

_BUNDLE = DocsBundle(
    "# exoscale-connector\n\n"
    "## Asset-type reference pages\n\n"
    "### zone\n\nZones are discovered live, never hardcoded.\n\n"
    "### security-group (+ rules)\n\nA security group is a firewall for instances.\n"
)

_FIVE = {
    "search_docs",
    "get_asset_page",
    "list_zones",
    "list_instance_types",
    "list_templates",
}


class _FakeClient:
    """Canned read-only HTTP client; optionally raises to exercise error paths."""

    def __init__(self, error: Exception | None = None) -> None:
        self._error = error

    def get(self, path: str, *, zone: str | None = None, params: dict | None = None) -> dict:
        if self._error is not None:
            raise self._error
        return {
            "zone": {"zones": [{"name": "at-vie-1"}, {"name": "de-fra-1"}]},
            "instance-type": {
                "instance-types": [{"id": "1", "family": "standard", "size": "tiny"}]
            },
            "template": {"templates": [{"id": "t1", "name": "Ubuntu"}]},
        }.get(path, {})


def _run(scenario: Callable[[], Awaitable[T]]) -> T:
    return anyio.run(scenario)


@asynccontextmanager
async def _session(error: Exception | None = None) -> AsyncIterator[ClientSession]:
    catalogue = Catalogue(client_factory=lambda: _FakeClient(error))
    server = build_server(catalogue=catalogue, bundle=_BUNDLE)
    async with connect(server) as session:
        await session.initialize()
        yield session


def test_list_tools_exposes_exactly_the_five_read_only_tools() -> None:
    async def scenario() -> None:
        async with _session() as session:
            result = await session.list_tools()
            names = {tool.name for tool in result.tools}
            assert names == _FIVE
            for tool in result.tools:
                assert tool.annotations is not None, tool.name
                assert tool.annotations.readOnlyHint is True, tool.name
                assert tool.annotations.destructiveHint is False, tool.name

    _run(scenario)


def test_tool_input_schemas_declare_their_parameters() -> None:
    async def scenario() -> None:
        async with _session() as session:
            tools = {t.name: t for t in (await session.list_tools()).tools}
            assert "query" in tools["search_docs"].inputSchema["properties"]
            assert "asset_type" in tools["get_asset_page"].inputSchema["properties"]
            assert "zone" in tools["list_instance_types"].inputSchema["properties"]
            tpl_props = tools["list_templates"].inputSchema["properties"]
            assert "zone" in tpl_props and "visibility" in tpl_props
            # list_zones takes no arguments.
            assert tools["list_zones"].inputSchema.get("properties", {}) == {}

    _run(scenario)


def test_search_docs_call_returns_ranked_sections() -> None:
    async def scenario() -> None:
        async with _session() as session:
            result = await session.call_tool("search_docs", {"query": "security group firewall"})
            assert result.isError is False
            payload = result.structuredContent["result"]
            assert isinstance(payload, list) and payload
            assert "section_id" in payload[0] and "score" in payload[0]

    _run(scenario)


def test_get_asset_page_call_returns_full_page() -> None:
    async def scenario() -> None:
        async with _session() as session:
            result = await session.call_tool("get_asset_page", {"asset_type": "security-group"})
            assert result.isError is False
            data = result.structuredContent
            assert data["found"] is True
            assert "firewall" in data["content"]

    _run(scenario)


def test_get_asset_page_miss_is_a_successful_result_not_an_error() -> None:
    async def scenario() -> None:
        async with _session() as session:
            result = await session.call_tool("get_asset_page", {"asset_type": "nope"})
            assert result.isError is False
            assert result.structuredContent["found"] is False
            assert "zone" in result.structuredContent["available_asset_types"]

    _run(scenario)


def test_live_tools_return_catalogue_data() -> None:
    async def scenario() -> None:
        async with _session() as session:
            zones = await session.call_tool("list_zones", {})
            assert [z["name"] for z in zones.structuredContent["result"]] == [
                "at-vie-1",
                "de-fra-1",
            ]
            types = await session.call_tool("list_instance_types", {"zone": "at-vie-1"})
            assert types.structuredContent["result"][0]["slug"] == "standard.tiny"
            templates = await session.call_tool(
                "list_templates", {"zone": "at-vie-1", "visibility": "public"}
            )
            assert templates.structuredContent["result"][0]["name"] == "Ubuntu"

    _run(scenario)


def test_invalid_argument_surfaces_as_tool_error() -> None:
    async def scenario() -> None:
        async with _session() as session:
            result = await session.call_tool("list_instance_types", {"zone": "  "})
            assert result.isError is True

    _run(scenario)


def test_connector_api_error_surfaces_as_tool_error() -> None:
    async def scenario() -> None:
        async with _session(error=APIError("forbidden", status_code=403)) as session:
            result = await session.call_tool("list_zones", {})
            assert result.isError is True

    _run(scenario)


def test_main_builds_the_server_and_runs_it(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The console-script entry point builds a server and serves over stdio."""
    ran: dict[str, bool] = {}

    class _Stub:
        def run(self) -> None:
            ran["called"] = True

    monkeypatch.setattr(server_module, "build_server", lambda: _Stub())
    server_module.main()
    assert ran.get("called") is True
