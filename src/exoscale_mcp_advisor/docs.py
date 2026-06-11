"""Docs tools — offline retrieval over the connector's packaged knowledge bundle.

The advisor serves the reference bundle that ``exoscale-connector`` already ships
(``exoscale_connector/_skill/reference.md``); no copy of the docs lives in this
repository, so the knowledge is exactly as current as the installed connector
version (design §4). This module parses that bundle and backs the two docs tools:

- :func:`DocsBundle.search` — plain keyword ranking over every section
  (design §5: no embeddings, no runtime AI, deterministic and dependency-light).
- :func:`DocsBundle.get_asset_page` — the full reference page for one asset type.

:class:`DocsBundle` is constructed from raw markdown so it is testable without the
installed package; :meth:`DocsBundle.from_package` is the production loader and
:func:`default_bundle` caches it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from typing import Optional

# The connector package and the path, within it, to the packaged bundle.
_CONNECTOR_PACKAGE = "exoscale_connector"
_BUNDLE_PARTS = ("_skill", "reference.md")

# The markdown heading under which the per-asset-type reference pages live, and
# the intro heading within it that is documentation-about-the-pages, not a page.
_ASSET_PAGES_SECTION = "Asset-type reference pages"
_ASSET_PAGES_INTRO = "Asset type reference"

# Heading occurrences of a query term count for this many body occurrences when
# ranking (design §5: "heading matches weighted higher").
_HEADING_WEIGHT = 5

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_WORD_RE = re.compile(r"[a-z0-9]+")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _heading_at(line: str) -> Optional[tuple[int, str]]:
    """Return ``(level, text)`` if the line is an ATX heading, else ``None``."""
    match = _HEADING_RE.match(line)
    if not match:
        return None
    return len(match.group(1)), match.group(2).strip()


@dataclass(frozen=True)
class Section:
    """One heading-delimited slice of the bundle.

    ``id`` is a stable, hierarchical slug path (e.g.
    ``api-surface-by-asset-type/exoscale_connector-resources-zone``) suitable for
    a consumer to reference a match. ``body`` is the text under the heading up to
    the next heading of any level; ``text`` is heading + body, used for ranking
    and snippets.
    """

    id: str
    heading: str
    level: int
    body: str
    order: int


@dataclass(frozen=True)
class AssetPage:
    """A full per-asset-type reference page (heading through its sub-sections)."""

    asset_type: str
    heading: str
    content: str


def _slugify(text: str) -> str:
    """Lowercase the text and collapse non-alphanumeric runs into single hyphens."""
    return _SLUG_RE.sub("-", text.lower()).strip("-")


def _normalize_asset_type(asset_type: str) -> str:
    """Normalize an asset-type request for tolerant matching.

    Case-folds and treats underscores and hyphens alike, so ``security_group``,
    ``Security-Group`` and ``security-group`` all resolve to the same page.
    """
    return asset_type.strip().lower().replace("_", "-")


def _tokenize(text: str) -> list[str]:
    """Case-folded alphanumeric tokens (drops punctuation and single characters)."""
    return [tok for tok in _WORD_RE.findall(text.lower()) if len(tok) > 1]


def _split_sections(markdown: str) -> list[Section]:
    """Split the bundle into flat, non-overlapping heading-delimited sections.

    Each heading owns the text up to the next heading of any level. Section ids
    are hierarchical slug paths built from the live heading stack, disambiguated
    with a numeric suffix on the rare collision so every id is unique.
    """
    lines = markdown.splitlines()
    sections: list[Section] = []
    used_ids: set[str] = set()
    # Stack of (level, slug) describing the path to the current heading.
    stack: list[tuple[int, str]] = []
    order = 0

    current: Optional[tuple[str, int, str]] = None  # (heading, level, id)
    body_lines: list[str] = []
    in_fence = False

    def flush() -> None:
        nonlocal current, body_lines, order
        if current is None:
            return
        heading, level, section_id = current
        sections.append(
            Section(
                id=section_id,
                heading=heading,
                level=level,
                body="\n".join(body_lines).strip(),
                order=order,
            )
        )
        order += 1
        body_lines = []

    for line in lines:
        if _FENCE_RE.match(line):
            in_fence = not in_fence
        heading_info = None if in_fence else _heading_at(line)
        if heading_info is None:
            if current is not None:
                body_lines.append(line)
            continue
        flush()
        level, heading = heading_info
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, _slugify(heading) or "section"))
        section_id = "/".join(slug for _, slug in stack)
        if section_id in used_ids:
            suffix = 2
            while f"{section_id}-{suffix}" in used_ids:
                suffix += 1
            section_id = f"{section_id}-{suffix}"
        used_ids.add(section_id)
        current = (heading, level, section_id)

    flush()
    return sections


def _extract_asset_pages(markdown: str) -> dict[str, AssetPage]:
    """Parse the per-asset-type reference pages keyed by normalized asset type.

    Scoped to the ``## Asset-type reference pages`` section: each ``###`` heading
    within it (except the intro) is one page, running to the next ``###`` sibling
    or the end of the section. The asset-type slug is the heading's first
    whitespace token, so ``### security-group (+ rules)`` → ``security-group`` and
    ``### object-storage bucket`` → ``object-storage``.
    """
    lines = markdown.splitlines()
    pages: dict[str, AssetPage] = {}

    in_section = False
    in_fence = False
    page_heading: Optional[str] = None
    page_slug: Optional[str] = None
    page_lines: list[str] = []

    def flush() -> None:
        nonlocal page_heading, page_slug, page_lines
        if page_heading is not None and page_slug:
            pages[page_slug] = AssetPage(
                asset_type=page_slug,
                heading=page_heading,
                content="\n".join(page_lines).strip(),
            )
        page_heading, page_slug, page_lines = None, None, []

    for line in lines:
        if _FENCE_RE.match(line):
            in_fence = not in_fence
        heading_info = None if in_fence else _heading_at(line)
        if heading_info is not None:
            level, heading = heading_info
            if level == 2:
                # Entering or leaving the asset-pages section ends any open page.
                flush()
                in_section = _ASSET_PAGES_SECTION.lower() in heading.lower()
                continue
            if level == 3 and in_section:
                flush()
                if heading == _ASSET_PAGES_INTRO:
                    continue  # documentation about the pages, not a page itself
                first_token = heading.split()[0] if heading.split() else heading
                page_slug = _normalize_asset_type(first_token)
                page_heading = heading
                page_lines = [line]
                continue
        if page_heading is not None:
            page_lines.append(line)

    flush()
    return pages


class DocsBundle:
    """Parsed view of the connector's reference bundle, backing the docs tools."""

    def __init__(self, markdown: str) -> None:
        self._markdown = markdown
        self._sections = _split_sections(markdown)
        self._asset_pages = _extract_asset_pages(markdown)

    @classmethod
    def from_package(cls) -> "DocsBundle":
        """Load the bundle shipped by the installed ``exoscale-connector`` package."""
        resource = files(_CONNECTOR_PACKAGE)
        for part in _BUNDLE_PARTS:
            resource = resource / part
        return cls(resource.read_text(encoding="utf-8"))

    @property
    def asset_types(self) -> list[str]:
        """The asset types that have a reference page, sorted."""
        return sorted(self._asset_pages)

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, object]]:
        """Rank bundle sections by keyword overlap with ``query``.

        Scoring is simple term frequency over case-folded alphanumeric tokens,
        with heading matches weighted higher (design §5). Returns up to ``limit``
        matches with a positive score, each as ``{heading, section_id, snippet,
        score}``, ordered by score then document position for determinism.
        """
        terms = _tokenize(query)
        if not terms:
            return []

        scored: list[tuple[int, int, Section]] = []
        for section in self._sections:
            heading_tokens = _tokenize(section.heading)
            body_tokens = _tokenize(section.body)
            score = 0
            for term in terms:
                score += heading_tokens.count(term) * _HEADING_WEIGHT
                score += body_tokens.count(term)
            if score > 0:
                scored.append((score, section.order, section))

        scored.sort(key=lambda item: (-item[0], item[1]))
        return [
            {
                "heading": section.heading,
                "section_id": section.id,
                "snippet": _snippet(section, terms),
                "score": score,
            }
            for score, _, section in scored[: max(limit, 0)]
        ]

    def get_asset_page(self, asset_type: str) -> dict[str, object]:
        """Return the full reference page for one asset type.

        On a miss, returns ``{found: False, ...}`` with the list of available
        asset types rather than raising, so the consumer can recover.
        """
        page = self._asset_pages.get(_normalize_asset_type(asset_type))
        if page is None:
            return {
                "found": False,
                "asset_type": asset_type,
                "available_asset_types": self.asset_types,
            }
        return {
            "found": True,
            "asset_type": page.asset_type,
            "heading": page.heading,
            "content": page.content,
        }


def _snippet(section: Section, terms: list[str], *, width: int = 240) -> str:
    """A short context snippet from the section body around the first matched term.

    Falls back to the body head when the match is only in the heading.
    """
    body = section.body.strip()
    if not body:
        return ""
    lowered = body.lower()
    first = min(
        (pos for pos in (lowered.find(term) for term in terms) if pos >= 0),
        default=-1,
    )
    if first < 0:
        text = body[:width]
        return text + ("…" if len(body) > width else "")
    start = max(0, first - width // 4)
    end = min(len(body), start + width)
    text = body[start:end].strip()
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(body) else ""
    return f"{prefix}{text}{suffix}"


@lru_cache(maxsize=1)
def default_bundle() -> DocsBundle:
    """The process-wide bundle loaded from the installed connector package."""
    return DocsBundle.from_package()
