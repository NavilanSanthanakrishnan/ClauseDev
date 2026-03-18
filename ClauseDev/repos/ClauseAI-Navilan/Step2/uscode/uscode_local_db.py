from __future__ import annotations

import json
import re
import shutil
import sqlite3
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Iterable, Sequence
from urllib.parse import urljoin
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

USCODE_DATA_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = USCODE_DATA_DIR / "uscode_local.db"
DEFAULT_ARCHIVE_PATH = USCODE_DATA_DIR / "xml_uscAll_current.zip"
DOWNLOAD_PAGE_URL = "https://uscode.house.gov/download/download.shtml"
CORNELL_BASE_URL = "https://www.law.cornell.edu/uscode/text"
USER_AGENT = "Clause/1.0 (+https://github.com/openai/codex)"

NODE_TAGS = {
    "title",
    "subtitle",
    "chapter",
    "subchapter",
    "part",
    "subpart",
    "division",
    "subdivision",
    "article",
    "subarticle",
    "appendix",
    "subappendix",
    "section",
}
PROVISION_TAGS = {
    "subsection",
    "paragraph",
    "subparagraph",
    "clause",
    "subclause",
    "item",
    "subitem",
}
BLOCK_TAGS = {
    "content",
    "continuation",
    "chapeau",
    "date",
    "heading",
    "inline",
    "note",
    "notes",
    "p",
    "paragraph",
    "quotedcontent",
    "row",
    "sourcecredit",
    "subclause",
    "subitem",
    "subparagraph",
    "subsection",
    "table",
    "tocitem",
}
STRUCTURAL_NODE_SKIP_TAGS = {
    "note",
    "notes",
    "sourcecredit",
    "content",
    "chapeau",
    "quotedcontent",
}
LABEL_TEMPLATES = {
    "title": "Title {num}",
    "subtitle": "Subtitle {num}",
    "chapter": "CHAPTER {num}",
    "subchapter": "Subchapter {num}",
    "part": "PART {num}",
    "subpart": "Subpart {num}",
    "division": "Division {num}",
    "subdivision": "Subdivision {num}",
    "article": "Article {num}",
    "subarticle": "Subarticle {num}",
    "appendix": "Appendix {num}",
    "subappendix": "Subappendix {num}",
    "section": "§ {num}",
}
CITATION_LABELS = {
    "title": "Title",
    "subtitle": "Subtitle",
    "chapter": "Chapter",
    "subchapter": "Subchapter",
    "part": "Part",
    "subpart": "Subpart",
    "division": "Division",
    "subdivision": "Subdivision",
    "article": "Article",
    "subarticle": "Subarticle",
    "appendix": "Appendix",
    "subappendix": "Subappendix",
}
CORNELL_SEGMENT_PREFIX = {
    "subtitle": "subtitle-",
    "chapter": "chapter-",
    "subchapter": "subchapter-",
    "part": "part-",
    "subpart": "subpart-",
    "division": "division-",
    "subdivision": "subdivision-",
    "article": "article-",
    "subarticle": "subarticle-",
    "appendix": "appendix-",
    "subappendix": "subappendix-",
}
IDENTIFIER_PREFIXES = {
    "title": "t",
    "subtitle": "st",
    "chapter": "ch",
    "subchapter": "sch",
    "part": "pt",
    "subpart": "spt",
    "division": "div",
    "subdivision": "sdiv",
    "article": "art",
    "subarticle": "sart",
    "appendix": "app",
    "subappendix": "sapp",
    "section": "s",
    "subsection": "subsec",
    "paragraph": "par",
    "subparagraph": "subpar",
    "clause": "cl",
    "subclause": "subcl",
    "item": "item",
    "subitem": "subitem",
}

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS usc_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS usc_nodes (
    identifier TEXT PRIMARY KEY,
    parent_identifier TEXT REFERENCES usc_nodes(identifier),
    title_number TEXT NOT NULL,
    kind TEXT NOT NULL,
    num_value TEXT,
    label TEXT NOT NULL,
    heading TEXT,
    citation TEXT NOT NULL,
    cornell_url TEXT,
    breadcrumb TEXT NOT NULL,
    breadcrumb_json TEXT NOT NULL DEFAULT '[]',
    sort_order INTEGER NOT NULL DEFAULT 0,
    source_file TEXT NOT NULL,
    release_point TEXT NOT NULL,
    status TEXT,
    notes_text TEXT,
    source_credit_text TEXT,
    content_text TEXT,
    full_text TEXT,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS usc_nodes_parent_sort_idx
    ON usc_nodes (parent_identifier, sort_order, label);
CREATE INDEX IF NOT EXISTS usc_nodes_citation_idx
    ON usc_nodes (citation);
CREATE INDEX IF NOT EXISTS usc_nodes_cornell_url_idx
    ON usc_nodes (cornell_url)
    WHERE cornell_url IS NOT NULL;

CREATE TABLE IF NOT EXISTS usc_provisions (
    identifier TEXT PRIMARY KEY,
    section_identifier TEXT NOT NULL REFERENCES usc_nodes(identifier),
    parent_identifier TEXT,
    title_number TEXT NOT NULL,
    kind TEXT NOT NULL,
    num_value TEXT,
    heading TEXT,
    citation TEXT NOT NULL,
    depth INTEGER NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    direct_text TEXT,
    full_text TEXT,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS usc_provisions_section_idx
    ON usc_provisions (section_identifier, depth, sort_order, citation);
CREATE INDEX IF NOT EXISTS usc_provisions_parent_idx
    ON usc_provisions (parent_identifier, sort_order);
CREATE INDEX IF NOT EXISTS usc_provisions_citation_idx
    ON usc_provisions (citation);

CREATE TABLE IF NOT EXISTS usc_references (
    source_table TEXT NOT NULL,
    source_identifier TEXT NOT NULL,
    target_href TEXT NOT NULL,
    target_identifier TEXT,
    target_citation TEXT,
    anchor_text TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (source_table, source_identifier, target_href, anchor_text)
);

CREATE INDEX IF NOT EXISTS usc_references_source_idx
    ON usc_references (source_table, source_identifier);
CREATE INDEX IF NOT EXISTS usc_references_target_idx
    ON usc_references (target_identifier);

CREATE VIRTUAL TABLE IF NOT EXISTS usc_nodes_fts
USING fts5(
    citation,
    label,
    heading,
    breadcrumb,
    content_text,
    notes_text,
    full_text
);

CREATE VIRTUAL TABLE IF NOT EXISTS usc_provisions_fts
USING fts5(
    citation,
    heading,
    direct_text,
    full_text
);
"""

UPSERT_NODE_SQL = """
INSERT INTO usc_nodes (
    identifier,
    parent_identifier,
    title_number,
    kind,
    num_value,
    label,
    heading,
    citation,
    cornell_url,
    breadcrumb,
    breadcrumb_json,
    sort_order,
    source_file,
    release_point,
    status,
    notes_text,
    source_credit_text,
    content_text,
    full_text,
    updated_at
) VALUES (
    :identifier,
    :parent_identifier,
    :title_number,
    :kind,
    :num_value,
    :label,
    :heading,
    :citation,
    :cornell_url,
    :breadcrumb,
    :breadcrumb_json,
    :sort_order,
    :source_file,
    :release_point,
    :status,
    :notes_text,
    :source_credit_text,
    :content_text,
    :full_text,
    :updated_at
)
ON CONFLICT(identifier) DO UPDATE SET
    parent_identifier = excluded.parent_identifier,
    title_number = excluded.title_number,
    kind = excluded.kind,
    num_value = excluded.num_value,
    label = excluded.label,
    heading = excluded.heading,
    citation = excluded.citation,
    cornell_url = excluded.cornell_url,
    breadcrumb = excluded.breadcrumb,
    breadcrumb_json = excluded.breadcrumb_json,
    sort_order = excluded.sort_order,
    source_file = excluded.source_file,
    release_point = excluded.release_point,
    status = excluded.status,
    notes_text = excluded.notes_text,
    source_credit_text = excluded.source_credit_text,
    content_text = excluded.content_text,
    full_text = excluded.full_text,
    updated_at = excluded.updated_at;
"""

UPSERT_PROVISION_SQL = """
INSERT INTO usc_provisions (
    identifier,
    section_identifier,
    parent_identifier,
    title_number,
    kind,
    num_value,
    heading,
    citation,
    depth,
    sort_order,
    direct_text,
    full_text,
    updated_at
) VALUES (
    :identifier,
    :section_identifier,
    :parent_identifier,
    :title_number,
    :kind,
    :num_value,
    :heading,
    :citation,
    :depth,
    :sort_order,
    :direct_text,
    :full_text,
    :updated_at
)
ON CONFLICT(identifier) DO UPDATE SET
    section_identifier = excluded.section_identifier,
    parent_identifier = excluded.parent_identifier,
    title_number = excluded.title_number,
    kind = excluded.kind,
    num_value = excluded.num_value,
    heading = excluded.heading,
    citation = excluded.citation,
    depth = excluded.depth,
    sort_order = excluded.sort_order,
    direct_text = excluded.direct_text,
    full_text = excluded.full_text,
    updated_at = excluded.updated_at;
"""

UPSERT_REFERENCE_SQL = """
INSERT OR REPLACE INTO usc_references (
    source_table,
    source_identifier,
    target_href,
    target_identifier,
    target_citation,
    anchor_text,
    updated_at
) VALUES (
    :source_table,
    :source_identifier,
    :target_href,
    :target_identifier,
    :target_citation,
    :anchor_text,
    :updated_at
);
"""


@dataclass
class ReleaseInfo:
    archive_url: str
    release_point: str
    release_label: str


@dataclass
class BuildStats:
    title_files: int = 0
    nodes: int = 0
    sections: int = 0
    provisions: int = 0
    references: int = 0


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _normalize_space(text: str) -> str:
    cleaned = unescape(text or "")
    cleaned = cleaned.replace("\xa0", " ").replace("\u2000", " ").replace("\u202f", " ")
    cleaned = re.sub(r"[ \t\r\f\v]+", " ", cleaned)
    cleaned = re.sub(r" *\n *", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _serialize_text(element: ET.Element | None) -> str:
    if element is None:
        return ""

    parts: list[str] = []

    def visit(node: ET.Element) -> None:
        if node.text:
            parts.append(node.text)
        for child in list(node):
            child_name = _local_name(child.tag)
            if child_name in BLOCK_TAGS and parts and not parts[-1].endswith("\n"):
                parts.append("\n")
            visit(child)
            if child.tail:
                parts.append(child.tail)
            if child_name in BLOCK_TAGS and parts and not parts[-1].endswith("\n"):
                parts.append("\n")

    visit(element)
    return _normalize_space("".join(parts))


def _direct_child(element: ET.Element, name: str) -> ET.Element | None:
    for child in list(element):
        if _local_name(child.tag) == name:
            return child
    return None


def _direct_children(element: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in list(element) if _local_name(child.tag) == name]


def _extract_num_value(element: ET.Element) -> str:
    num = _direct_child(element, "num")
    if num is None:
        return ""
    value = num.attrib.get("value")
    if value:
        return value.strip()
    return _normalize_space("".join(num.itertext()))


def _extract_heading(element: ET.Element) -> str:
    heading = _direct_child(element, "heading")
    return _serialize_text(heading) if heading is not None else ""


def _extract_direct_text_parts(
    element: ET.Element,
    skip_tags: set[str] | None = None,
) -> str:
    skip = skip_tags or set()
    parts: list[str] = []
    for child in list(element):
        child_name = _local_name(child.tag)
        if child_name in skip or child_name in PROVISION_TAGS or child_name in NODE_TAGS:
            continue
        text = _serialize_text(child)
        if text:
            parts.append(text)
    return "\n\n".join(parts).strip()


def _section_content_text(element: ET.Element) -> str:
    parts: list[str] = []
    for child in list(element):
        child_name = _local_name(child.tag)
        if child_name in {"num", "heading", "notes", "sourcecredit"}:
            continue
        text = _serialize_text(child)
        if text:
            parts.append(text)
    return "\n\n".join(parts).strip()


def _iter_structural_node_children(element: ET.Element) -> Iterable[ET.Element]:
    for child in list(element):
        child_name = _local_name(child.tag)
        if child_name in NODE_TAGS:
            yield child
            continue
        if child_name in PROVISION_TAGS or child_name in STRUCTURAL_NODE_SKIP_TAGS:
            continue
        yield from _iter_structural_node_children(child)


def _notes_text(element: ET.Element) -> str:
    parts = [_serialize_text(child) for child in _direct_children(element, "notes")]
    return "\n\n".join(part for part in parts if part).strip()


def _source_credit_text(element: ET.Element) -> str:
    parts = [_serialize_text(child) for child in _direct_children(element, "sourcecredit")]
    return "\n\n".join(part for part in parts if part).strip()


def _build_label(kind: str, num_value: str) -> str:
    template = LABEL_TEMPLATES.get(kind, "{num}")
    return template.format(num=num_value).strip()


def _build_node_citation(title_number: str, kind: str, num_value: str) -> str:
    if kind == "title":
        return f"Title {title_number}"
    if kind == "section":
        return f"{title_number} U.S.C. § {num_value}"
    label = CITATION_LABELS.get(kind, kind.title())
    return f"Title {title_number} {label} {num_value}".strip()


def _build_provision_citation(title_number: str, section_num: str, suffix_parts: Sequence[str]) -> str:
    suffix = "".join(f"({part})" for part in suffix_parts if part)
    return f"{title_number} U.S.C. § {section_num}{suffix}"


def _build_cornell_url(title_number: str, lineage: Sequence[dict[str, str]]) -> str | None:
    if not lineage:
        return None

    current = lineage[-1]
    if current["kind"] == "title":
        return f"{CORNELL_BASE_URL}/{title_number}"
    if current["kind"] == "section":
        return f"{CORNELL_BASE_URL}/{title_number}/{current['num']}"

    segments = [title_number]
    for item in lineage[1:]:
        prefix = CORNELL_SEGMENT_PREFIX.get(item["kind"])
        if not prefix:
            continue
        segments.append(f"{prefix}{item['num']}")
    return f"{CORNELL_BASE_URL}/{'/'.join(segments)}"


def _member_key(member_name: str) -> str:
    match = re.search(r"usc(.+)\.xml$", member_name.lower())
    if not match:
        raise ValueError(f"Unexpected title filename: {member_name}")
    return match.group(1)


def _member_sort_key(member_name: str) -> tuple[int, str]:
    key = _member_key(member_name)
    match = re.fullmatch(r"(\d+)([a-z]*)", key)
    if not match:
        return (999, key)
    return (int(match.group(1)), match.group(2))


def _normalize_title_filter(value: str) -> str:
    cleaned = value.strip().lower().replace("title", "").replace(" ", "")
    match = re.fullmatch(r"(\d+)([a-z]*)", cleaned)
    if not match:
        raise ValueError(f"Unsupported title selector: {value}")
    return f"{int(match.group(1)):02d}{match.group(2)}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _slugify(value: str) -> str:
    token = re.sub(r"[^0-9A-Za-z]+", "-", value.strip()).strip("-").lower()
    return token or "item"


def _node_identifier(
    element: ET.Element,
    *,
    parent_identifier: str | None,
    kind: str,
    num_value: str,
    sort_order: int,
) -> str:
    identifier = element.attrib.get("identifier", "").strip()
    if identifier:
        return identifier

    prefix = IDENTIFIER_PREFIXES.get(kind, kind)
    token = _slugify(num_value or _extract_heading(element) or str(sort_order))
    if parent_identifier:
        return f"{parent_identifier}/x-{prefix}-{token}"
    return f"/synthetic/{prefix}-{token}"


def _fetch_url_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=120) as response:
        return response.read().decode("utf-8", "ignore")


def discover_latest_release() -> ReleaseInfo:
    html = _fetch_url_text(DOWNLOAD_PAGE_URL)
    archive_match = re.search(r'href="([^"]*xml_uscAll@([^"]+)\.zip)"', html)
    if not archive_match:
        raise RuntimeError("Could not find the current all-titles XML archive on the OLRC download page.")

    label_match = re.search(r'<h3 class="releasepointinformation">(.*?)</h3>', html, re.S)
    release_label = archive_match.group(2)
    if label_match:
        release_label = _normalize_space(re.sub(r"<[^>]+>", " ", label_match.group(1)))

    return ReleaseInfo(
        archive_url=urljoin(DOWNLOAD_PAGE_URL, archive_match.group(1)),
        release_point=archive_match.group(2),
        release_label=release_label,
    )


def download_archive(
    archive_url: str,
    destination: Path = DEFAULT_ARCHIVE_PATH,
    force: bool = False,
) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 0 and not force:
        return destination

    request = Request(archive_url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=300) as response, destination.open("wb") as handle:
        shutil.copyfileobj(response, handle)
    return destination


def _set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO usc_meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def initialize_database(conn: sqlite3.Connection, reset: bool = True) -> None:
    conn.executescript(
        """
        DROP INDEX IF EXISTS usc_nodes_citation_uidx;
        DROP INDEX IF EXISTS usc_section_citation_uidx;
        DROP INDEX IF EXISTS usc_nodes_cornell_url_uidx;
        DROP INDEX IF EXISTS usc_provisions_citation_uidx;
        """
    )
    conn.executescript(SCHEMA_SQL)
    if reset:
        conn.executescript(
            """
            DELETE FROM usc_meta;
            DELETE FROM usc_references;
            DELETE FROM usc_provisions;
            DELETE FROM usc_nodes;
            DELETE FROM usc_nodes_fts;
            DELETE FROM usc_provisions_fts;
            """
        )


def _insert_references(
    conn: sqlite3.Connection,
    *,
    source_table: str,
    source_identifier: str,
    element: ET.Element | None,
    stats: BuildStats,
) -> None:
    if element is None:
        return

    updated_at = _utc_now()
    for ref in element.iter():
        if _local_name(ref.tag) != "ref":
            continue
        href = ref.attrib.get("href", "").strip()
        if not href:
            continue
        target_identifier = href if href.startswith("/us/usc/") else None
        anchor_text = _normalize_space("".join(ref.itertext()))
        cursor = conn.execute(
            UPSERT_REFERENCE_SQL,
            {
                "source_table": source_table,
                "source_identifier": source_identifier,
                "target_href": href,
                "target_identifier": target_identifier,
                "target_citation": None,
                "anchor_text": anchor_text,
                "updated_at": updated_at,
            },
        )
        if cursor.rowcount > 0:
            stats.references += 1


def _insert_node(
    conn: sqlite3.Connection,
    *,
    identifier: str,
    parent_identifier: str | None,
    title_number: str,
    kind: str,
    num_value: str,
    label: str,
    heading: str,
    citation: str,
    cornell_url: str | None,
    breadcrumb: str,
    breadcrumb_json: str,
    sort_order: int,
    source_file: str,
    release_point: str,
    status: str | None,
    notes_text: str,
    source_credit_text: str,
    content_text: str,
    full_text: str,
) -> None:
    conn.execute(
        UPSERT_NODE_SQL,
        {
            "identifier": identifier,
            "parent_identifier": parent_identifier,
            "title_number": title_number,
            "kind": kind,
            "num_value": num_value or None,
            "label": label,
            "heading": heading or None,
            "citation": citation,
            "cornell_url": cornell_url,
            "breadcrumb": breadcrumb,
            "breadcrumb_json": breadcrumb_json,
            "sort_order": sort_order,
            "source_file": source_file,
            "release_point": release_point,
            "status": status or None,
            "notes_text": notes_text or None,
            "source_credit_text": source_credit_text or None,
            "content_text": content_text or None,
            "full_text": full_text or None,
            "updated_at": _utc_now(),
        },
    )


def _insert_provision(
    conn: sqlite3.Connection,
    *,
    identifier: str,
    section_identifier: str,
    parent_identifier: str | None,
    title_number: str,
    kind: str,
    num_value: str,
    heading: str,
    citation: str,
    depth: int,
    sort_order: int,
    direct_text: str,
    full_text: str,
) -> None:
    conn.execute(
        UPSERT_PROVISION_SQL,
        {
            "identifier": identifier,
            "section_identifier": section_identifier,
            "parent_identifier": parent_identifier,
            "title_number": title_number,
            "kind": kind,
            "num_value": num_value or None,
            "heading": heading or None,
            "citation": citation,
            "depth": depth,
            "sort_order": sort_order,
            "direct_text": direct_text or None,
            "full_text": full_text or None,
            "updated_at": _utc_now(),
        },
    )


def _walk_provision(
    conn: sqlite3.Connection,
    *,
    element: ET.Element,
    section_identifier: str,
    title_number: str,
    section_num: str,
    provision_suffix: list[str],
    parent_identifier: str | None,
    depth: int,
    sort_order: int,
    stats: BuildStats,
) -> None:
    kind = _local_name(element.tag)
    num_value = _extract_num_value(element)
    identifier = _node_identifier(
        element,
        parent_identifier=parent_identifier or section_identifier,
        kind=kind,
        num_value=num_value,
        sort_order=sort_order,
    )
    heading = _extract_heading(element)
    suffix_parts = [*provision_suffix]
    if num_value:
        suffix_parts.append(num_value)
    citation = _build_provision_citation(title_number, section_num, suffix_parts)
    direct_text = _extract_direct_text_parts(
        element,
        skip_tags={"num", "heading", "notes", "sourcecredit"},
    )
    full_text = _serialize_text(element)

    _insert_provision(
        conn,
        identifier=identifier,
        section_identifier=section_identifier,
        parent_identifier=parent_identifier,
        title_number=title_number,
        kind=kind,
        num_value=num_value,
        heading=heading,
        citation=citation,
        depth=depth,
        sort_order=sort_order,
        direct_text=direct_text,
        full_text=full_text,
    )
    stats.provisions += 1
    _insert_references(
        conn,
        source_table="provision",
        source_identifier=identifier,
        element=element,
        stats=stats,
    )

    child_order = 0
    for child in list(element):
        if _local_name(child.tag) not in PROVISION_TAGS:
            continue
        child_order += 1
        _walk_provision(
            conn,
            element=child,
            section_identifier=section_identifier,
            title_number=title_number,
            section_num=section_num,
            provision_suffix=suffix_parts,
            parent_identifier=identifier,
            depth=depth + 1,
            sort_order=child_order,
            stats=stats,
        )


def _walk_node(
    conn: sqlite3.Connection,
    *,
    element: ET.Element,
    parent_identifier: str | None,
    title_number: str,
    lineage: list[dict[str, str]],
    sort_order: int,
    source_file: str,
    release_point: str,
    stats: BuildStats,
) -> None:
    kind = _local_name(element.tag)
    num_value = _extract_num_value(element)
    identifier = _node_identifier(
        element,
        parent_identifier=parent_identifier,
        kind=kind,
        num_value=num_value,
        sort_order=sort_order,
    )
    heading = _extract_heading(element)
    label = _build_label(kind, num_value)
    citation = _build_node_citation(title_number, kind, num_value)
    if parent_identifier is None:
        label = f"Title {title_number}"
        citation = f"Title {title_number}"
    current = {"identifier": identifier, "kind": kind, "num": num_value, "label": label, "heading": heading}
    full_lineage = [*lineage, current]
    breadcrumb = " > ".join(item["label"] for item in full_lineage if item["label"])
    breadcrumb_json = json.dumps(full_lineage)
    cornell_url = _build_cornell_url(title_number, full_lineage)
    notes_text = _notes_text(element)
    source_credit_text = _source_credit_text(element)
    content_text = _section_content_text(element) if kind == "section" else ""
    full_text = "\n\n".join(
        part for part in [heading, content_text, source_credit_text, notes_text] if part
    ).strip()

    _insert_node(
        conn,
        identifier=identifier,
        parent_identifier=parent_identifier,
        title_number=title_number,
        kind=kind,
        num_value=num_value,
        label=label,
        heading=heading,
        citation=citation,
        cornell_url=cornell_url,
        breadcrumb=breadcrumb,
        breadcrumb_json=breadcrumb_json,
        sort_order=sort_order,
        source_file=source_file,
        release_point=release_point,
        status=element.attrib.get("status"),
        notes_text=notes_text,
        source_credit_text=source_credit_text,
        content_text=content_text,
        full_text=full_text,
    )
    stats.nodes += 1
    if kind == "section":
        stats.sections += 1

    _insert_references(
        conn,
        source_table="node",
        source_identifier=identifier,
        element=element,
        stats=stats,
    )

    if kind == "section":
        provision_order = 0
        for child in list(element):
            if _local_name(child.tag) not in PROVISION_TAGS:
                continue
            provision_order += 1
            _walk_provision(
                conn,
                element=child,
                section_identifier=identifier,
                title_number=title_number,
                section_num=num_value,
                provision_suffix=[],
                parent_identifier=None,
                depth=1,
                sort_order=provision_order,
                stats=stats,
            )

    child_order = 0
    for child in _iter_structural_node_children(element):
        child_order += 1
        _walk_node(
            conn,
            element=child,
            parent_identifier=identifier,
            title_number=title_number,
            lineage=full_lineage,
            sort_order=child_order,
            source_file=source_file,
            release_point=release_point,
            stats=stats,
        )


def _import_title_file(
    conn: sqlite3.Connection,
    *,
    archive: zipfile.ZipFile,
    member_name: str,
    release_point: str,
    stats: BuildStats,
) -> None:
    with archive.open(member_name) as handle:
        tree = ET.parse(handle)

    root = tree.getroot()
    meta_doc_number = root.findtext(".//{http://xml.house.gov/schemas/uslm/1.0}docNumber", default="")
    title_number = meta_doc_number.strip()
    if not title_number:
        raise RuntimeError(f"Could not determine title number for {member_name}")

    main = None
    for child in list(root):
        if _local_name(child.tag) == "main":
            main = child
            break
    search_root = main if main is not None else root

    title_element = None
    for child in list(search_root):
        if _local_name(child.tag) in NODE_TAGS:
            title_element = child
            break
    if title_element is None:
        raise RuntimeError(f"Missing top-level structural node in {member_name}")

    _walk_node(
        conn,
        element=title_element,
        parent_identifier=None,
        title_number=title_number,
        lineage=[],
        sort_order=1,
        source_file=member_name,
        release_point=release_point,
        stats=stats,
    )
    stats.title_files += 1


def _rebuild_reference_citations(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        UPDATE usc_references
        SET target_citation = (
            SELECT citation FROM usc_nodes WHERE usc_nodes.identifier = usc_references.target_identifier
            UNION ALL
            SELECT citation FROM usc_provisions WHERE usc_provisions.identifier = usc_references.target_identifier
            LIMIT 1
        )
        WHERE target_identifier IS NOT NULL;
        """
    )


def _rebuild_search_indexes(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM usc_nodes_fts")
    conn.execute("DELETE FROM usc_provisions_fts")
    conn.execute(
        """
        INSERT INTO usc_nodes_fts (rowid, citation, label, heading, breadcrumb, content_text, notes_text, full_text)
        SELECT rowid, citation, label, COALESCE(heading, ''), breadcrumb, COALESCE(content_text, ''), COALESCE(notes_text, ''), COALESCE(full_text, '')
        FROM usc_nodes;
        """
    )
    conn.execute(
        """
        INSERT INTO usc_provisions_fts (rowid, citation, heading, direct_text, full_text)
        SELECT rowid, citation, COALESCE(heading, ''), COALESCE(direct_text, ''), COALESCE(full_text, '')
        FROM usc_provisions;
        """
    )


def build_uscode_database(
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
    archive_path: Path | str = DEFAULT_ARCHIVE_PATH,
    archive_url: str | None = None,
    reset: bool = True,
    force_download: bool = False,
    titles: Sequence[str] | None = None,
    limit_titles: int | None = None,
) -> BuildStats:
    db_path = Path(db_path)
    archive_path = Path(archive_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path.parent.mkdir(parents=True, exist_ok=True)

    release = discover_latest_release() if archive_url is None else ReleaseInfo(
        archive_url=archive_url,
        release_point=re.search(r"@([^/]+)\.zip$", archive_url).group(1) if re.search(r"@([^/]+)\.zip$", archive_url) else "custom",
        release_label=re.search(r"@([^/]+)\.zip$", archive_url).group(1) if re.search(r"@([^/]+)\.zip$", archive_url) else "custom",
    )
    download_archive(release.archive_url, archive_path, force=force_download)

    title_filters = {_normalize_title_filter(title) for title in titles or []}
    stats = BuildStats()

    with sqlite3.connect(db_path) as conn:
        initialize_database(conn, reset=reset)
        _set_meta(conn, "source_archive_url", release.archive_url)
        _set_meta(conn, "release_point", release.release_point)
        _set_meta(conn, "release_label", release.release_label)
        _set_meta(conn, "source_archive_path", str(archive_path))
        _set_meta(conn, "build_started_at", _utc_now())

        with zipfile.ZipFile(archive_path) as archive:
            members = [name for name in archive.namelist() if name.lower().endswith(".xml")]
            members.sort(key=_member_sort_key)
            if title_filters:
                members = [name for name in members if _member_key(name) in title_filters]
            if limit_titles is not None:
                members = members[:limit_titles]

            for member_name in members:
                _import_title_file(
                    conn,
                    archive=archive,
                    member_name=member_name,
                    release_point=release.release_point,
                    stats=stats,
                )

        _rebuild_reference_citations(conn)
        _rebuild_search_indexes(conn)
        _set_meta(conn, "build_completed_at", _utc_now())
        _set_meta(conn, "title_file_count", str(stats.title_files))
        _set_meta(conn, "node_count", str(stats.nodes))
        _set_meta(conn, "section_count", str(stats.sections))
        _set_meta(conn, "provision_count", str(stats.provisions))
        _set_meta(conn, "reference_count", str(stats.references))
        conn.commit()

    return stats


def open_repository(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_stats(db_path: Path | str = DEFAULT_DB_PATH) -> dict[str, str]:
    with open_repository(db_path) as conn:
        rows = conn.execute("SELECT key, value FROM usc_meta ORDER BY key").fetchall()
    return {row["key"]: row["value"] for row in rows}


def list_children(parent_identifier: str, db_path: Path | str = DEFAULT_DB_PATH) -> list[sqlite3.Row]:
    with open_repository(db_path) as conn:
        return conn.execute(
            """
            SELECT identifier, kind, label, heading, citation, cornell_url
            FROM usc_nodes
            WHERE parent_identifier = ?
            ORDER BY sort_order, label
            """,
            (parent_identifier,),
        ).fetchall()


def get_node(
    *,
    identifier: str | None = None,
    citation: str | None = None,
    cornell_url: str | None = None,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> sqlite3.Row | None:
    criteria = [(identifier, "identifier"), (citation, "citation"), (cornell_url, "cornell_url")]
    value, field = next(((value, field) for value, field in criteria if value), (None, None))
    if value is None or field is None:
        raise ValueError("Provide identifier, citation, or cornell_url.")

    with open_repository(db_path) as conn:
        return conn.execute(
            f"""
            SELECT *
            FROM usc_nodes
            WHERE {field} = ?
            LIMIT 1
            """,
            (value,),
        ).fetchone()


def search_sections(
    query: str,
    *,
    limit: int = 10,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> list[sqlite3.Row]:
    with open_repository(db_path) as conn:
        try:
            return conn.execute(
                """
                SELECT
                    usc_nodes.citation,
                    usc_nodes.heading,
                    usc_nodes.identifier,
                    usc_nodes.cornell_url,
                    snippet(usc_nodes_fts, 6, '[', ']', ' … ', 14) AS match_snippet
                FROM usc_nodes_fts
                JOIN usc_nodes ON usc_nodes.rowid = usc_nodes_fts.rowid
                WHERE usc_nodes.kind = 'section'
                  AND usc_nodes_fts MATCH ?
                ORDER BY bm25(usc_nodes_fts)
                LIMIT ?
                """,
                (query, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            pattern = f"%{query}%"
            return conn.execute(
                """
                SELECT citation, heading, identifier, cornell_url, substr(full_text, 1, 240) AS match_snippet
                FROM usc_nodes
                WHERE kind = 'section'
                  AND (citation LIKE ? OR heading LIKE ? OR full_text LIKE ?)
                ORDER BY citation
                LIMIT ?
                """,
                (pattern, pattern, pattern, limit),
            ).fetchall()


def search_provisions(
    query: str,
    *,
    limit: int = 10,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> list[sqlite3.Row]:
    with open_repository(db_path) as conn:
        try:
            return conn.execute(
                """
                SELECT
                    usc_provisions.citation,
                    usc_provisions.heading,
                    usc_provisions.identifier,
                    snippet(usc_provisions_fts, 3, '[', ']', ' … ', 14) AS match_snippet
                FROM usc_provisions_fts
                JOIN usc_provisions ON usc_provisions.rowid = usc_provisions_fts.rowid
                WHERE usc_provisions_fts MATCH ?
                ORDER BY bm25(usc_provisions_fts)
                LIMIT ?
                """,
                (query, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            pattern = f"%{query}%"
            return conn.execute(
                """
                SELECT citation, heading, identifier, substr(full_text, 1, 240) AS match_snippet
                FROM usc_provisions
                WHERE citation LIKE ? OR heading LIKE ? OR full_text LIKE ?
                ORDER BY citation
                LIMIT ?
                """,
                (pattern, pattern, pattern, limit),
            ).fetchall()
