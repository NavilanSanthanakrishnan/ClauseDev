from __future__ import annotations

import concurrent.futures
import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import sleep
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "sql" / "schema_california_code.sql"
LEGINFO_SECTION_PATH = "/faces/codes_displaySection.xhtml"
RELEVANT_QUERY_PARAMS = (
    "lawCode",
    "tocCode",
    "division",
    "title",
    "part",
    "chapter",
    "article",
    "heading2",
)
TEXT_URL_BASENAME = "codes_displayText.xhtml"
EXPANDED_URL_BASENAME = "codes_displayexpandedbranch.xhtml"
DEFAULT_USER_AGENT = "Clause-Step4-California-Code-Ingest/1.0"


@dataclass(slots=True)
class SectionRecord:
    section_number: str
    heading: str
    division_name: str
    chapter_name: str
    article_name: str
    hierarchy_path: str
    display_url: str
    body_text: str
    history_text: str


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def humanize_code_name(source_directory: str) -> str:
    raw = source_directory.rsplit("-", 1)[0]
    replacements = {
        "CodeofCivilProcedure": "Code of Civil Procedure",
        "BusinessandProfessionsCode": "Business and Professions Code",
        "FoodandAgriculturalCode": "Food and Agricultural Code",
        "FishandGameCode": "Fish and Game Code",
        "HarborsandNavigationCode": "Harbors and Navigation Code",
        "HealthandSafetyCode": "Health and Safety Code",
        "MilitaryandVeteransCode": "Military and Veterans Code",
        "PublicContractCode": "Public Contract Code",
        "PublicResourcesCode": "Public Resources Code",
        "PublicUtilitiesCode": "Public Utilities Code",
        "RevenueandTaxationCode": "Revenue and Taxation Code",
        "StreetsandHighwaysCode": "Streets and Highways Code",
        "UnemploymentInsuranceCode": "Unemployment Insurance Code",
        "WelfareandInstitutionsCode": "Welfare and Institutions Code",
    }
    if raw in replacements:
        return replacements[raw]
    raw = re.sub(r"([a-z])and([A-Z])", r"\1 and \2", raw)
    raw = re.sub(r"([a-z])([A-Z])", r"\1 \2", raw)
    return raw.strip()


def canonicalize_leginfo_url(url: str) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    ordered = [(key, query.get(key, "")) for key in RELEVANT_QUERY_PARAMS if key in query]
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", urlencode(ordered), ""))


def fetch_kind_for_url(url: str) -> str:
    basename = Path(urlparse(url).path).name
    if basename == TEXT_URL_BASENAME:
        return "text"
    if basename == EXPANDED_URL_BASENAME:
        return "expandedbranch"
    return "other"


def request_text(url: str, timeout: float = 30.0, retries: int = 3, retry_backoff_seconds: float = 2.0) -> tuple[int, str]:
    request = Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
    for attempt in range(max(1, retries)):
        try:
            with urlopen(request, timeout=timeout) as response:
                status = getattr(response, "status", 200)
                body = response.read().decode("utf-8", "ignore")
            return status, body
        except (HTTPError, URLError):
            if attempt >= max(1, retries) - 1:
                raise
            sleep(retry_backoff_seconds * (2**attempt))
    raise RuntimeError(f"unreachable request retry state for {url}")


def make_section_display_url(page_url: str, section_number: str) -> str:
    parsed = urlparse(page_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    law_code = query.get("lawCode", "") or query.get("tocCode", "")
    ordered = [("lawCode", law_code), ("sectionNum", section_number)]
    return urlunparse((parsed.scheme, parsed.netloc, LEGINFO_SECTION_PATH, "", urlencode(ordered), ""))


def parse_leginfo_sections(html: str, page_url: str) -> tuple[str, str, list[SectionRecord]]:
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one("#manylawsections")
    if container is None:
        raise ValueError("missing #manylawsections container")

    code_title = clean_text(container.find("h3").get_text(" ", strip=True) if container.find("h3") else "")
    breadcrumb = " > ".join(
        clean_text(item.get_text(" ", strip=True))
        for item in soup.select("#breadcrumbs li")
        if clean_text(item.get_text(" ", strip=True))
    )

    current_division = ""
    current_chapter = ""
    current_article = ""
    sections: list[SectionRecord] = []

    for block in container.find_all("div", align="left"):
        h4 = block.find("h4")
        h5 = block.find("h5")
        h6 = block.find("h6")

        if h4 and not h6:
            current_division = clean_text(h4.get_text(" ", strip=True))
            current_chapter = ""
            current_article = ""
            continue

        if h5 and not h6:
            heading_text = clean_text(h5.get_text(" ", strip=True))
            if heading_text.upper().startswith("ARTICLE"):
                current_article = heading_text
            else:
                current_chapter = heading_text
                current_article = ""
            continue

        if not h6:
            continue

        section_number = clean_text(h6.get_text(" ", strip=True))
        section_copy = BeautifulSoup(str(block), "html.parser")
        for tag in section_copy.find_all("h6"):
            tag.decompose()

        history_parts: list[str] = []
        for paragraph in section_copy.find_all("p"):
            paragraph_text = clean_text(paragraph.get_text(" ", strip=True))
            if not paragraph_text:
                paragraph.decompose()
                continue
            if paragraph_text.startswith("(") and (
                "Stats." in paragraph_text
                or "Repealed" in paragraph_text
                or "Amended" in paragraph_text
                or "Renumbered" in paragraph_text
                or "Added" in paragraph_text
            ):
                history_parts.append(paragraph_text)
                paragraph.decompose()

        body_text = clean_text(section_copy.get_text(" ", strip=True))
        body_text = re.sub(rf"^{re.escape(section_number)}\s*", "", body_text)
        body_text = clean_text(body_text)
        if not body_text:
            continue

        hierarchy = " > ".join(part for part in (current_division, current_chapter, current_article) if part)
        sections.append(
            SectionRecord(
                section_number=section_number,
                heading="",
                division_name=current_division,
                chapter_name=current_chapter,
                article_name=current_article,
                hierarchy_path=hierarchy,
                display_url=make_section_display_url(page_url, section_number),
                body_text=body_text,
                history_text="\n".join(history_parts),
            )
        )

    return code_title, breadcrumb, sections


def extract_leginfo_page_context(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.select_one("#manylawsections h3") or soup.find("h3")
    title_text = clean_text(title_tag.get_text(" ", strip=True) if title_tag else "")
    breadcrumb = " > ".join(
        clean_text(item.get_text(" ", strip=True))
        for item in soup.select("#breadcrumbs li")
        if clean_text(item.get_text(" ", strip=True))
    )
    return title_text, breadcrumb


def discover_leginfo_child_urls(html: str, page_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    page_canonical_url = canonicalize_leginfo_url(page_url)
    discovered: set[str] = set()
    for anchor in soup.select("a[href]"):
        href = (anchor.get("href") or "").strip()
        if not href or "goUp=Y" in href:
            continue
        if TEXT_URL_BASENAME not in href and EXPANDED_URL_BASENAME not in href:
            continue
        absolute_url = urljoin(page_url, href)
        canonical_url = canonicalize_leginfo_url(absolute_url)
        if not urlparse(canonical_url).query or canonical_url == page_canonical_url:
            continue
        discovered.add(canonical_url)
    return sorted(discovered)


class CaliforniaCodeDatabaseBuilder:
    def __init__(self, *, source_dir: Path, db_path: Path) -> None:
        self.source_dir = source_dir
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA synchronous = NORMAL")
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA temp_store = MEMORY")
        self.conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    def close(self) -> None:
        self.conn.close()

    def _code_id(self, code_abbrev: str, code_name: str, source_directory: str) -> int:
        self.conn.execute(
            """
            INSERT INTO code_books (code_abbrev, code_name, source_directory, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(code_abbrev) DO UPDATE SET
                code_name = excluded.code_name,
                source_directory = excluded.source_directory,
                updated_at = excluded.updated_at
            """,
            (code_abbrev, code_name, source_directory, utc_now()),
        )
        row = self.conn.execute(
            "SELECT id FROM code_books WHERE code_abbrev = ?",
            (code_abbrev,),
        ).fetchone()
        return int(row["id"])

    def _register_source_ref(
        self,
        *,
        code_id: int,
        toc_file_id: int,
        ref_kind: str,
        ref_key: str,
        ref_url: str,
    ) -> None:
        if not ref_url or not isinstance(ref_url, str):
            return

        canonical_url = canonicalize_leginfo_url(ref_url)
        fetch_kind = fetch_kind_for_url(canonical_url)
        self.conn.execute(
            """
            INSERT OR IGNORE INTO article_refs (
                code_id,
                toc_file_id,
                ref_kind,
                article_key,
                article_url,
                canonical_url,
                fetch_kind
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (code_id, toc_file_id, ref_kind, ref_key, ref_url, canonical_url, fetch_kind),
        )
        self._register_source_page(code_id=code_id, canonical_url=canonical_url, fetch_kind=fetch_kind)

    def _register_source_page(self, *, code_id: int, canonical_url: str, fetch_kind: str) -> None:
        fetch_status = "pending" if fetch_kind in {"text", "expandedbranch"} else "skipped_non_text"
        self.conn.execute(
            """
            INSERT INTO source_pages (canonical_url, code_id, fetch_kind, fetch_status)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(canonical_url) DO UPDATE SET
                code_id = excluded.code_id,
                fetch_kind = excluded.fetch_kind,
                fetch_status = CASE
                    WHEN source_pages.fetch_status IN ('parsed', 'parsed_empty') THEN source_pages.fetch_status
                    ELSE excluded.fetch_status
                END
            """,
            (canonical_url, code_id, fetch_kind, fetch_status),
        )

    def load_toc_metadata(self, *, only_code: str | None = None) -> dict[str, int]:
        toc_file_count = 0
        source_ref_count = 0

        for code_dir in sorted(path for path in self.source_dir.iterdir() if path.is_dir()):
            if "-" not in code_dir.name:
                continue
            code_abbrev = code_dir.name.rsplit("-", 1)[1]
            if only_code and code_abbrev != only_code:
                continue
            code_name = humanize_code_name(code_dir.name)
            code_id = self._code_id(code_abbrev, code_name, code_dir.name)

            json_files = sorted(code_dir.glob("*.json"))
            self.conn.execute(
                "UPDATE code_books SET toc_root_file_count = ?, updated_at = ? WHERE id = ?",
                (len(json_files), utc_now(), code_id),
            )

            for path in json_files:
                toc_file_count += 1
                relative_path = str(path.relative_to(self.source_dir))
                payload = json.loads(path.read_text(encoding="utf-8"))
                division_name = payload.get("division_name", "").strip()
                division_url = payload.get("url", "").strip()
                articles = payload.get("articles", {}) or {}

                self.conn.execute(
                    """
                    INSERT INTO toc_files (code_id, relative_path, division_name, division_url, file_sha256, article_count)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(relative_path) DO UPDATE SET
                        code_id = excluded.code_id,
                        division_name = excluded.division_name,
                        division_url = excluded.division_url,
                        file_sha256 = excluded.file_sha256,
                        article_count = excluded.article_count
                    """,
                    (
                        code_id,
                        relative_path,
                        division_name,
                        division_url,
                        sha256_text(path.read_text(encoding="utf-8")),
                        len(articles),
                    ),
                )
                toc_file_id = int(
                    self.conn.execute(
                        "SELECT id FROM toc_files WHERE relative_path = ?",
                        (relative_path,),
                    ).fetchone()["id"]
                )

                if division_url:
                    self._register_source_ref(
                        code_id=code_id,
                        toc_file_id=toc_file_id,
                        ref_kind="division",
                        ref_key="__division_url__",
                        ref_url=division_url,
                    )
                    source_ref_count += 1

                for article_key, article_url in articles.items():
                    if not isinstance(article_url, str):
                        continue
                    self._register_source_ref(
                        code_id=code_id,
                        toc_file_id=toc_file_id,
                        ref_kind="article",
                        ref_key=article_key,
                        ref_url=article_url,
                    )
                    source_ref_count += 1

        self.conn.commit()
        return {
            "toc_files": toc_file_count,
            "source_refs": source_ref_count,
            "source_pages": int(self.conn.execute("SELECT COUNT(*) FROM source_pages").fetchone()[0]),
        }

    def pending_pages(
        self,
        *,
        only_code: str | None = None,
        limit_pages: int | None = None,
        refetch_failed: bool = False,
    ) -> list[sqlite3.Row]:
        statuses = ("pending", "failed") if refetch_failed else ("pending",)
        params: list[object] = [*statuses]
        query = """
            SELECT sp.canonical_url, sp.code_id, cb.code_abbrev
            FROM source_pages sp
            JOIN code_books cb
              ON cb.id = sp.code_id
            WHERE (
                sp.fetch_kind = 'text'
                OR (
                    sp.fetch_kind = 'expandedbranch'
                    AND EXISTS (
                        SELECT 1
                        FROM article_refs ar
                        WHERE ar.canonical_url = sp.canonical_url
                          AND (
                              ar.ref_kind = 'article'
                              OR (
                                  ar.ref_kind = 'division'
                                  AND NOT EXISTS (
                                      SELECT 1
                                      FROM article_refs sibling
                                      WHERE sibling.toc_file_id = ar.toc_file_id
                                        AND sibling.fetch_kind = 'text'
                                  )
                              )
                          )
                    )
                )
            )
              AND sp.fetch_status IN ({placeholders})
        """.format(placeholders=", ".join("?" for _ in statuses))
        if only_code:
            query += " AND cb.code_abbrev = ?"
            params.append(only_code)
        query += """
            ORDER BY
                cb.code_abbrev,
                CASE WHEN sp.fetch_kind = 'text' THEN 0 ELSE 1 END,
                sp.canonical_url
        """
        if limit_pages:
            query += " LIMIT ?"
            params.append(limit_pages)
        return list(self.conn.execute(query, params))

    def _article_ref_ids(self, canonical_url: str) -> list[int]:
        return [
            int(row["id"])
            for row in self.conn.execute(
                "SELECT id FROM article_refs WHERE canonical_url = ? ORDER BY id",
                (canonical_url,),
            ).fetchall()
        ]

    def _refresh_fts(self, section_id: int) -> None:
        row = self.conn.execute(
            """
            SELECT
                s.id,
                cb.code_abbrev,
                s.section_number,
                COALESCE(s.heading, '') AS heading,
                COALESCE(s.hierarchy_path, '') AS hierarchy_path,
                s.body_text,
                COALESCE(s.history_text, '') AS history_text
            FROM sections s
            JOIN code_books cb
              ON cb.id = s.code_id
            WHERE s.id = ?
            """,
            (section_id,),
        ).fetchone()
        if row is None:
            return
        self.conn.execute("DELETE FROM section_fts WHERE rowid = ?", (section_id,))
        self.conn.execute(
            """
            INSERT INTO section_fts (
                rowid,
                section_id,
                code_abbrev,
                section_number,
                heading,
                hierarchy_path,
                body_text,
                history_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                section_id,
                section_id,
                row["code_abbrev"],
                row["section_number"],
                row["heading"],
                row["hierarchy_path"],
                row["body_text"],
                row["history_text"],
            ),
        )

    def _upsert_section(
        self,
        *,
        code_id: int,
        section: SectionRecord,
        source_page_url: str,
        article_ref_ids: Iterable[int],
    ) -> int:
        article_ref_ids = list(article_ref_ids)
        incoming_hash = sha256_text(f"{section.body_text}\n{section.history_text}".strip())
        row = self.conn.execute(
            """
            SELECT
                id,
                text_hash,
                source_page_url,
                body_text,
                history_text,
                source_count,
                heading,
                division_name,
                chapter_name,
                article_name,
                hierarchy_path
            FROM sections
            WHERE code_id = ? AND section_number = ?
            """,
            (code_id, section.section_number),
        ).fetchone()

        if row is None:
            cursor = self.conn.execute(
                """
                INSERT INTO sections (
                    code_id,
                    section_number,
                    heading,
                    division_name,
                    chapter_name,
                    article_name,
                    hierarchy_path,
                    display_url,
                    source_page_url,
                    body_text,
                    history_text,
                    text_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    code_id,
                    section.section_number,
                    section.heading,
                    section.division_name,
                    section.chapter_name,
                    section.article_name,
                    section.hierarchy_path,
                    section.display_url,
                    source_page_url,
                    section.body_text,
                    section.history_text,
                    incoming_hash,
                ),
            )
            section_id = int(cursor.lastrowid)
            refresh_fts = True
        else:
            section_id = int(row["id"])
            update_body = False
            refresh_fts = False
            if row["text_hash"] != incoming_hash:
                self.conn.execute(
                    """
                    INSERT INTO section_collisions (
                        code_id,
                        section_number,
                        existing_text_hash,
                        incoming_text_hash,
                        existing_source_url,
                        incoming_source_url
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        code_id,
                        section.section_number,
                        row["text_hash"],
                        incoming_hash,
                        row["source_page_url"],
                        source_page_url,
                    ),
                )
                current_len = len((row["body_text"] or "") + (row["history_text"] or ""))
                incoming_len = len(section.body_text + section.history_text)
                update_body = incoming_len > current_len
                refresh_fts = update_body

            metadata_changed = any(
                incoming and incoming != (row[column] or "")
                for column, incoming in (
                    ("heading", section.heading),
                    ("division_name", section.division_name),
                    ("chapter_name", section.chapter_name),
                    ("article_name", section.article_name),
                    ("hierarchy_path", section.hierarchy_path),
                )
            )
            refresh_fts = refresh_fts or metadata_changed

            self.conn.execute(
                """
                UPDATE sections
                SET
                    heading = CASE WHEN ? <> '' THEN ? ELSE heading END,
                    division_name = CASE WHEN ? <> '' THEN ? ELSE division_name END,
                    chapter_name = CASE WHEN ? <> '' THEN ? ELSE chapter_name END,
                    article_name = CASE WHEN ? <> '' THEN ? ELSE article_name END,
                    hierarchy_path = CASE WHEN ? <> '' THEN ? ELSE hierarchy_path END,
                    display_url = ?,
                    source_count = source_count + 1,
                    last_seen_at = ?
                WHERE id = ?
                """,
                (
                    section.heading,
                    section.heading,
                    section.division_name,
                    section.division_name,
                    section.chapter_name,
                    section.chapter_name,
                    section.article_name,
                    section.article_name,
                    section.hierarchy_path,
                    section.hierarchy_path,
                    section.display_url,
                    utc_now(),
                    section_id,
                ),
            )
            if update_body:
                self.conn.execute(
                    """
                    UPDATE sections
                    SET body_text = ?, history_text = ?, text_hash = ?, source_page_url = ?
                    WHERE id = ?
                    """,
                    (section.body_text, section.history_text, incoming_hash, source_page_url, section_id),
                )

        for article_ref_id in article_ref_ids:
            self.conn.execute(
                """
                INSERT OR IGNORE INTO section_sources (section_id, source_page_url, article_ref_id)
                VALUES (?, ?, ?)
                """,
                (section_id, source_page_url, article_ref_id),
            )
        if not article_ref_ids:
            self.conn.execute(
                """
                INSERT OR IGNORE INTO section_sources (section_id, source_page_url, article_ref_id)
                VALUES (?, ?, NULL)
                """,
                (section_id, source_page_url),
            )

        if refresh_fts:
            self._refresh_fts(section_id)
        return section_id

    def fetch_and_parse_pages(
        self,
        *,
        only_code: str | None = None,
        limit_pages: int | None = None,
        workers: int = 6,
        refetch_failed: bool = False,
    ) -> dict[str, int]:
        pages_seen = 0
        pages_fetched = 0
        sections_upserted = 0
        failures = 0

        def worker(canonical_url: str) -> tuple[str, int, str, str, str, list[SectionRecord] | None, list[str], str | None]:
            try:
                status, html = request_text(canonical_url)
                discovered_urls = discover_leginfo_child_urls(html, canonical_url)
                try:
                    title_text, breadcrumb_text, sections = parse_leginfo_sections(html, canonical_url)
                except ValueError as exc:
                    if discovered_urls:
                        title_text, breadcrumb_text = extract_leginfo_page_context(html)
                        return canonical_url, status, html, title_text, breadcrumb_text, [], discovered_urls, None
                    raise exc
                return canonical_url, status, html, title_text, breadcrumb_text, sections, discovered_urls, None
            except Exception as exc:  # noqa: BLE001
                return canonical_url, 0, "", "", "", None, [], str(exc)

        remaining_limit = limit_pages

        while True:
            pages = self.pending_pages(
                only_code=only_code,
                limit_pages=remaining_limit,
                refetch_failed=refetch_failed,
            )
            if not pages:
                break

            pages_seen += len(pages)
            if remaining_limit is not None:
                remaining_limit -= len(pages)

            code_id_by_url = {row["canonical_url"]: int(row["code_id"]) for row in pages}

            with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
                futures = {
                    executor.submit(worker, row["canonical_url"]): row["canonical_url"]
                    for row in pages
                }
                for future in concurrent.futures.as_completed(futures):
                    canonical_url, status, html, title_text, breadcrumb_text, sections, discovered_urls, error = future.result()
                    if error or sections is None:
                        failures += 1
                        self.conn.execute(
                            """
                            UPDATE source_pages
                            SET
                                http_status = ?,
                                fetch_status = 'failed',
                                fetched_at = ?,
                                error_message = ?
                            WHERE canonical_url = ?
                            """,
                            (status or None, utc_now(), error, canonical_url),
                        )
                        self.conn.commit()
                        continue

                    pages_fetched += 1
                    code_id = code_id_by_url[canonical_url]
                    article_ref_ids = self._article_ref_ids(canonical_url)

                    for discovered_url in discovered_urls:
                        self._register_source_page(
                            code_id=code_id,
                            canonical_url=discovered_url,
                            fetch_kind=fetch_kind_for_url(discovered_url),
                        )

                    for section in sections:
                        self._upsert_section(
                            code_id=code_id,
                            section=section,
                            source_page_url=canonical_url,
                            article_ref_ids=article_ref_ids,
                        )
                        sections_upserted += 1

                    self.conn.execute(
                        """
                        UPDATE source_pages
                        SET
                            http_status = ?,
                            fetch_status = ?,
                            fetched_at = ?,
                            html_sha256 = ?,
                            title_text = ?,
                            breadcrumb_text = ?,
                            parsed_section_count = ?,
                            error_message = NULL
                        WHERE canonical_url = ?
                        """,
                        (
                            status,
                            "parsed" if sections else "parsed_empty",
                            utc_now(),
                            sha256_text(html),
                            title_text,
                            breadcrumb_text,
                            len(sections),
                            canonical_url,
                        ),
                    )
                    self.conn.commit()

            if remaining_limit is not None and remaining_limit <= 0:
                break

        return {
            "pages_seen": pages_seen,
            "pages_fetched": pages_fetched,
            "sections_upserted": sections_upserted,
            "failures": failures,
        }

    def counts(self) -> dict[str, int]:
        tables = (
            "code_books",
            "toc_files",
            "article_refs",
            "source_pages",
            "sections",
            "section_collisions",
        )
        return {
            table: int(self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in tables
        }

    def source_page_status_counts(self, *, only_code: str | None = None) -> dict[str, int]:
        params: list[object] = []
        query = """
            SELECT sp.fetch_status, COUNT(*)
            FROM source_pages sp
            JOIN code_books cb
              ON cb.id = sp.code_id
        """
        if only_code:
            query += " WHERE cb.code_abbrev = ?"
            params.append(only_code)
        query += " GROUP BY sp.fetch_status ORDER BY sp.fetch_status"
        return {
            str(status): int(count)
            for status, count in self.conn.execute(query, params).fetchall()
        }
