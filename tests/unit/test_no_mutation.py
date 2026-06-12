"""Structural no-mutation test — THE read-only enforcement point (design §6).

Read-only is a structural property of this server, not a policy. These tests
enumerate the tools the server actually registers and fail the build if that set
is ever anything but the approved read-only tools, mirroring the connector's
artifact-sync "enforcement-point" trick. A future contributor cannot add a
``create_instance`` tool without a red test forcing the conversation.

Defense in depth, layer one (the code cannot mutate); the least-privilege IAM key
is layer two (design §7).
"""
from __future__ import annotations

import inspect
import re
from pathlib import Path

from mcp.types import ToolAnnotations

from exoscale_mcp_advisor import catalogue, server
from exoscale_mcp_advisor.docs import DocsBundle
from exoscale_mcp_advisor.server import READ_ONLY_TOOL_NAMES, build_server

# The design doc is the single human-facing record of the tool surface; the
# approved set itself is defined in exactly one place — ``READ_ONLY_TOOL_NAMES``.
_DESIGN_DOC = Path(__file__).resolve().parents[2] / "docs" / "mcp-advisor-design.md"

# A tool table row leads with the tool name in backticks: ``| `list_zones` | …``.
# The trailing ``(`` keeps signature/backing-call cells (which contain ``(``) out;
# only the first cell — the bare tool name — matches.
_DOC_TOOL_ROW = re.compile(r"^\|\s*`([a-z_]+)`\s*\|", re.MULTILINE)

# Connector mutation verbs. A read-only tool layer must never call any of these;
# only the read verbs (`list`, and incidentally `get`) are permitted. The trailing
# paren keeps the match to real call sites, not prose in docstrings.
_MUTATING_CALLS = (".create(", ".update(", ".delete(", ".post(", ".put(", ".ensure(")

# A tiny bundle so building the server needs no installed connector package.
_FAKE_BUNDLE = DocsBundle("# t\n\n## Asset-type reference pages\n\n### zone\n\nz.\n")


def _registered_names(srv: object) -> set[str]:
    return {tool.name for tool in srv._tool_manager.list_tools()}  # type: ignore[attr-defined]


def test_server_registers_exactly_the_read_only_tools() -> None:
    srv = build_server(catalogue=catalogue.Catalogue(), bundle=_FAKE_BUNDLE)
    assert _registered_names(srv) == set(READ_ONLY_TOOL_NAMES)


def test_design_doc_tool_tables_match_the_approved_set() -> None:
    """The design doc must document exactly the registered tools — mechanically.

    Parses every tool-table row across the design doc (§3 v1 surface plus the
    per-release addenda §14/§15) and asserts their union equals the single
    approved set. Adding a tool without documenting it — or documenting a tool
    that no longer exists — fails the build, the same enforcement-point trick the
    no-mutation guard uses.
    """
    documented = set(_DOC_TOOL_ROW.findall(_DESIGN_DOC.read_text(encoding="utf-8")))
    assert documented == set(READ_ONLY_TOOL_NAMES)


def test_every_registered_tool_is_annotated_read_only() -> None:
    srv = build_server(catalogue=catalogue.Catalogue(), bundle=_FAKE_BUNDLE)
    for tool in srv._tool_manager.list_tools():  # type: ignore[attr-defined]
        annotations = tool.annotations
        assert isinstance(annotations, ToolAnnotations), tool.name
        assert annotations.readOnlyHint is True, tool.name
        assert annotations.destructiveHint is False, tool.name


def test_catalogue_layer_uses_no_mutating_connector_verb() -> None:
    """The live-tool layer's source must call only read verbs — never a mutation."""
    source = inspect.getsource(catalogue)
    offenders = [call for call in _MUTATING_CALLS if call in source]
    assert not offenders, f"catalogue.py calls mutating verb(s): {offenders}"


def test_server_layer_uses_no_mutating_connector_verb() -> None:
    source = inspect.getsource(server)
    offenders = [call for call in _MUTATING_CALLS if call in source]
    assert not offenders, f"server.py calls mutating verb(s): {offenders}"


def test_guard_trips_when_an_extra_tool_is_added() -> None:
    """Prove the enforcement actually catches drift: an extra tool breaks the set."""
    srv = build_server(catalogue=catalogue.Catalogue(), bundle=_FAKE_BUNDLE)

    @srv.tool(name="create_instance")  # the kind of tool that must never ship
    def create_instance(zone: str) -> dict[str, object]:
        return {"created": zone}

    assert _registered_names(srv) != set(READ_ONLY_TOOL_NAMES)
