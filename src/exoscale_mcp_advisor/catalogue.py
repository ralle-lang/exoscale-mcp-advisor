"""Live catalogue tools — read-only, ``list`` verb only.

Three thin wrappers over the connector's read-only catalogue clients (design §3):
``list_zones`` → ``ZoneClient.list()``, ``list_instance_types`` →
``InstanceTypeClient.list()``, ``list_templates`` → ``TemplateClient.list()``.
Every tool calls a connector ``list()`` and nothing else — no ``get`` / ``create``
/ ``update`` / ``delete``. This is layer one of the read-only guarantee: the code
literally cannot mutate (design §6).

The low-level :class:`~exoscale_connector.client.ExoscaleClient` is injected via a
factory so the real, read-only resource clients can be exercised in tests against
a fake HTTP client — proving request shaping and parsing without a network.
Credentials are read from the environment by the default factory
(``ExoscaleClient.from_env``); nothing is read from files (design §7).
"""
from __future__ import annotations

from typing import Callable

from exoscale_connector import ExoscaleClient
from exoscale_connector.models import ExoscaleModel
from exoscale_connector.resources.dbaas import DBaaSServiceClient
from exoscale_connector.resources.instance_type import InstanceType, InstanceTypeClient
from exoscale_connector.resources.template import TemplateClient
from exoscale_connector.resources.zone import ZoneClient

# Templates accept a visibility filter; only these two values are meaningful.
_TEMPLATE_VISIBILITIES = ("public", "private")

ClientFactory = Callable[[], ExoscaleClient]


def _dump(model: ExoscaleModel) -> dict[str, object]:
    """Render a connector model as a compact, JSON-serializable dict.

    Drops ``None`` fields to keep the catalogue output small; server-supplied
    extra fields pass through (the models allow them), so the advisor stays
    forward-compatible as the API grows.
    """
    return model.model_dump(mode="json", exclude_none=True)


def _dump_instance_type(instance_type: InstanceType) -> dict[str, object]:
    """Like :func:`_dump` but adds the human ``family.size`` slug for convenience."""
    data = _dump(instance_type)
    if instance_type.family and instance_type.size:
        data["slug"] = instance_type.slug
    return data


def _require_zone(zone: str) -> str:
    """Validate and normalize a required zone argument."""
    cleaned = (zone or "").strip()
    if not cleaned:
        raise ValueError("a non-empty 'zone' is required (e.g. 'at-vie-1')")
    return cleaned


class Catalogue:
    """Read-only access to the live Exoscale catalogue (zones, types, templates)."""

    def __init__(self, client_factory: ClientFactory | None = None) -> None:
        self._client_factory: ClientFactory = client_factory or ExoscaleClient.from_env
        self._client: ExoscaleClient | None = None

    def _client_instance(self) -> ExoscaleClient:
        """Lazily build (once) the signed HTTP client from the factory."""
        if self._client is None:
            self._client = self._client_factory()
        return self._client

    def list_zones(self) -> list[dict[str, object]]:
        """List the Exoscale zones visible to the configured credentials.

        Uses the environment's default zone to bootstrap the zone-scoped API host
        (the documented chicken-and-egg: one working zone lists all the others).
        """
        zones = ZoneClient(self._client_instance()).list()
        return [_dump(zone) for zone in zones]

    def list_instance_types(self, zone: str) -> list[dict[str, object]]:
        """List the compute offerings (instance types) available in ``zone``."""
        target = _require_zone(zone)
        types = InstanceTypeClient(self._client_instance()).list(zone=target)
        return [_dump_instance_type(t) for t in types]

    def list_templates(
        self, zone: str, visibility: str = "public"
    ) -> list[dict[str, object]]:
        """List the compute templates (boot images) in ``zone``.

        ``visibility`` is ``"public"`` (Exoscale's stock images, the default) or
        ``"private"`` (templates registered in your organisation).
        """
        target = _require_zone(zone)
        chosen = (visibility or "public").strip().lower()
        if chosen not in _TEMPLATE_VISIBILITIES:
            raise ValueError(
                f"'visibility' must be one of {_TEMPLATE_VISIBILITIES}, got {visibility!r}"
            )
        templates = TemplateClient(self._client_instance()).list(
            zone=target, visibility=chosen
        )
        return [_dump(t) for t in templates]

    def list_dbaas_plans(self, zone: str | None = None) -> list[dict[str, object]]:
        """List the available DBaaS service types (managed-database plans).

        Wraps the connector's read-only ``DBaaSServiceClient.list_service_types``,
        which returns the raw, type-specific service-type catalogue (engines and
        their plans/node specs). ``zone`` is optional — when omitted the server's
        default zone is used to reach the (zone-agnostic) endpoint; when given it
        is validated like the other live tools.
        """
        target = _require_zone(zone) if zone is not None else None
        return DBaaSServiceClient(self._client_instance()).list_service_types(
            zone=target
        )
