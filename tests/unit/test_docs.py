"""Mocked unit tests for the docs tools (design §9.2).

Drive the parser and the two docs tools against a small, hand-written bundle so
ranking, page lookup, and not-found behaviour are tested deterministically with
no dependency on the installed connector package. A separate test confirms the
production loader can read the real packaged bundle.
"""
from __future__ import annotations

from exoscale_mcp_advisor.docs import DocsBundle, default_bundle

# A compact bundle exercising both heading systems and a fenced code block whose
# `#` comment lines must NOT be parsed as markdown headings.
_BUNDLE = """# exoscale-connector — AI reference bundle

Intro text about the connector.

## API surface by asset type

### `exoscale_connector.resources.security_group`

#### client `SecurityGroupClient`

Manage security groups and their rules. Create a rule on a group.

```python
# create a security group rule
client.create_rule(...)
```

## Asset-type reference pages (live-verified)

### Asset type reference

One page per asset type. This intro is not itself a page.

#### Page template

```
# <asset-type>
## Model
## CLI
```

### security-group (+ rules)

A security group is an Exoscale L3/L4 firewall for instances.

#### Gotchas

Ingress rules need a flow-direction of ingress.

### dns (domain + records)

Manage DNS domains and their records.

### zone

Zones are discovered live, never hardcoded.
"""


def _bundle() -> DocsBundle:
    return DocsBundle(_BUNDLE)


def test_asset_types_lists_only_real_pages_not_the_intro() -> None:
    assert _bundle().asset_types == ["dns", "security-group", "zone"]


def test_get_asset_page_returns_the_full_page() -> None:
    page = _bundle().get_asset_page("security-group")
    assert page["found"] is True
    assert page["heading"] == "security-group (+ rules)"
    content = page["content"]
    assert isinstance(content, str)
    assert content.startswith("### security-group (+ rules)")
    assert "firewall" in content
    assert "flow-direction of ingress" in content
    # The page must stop before the next sibling page.
    assert "Manage DNS domains" not in content


def test_get_asset_page_is_case_and_separator_insensitive() -> None:
    for query in ("security-group", "Security_Group", "  SECURITY-GROUP  "):
        assert _bundle().get_asset_page(query)["found"] is True


def test_get_asset_page_miss_lists_available_types() -> None:
    result = _bundle().get_asset_page("does-not-exist")
    assert result["found"] is False
    assert result["available_asset_types"] == ["dns", "security-group", "zone"]


def test_search_ranks_heading_matches_above_body_matches() -> None:
    results = _bundle().search("security group", limit=10)
    assert results, "expected at least one match"
    # The SecurityGroupClient heading section should outrank a passing body mention.
    top = results[0]
    assert "security" in str(top["heading"]).lower() or "securitygroup" in str(
        top["section_id"]
    )
    assert int(top["score"]) > 0


def test_search_respects_limit_and_orders_by_score() -> None:
    results = _bundle().search("rule", limit=2)
    assert len(results) <= 2
    scores = [int(r["score"]) for r in results]
    assert scores == sorted(scores, reverse=True)


def test_search_empty_query_returns_no_matches() -> None:
    assert _bundle().search("   ") == []
    assert _bundle().search("") == []


def test_search_no_match_returns_empty() -> None:
    assert _bundle().search("kubernetes etcd raft") == []


def test_fenced_code_comments_are_not_treated_as_pages_or_headings() -> None:
    # `# <asset-type>`, `## Model`, `## CLI` live inside fenced blocks; none of
    # them should appear as an asset page.
    types = _bundle().asset_types
    assert "<asset-type>" not in types
    assert "model" not in types
    assert "cli" not in types


def test_snippet_is_present_and_bounded() -> None:
    result = _bundle().search("firewall", limit=1)[0]
    snippet = str(result["snippet"])
    assert "firewall" in snippet
    assert len(snippet) <= 260


def test_default_bundle_loads_the_real_packaged_reference() -> None:
    # Production loader: reads exoscale_connector/_skill/reference.md.
    bundle = default_bundle()
    assert "security-group" in bundle.asset_types
    assert "zone" in bundle.asset_types
    page = bundle.get_asset_page("zone")
    assert page["found"] is True
