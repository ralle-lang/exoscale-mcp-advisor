"""Mocked unit tests for the live catalogue tools (design §9.2).

Drive the catalogue against a fake low-level HTTP client so the *real* connector
resource clients run — proving request shaping (path, per-call zone, visibility
param), response parsing, and error propagation, all without a network. This is
the same seam the structural test relies on: the tools call only ``list()``.
"""
from __future__ import annotations

import pytest
from exoscale_connector.errors import APIError, ConfigError

from exoscale_mcp_advisor.catalogue import Catalogue


class FakeClient:
    """Records GET calls and returns canned payloads (or raises) per collection path."""

    def __init__(
        self, payloads: dict[str, dict] | None = None, error: Exception | None = None
    ) -> None:
        self._payloads = payloads or {}
        self._error = error
        self.calls: list[tuple[str, str | None, dict | None]] = []

    def get(
        self, path: str, *, zone: str | None = None, params: dict | None = None
    ) -> dict:
        self.calls.append((path, zone, params))
        if self._error is not None:
            raise self._error
        return self._payloads.get(path, {})


def _catalogue(client: FakeClient) -> Catalogue:
    return Catalogue(client_factory=lambda: client)


# --------------------------------------------------------------------------- #
# list_zones
# --------------------------------------------------------------------------- #
def test_list_zones_hits_the_zone_collection_and_parses() -> None:
    client = FakeClient({"zone": {"zones": [{"name": "at-vie-1"}, {"name": "de-fra-1"}]}})
    zones = _catalogue(client).list_zones()
    assert zones == [{"name": "at-vie-1"}, {"name": "de-fra-1"}]
    assert client.calls == [("zone", None, None)]


def test_list_zones_empty() -> None:
    client = FakeClient({"zone": {"zones": []}})
    assert _catalogue(client).list_zones() == []


# --------------------------------------------------------------------------- #
# list_instance_types
# --------------------------------------------------------------------------- #
def test_list_instance_types_targets_the_requested_zone_and_adds_slug() -> None:
    client = FakeClient(
        {
            "instance-type": {
                "instance-types": [
                    {
                        "id": "1",
                        "family": "standard",
                        "size": "tiny",
                        "cpus": 1,
                        "memory": 2 * 1024**3,
                    },
                    {"id": "2", "family": "gpu", "size": "small"},
                ]
            }
        }
    )
    types = _catalogue(client).list_instance_types("at-vie-1")
    assert types[0]["slug"] == "standard.tiny"
    assert types[1]["slug"] == "gpu.small"
    # Raw bytes are preserved and a human-readable GiB is derived alongside.
    assert types[0]["memory"] == 2 * 1024**3
    assert types[0]["memory_gib"] == 2.0
    # No memory field → no derived field (rather than a misleading 0).
    assert "memory_gib" not in types[1]
    # The zone must be threaded to the per-call API host, not the client default.
    assert client.calls == [("instance-type", "at-vie-1", None)]


@pytest.mark.parametrize("bad_zone", ["", "   "])
def test_list_instance_types_rejects_empty_zone(bad_zone: str) -> None:
    client = FakeClient()
    with pytest.raises(ValueError, match="zone"):
        _catalogue(client).list_instance_types(bad_zone)
    assert client.calls == []  # validated before any API call


# --------------------------------------------------------------------------- #
# list_templates
# --------------------------------------------------------------------------- #
def test_list_templates_defaults_to_public_visibility() -> None:
    client = FakeClient({"template": {"templates": [{"id": "t1", "name": "Ubuntu"}]}})
    templates = _catalogue(client).list_templates("at-vie-1")
    assert templates == [{"id": "t1", "name": "Ubuntu"}]
    assert client.calls == [("template", "at-vie-1", {"visibility": "public"})]


def test_list_templates_derives_size_gib_keeping_raw_size() -> None:
    client = FakeClient(
        {"template": {"templates": [{"id": "t1", "name": "Ubuntu", "size": 10 * 1024**3}]}}
    )
    template = _catalogue(client).list_templates("at-vie-1")[0]
    assert template["size"] == 10 * 1024**3
    assert template["size_gib"] == 10.0


def test_list_templates_passes_private_visibility() -> None:
    client = FakeClient({"template": {"templates": []}})
    _catalogue(client).list_templates("at-vie-1", "private")
    assert client.calls == [("template", "at-vie-1", {"visibility": "private"})]


def test_list_templates_visibility_is_case_insensitive() -> None:
    client = FakeClient({"template": {"templates": []}})
    _catalogue(client).list_templates("at-vie-1", "PUBLIC")
    assert client.calls == [("template", "at-vie-1", {"visibility": "public"})]


def test_list_templates_rejects_unknown_visibility() -> None:
    client = FakeClient()
    with pytest.raises(ValueError, match="visibility"):
        _catalogue(client).list_templates("at-vie-1", "bogus")
    assert client.calls == []


def test_list_templates_rejects_empty_zone() -> None:
    client = FakeClient()
    with pytest.raises(ValueError, match="zone"):
        _catalogue(client).list_templates("")


# --------------------------------------------------------------------------- #
# list_dbaas_plans
# --------------------------------------------------------------------------- #
def test_list_dbaas_plans_hits_the_service_type_endpoint() -> None:
    client = FakeClient(
        {"dbaas-service-type": {"dbaas-service-types": [{"name": "pg"}, {"name": "mysql"}]}}
    )
    plans = _catalogue(client).list_dbaas_plans()
    assert plans == [{"name": "pg"}, {"name": "mysql"}]
    # zone omitted → no per-call zone override.
    assert client.calls == [("dbaas-service-type", None, None)]


def test_list_dbaas_plans_threads_an_explicit_zone() -> None:
    client = FakeClient({"dbaas-service-type": {"dbaas-service-types": []}})
    _catalogue(client).list_dbaas_plans("at-vie-1")
    assert client.calls == [("dbaas-service-type", "at-vie-1", None)]


def test_list_dbaas_plans_rejects_a_blank_zone_when_given() -> None:
    client = FakeClient()
    with pytest.raises(ValueError, match="zone"):
        _catalogue(client).list_dbaas_plans("   ")
    assert client.calls == []


# --------------------------------------------------------------------------- #
# Error propagation — the tools surface connector errors rather than swallowing.
# --------------------------------------------------------------------------- #
def test_api_errors_propagate() -> None:
    client = FakeClient(error=APIError("forbidden", status_code=403))
    with pytest.raises(APIError) as excinfo:
        _catalogue(client).list_zones()
    assert excinfo.value.status_code == 403


def test_client_is_built_once_and_reused() -> None:
    built = 0

    def factory() -> FakeClient:
        nonlocal built
        built += 1
        return FakeClient({"zone": {"zones": []}})

    cat = Catalogue(client_factory=factory)
    cat.list_zones()
    cat.list_zones()
    assert built == 1  # lazy, and cached after first use


def test_default_factory_needs_credentials_lazily(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Constructing the catalogue must not require credentials; only the first
    # live call resolves them from the environment (and fails clearly if unset).
    for var in ("EXOSCALE_API_KEY", "EXOSCALE_API_SECRET", "EXOSCALE_ZONE"):
        monkeypatch.delenv(var, raising=False)
    cat = Catalogue()  # no factory → ExoscaleClient.from_env; constructs fine
    with pytest.raises(ConfigError):
        cat.list_zones()  # resolving credentials now fails clearly
