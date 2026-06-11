"""Bootstrap smoke test — proves the package imports and CI is wired.

The real test suite arrives with implementation (design §9): the structural
no-mutation-surface test, mocked-connector unit tests, protocol-level tests via
the MCP SDK in-memory transport, and one gated live smoke test.
"""
from __future__ import annotations

import exoscale_mcp_advisor


def test_package_exposes_version() -> None:
    assert isinstance(exoscale_mcp_advisor.__version__, str)
    assert exoscale_mcp_advisor.__version__
