"""Gate for the opt-in live smoke test (design §9.4).

Everything under ``tests/integration`` is skipped unless ``EXOSCALE_RUN_LIVE_TESTS``
is truthy — the same opt-in discipline as the connector's live tests. CI never
sets the flag (and runs only ``tests/unit``), so live tests are doubly safe to
keep in the tree. When enabled, credentials are read from the environment
(``EXOSCALE_API_KEY`` / ``EXOSCALE_API_SECRET`` / ``EXOSCALE_ZONE``), vault-
injected at runtime — never hardcoded, never read from files (design §7).
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

_RUN_FLAG = "EXOSCALE_RUN_LIVE_TESTS"
_TRUTHY = {"1", "true", "yes", "on"}
_DEFAULT_ZONE = "at-vie-1"
_INTEGRATION_DIR = Path(__file__).parent.resolve()


def _live_enabled() -> bool:
    return os.environ.get(_RUN_FLAG, "").strip().lower() in _TRUTHY


def _under_integration(item: pytest.Item) -> bool:
    try:
        Path(item.path).resolve().relative_to(_INTEGRATION_DIR)
    except (ValueError, AttributeError):
        return False
    return True


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "live: opt-in test that calls the real Exoscale API")


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    # This hook is global: only gate items that actually live under
    # tests/integration, never the unit suite collected in the same session.
    if _live_enabled():
        return
    skip = pytest.mark.skip(
        reason=f"live smoke disabled; set {_RUN_FLAG}=1 (read-only) to run"
    )
    for item in items:
        if _under_integration(item):
            item.add_marker(skip)


@pytest.fixture(scope="session")
def live_zone() -> str:
    """The zone the smoke test targets (``EXOSCALE_ZONE`` or ``at-vie-1``)."""
    return (os.environ.get("EXOSCALE_ZONE") or _DEFAULT_ZONE).strip() or _DEFAULT_ZONE
