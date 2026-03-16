#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import io
import sys
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from pathlib import Path

import psycopg


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "sql" / "schema_official_california_codes_postgres.sql"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Load official California code data from a PUBINFO zip into PostgreSQL.")
    parser.add_argument(
        "--zip",
        default=str(ROOT / "cache" / "pubinfo_2025.zip"),
        help="Path to the official PUBINFO zip archive.",
    )
    parser.add_argument(
        "--pg-dsn",
        default="host=127.0.0.1 port=55432 dbname=california_code user=navilan",
        help="Target PostgreSQL DSN.",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Truncate the official California code tables before loading.",
    )
    return parser


def parse_timestamp(value: str | None) -> datetime | None:
    if not value or value == "NULL":
        return None
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def parse_nullable(value: str | None) -> str | None:
    if value is None or value == "NULL":
        return None
    return value


def iter_dat_rows(zf: zipfile.ZipFile, member: str):
    with zf.open(member) as handle:
        text_stream = io.TextIOWrapper(handle, encoding="utf-8", newline="")
        reader = csv.reader(text_stream, delimiter="\t", quotechar="`")
        for row in reader:
            yield row


def parse_content_xml(raw_xml: str) -> str:
    try:
        root = ET.fromstring(raw_xml)
    except ET.ParseError:
        return " ".join(raw_xml.replace("\n", " ").split())

    paragraphs: list[str] = []
    for elem in root.iter():
        tag = elem.tag.rsplit("}", 1)[-1]
        if tag == "p":
            text = " ".join("".join(elem.itertext()).split())
            if text:
                paragraphs.append(text)

    if paragraphs:
        return "\n\n".join(paragraphs)
    return " ".join("".join(root.itertext()).split())


def load_codes(cur: psycopg.Cursor, zf: zipfile.ZipFile) -> int:
    rows = [
        (row[0], row[1])
        for row in iter_dat_rows(zf, "CODES_TBL.dat")
        if len(row) >= 2
    ]
    with cur.copy("COPY official_codes (code, title) FROM STDIN") as copy:
        for row in rows:
            copy.write_row(row)
    return len(rows)


def load_law_toc(cur: psycopg.Cursor, zf: zipfile.ZipFile) -> int:
    count = 0
    with cur.copy(
        """
        COPY official_law_toc (
            law_code, division, title_num, part_num, chapter_num, article_num, heading,
            active_flg, trans_uid, trans_update, node_sequence, node_level, node_position,
            node_treepath, contains_law_sections, history_note, op_statutes, op_chapter, op_section
        ) FROM STDIN
        """
    ) as copy:
        for row in iter_dat_rows(zf, "LAW_TOC_TBL.dat"):
            copy.write_row(
                (
                    row[0],
                    parse_nullable(row[1]),
                    parse_nullable(row[2]),
                    parse_nullable(row[3]),
                    parse_nullable(row[4]),
                    parse_nullable(row[5]),
                    row[6],
                    parse_nullable(row[7]),
                    parse_nullable(row[8]),
                    parse_timestamp(row[9]),
                    int(row[10]) if row[10] != "NULL" else None,
                    int(row[11]) if row[11] != "NULL" else None,
                    int(row[12]) if row[12] != "NULL" else None,
                    row[13],
                    parse_nullable(row[14]),
                    parse_nullable(row[15]),
                    parse_nullable(row[16]),
                    parse_nullable(row[17]),
                    parse_nullable(row[18]),
                )
            )
            count += 1
    return count


def load_law_toc_sections(cur: psycopg.Cursor, zf: zipfile.ZipFile) -> int:
    count = 0
    with cur.copy(
        """
        COPY official_law_toc_sections (
            id, law_code, node_treepath, section_num, section_order, title_text,
            op_statutes, op_chapter, op_section, trans_uid, trans_update,
            law_section_version_id, seq_num
        ) FROM STDIN
        """
    ) as copy:
        for row in iter_dat_rows(zf, "LAW_TOC_SECTIONS_TBL.dat"):
            copy.write_row(
                (
                    row[0],
                    row[1],
                    row[2],
                    row[3],
                    int(row[4]) if row[4] != "NULL" else None,
                    parse_nullable(row[5]),
                    parse_nullable(row[6]),
                    parse_nullable(row[7]),
                    parse_nullable(row[8]),
                    parse_nullable(row[9]),
                    parse_timestamp(row[10]),
                    parse_nullable(row[11]),
                    int(row[12]) if row[12] != "NULL" else None,
                )
            )
            count += 1
    return count


def load_law_sections(cur: psycopg.Cursor, zf: zipfile.ZipFile) -> int:
    count = 0
    with cur.copy(
        """
        COPY official_law_sections (
            id, law_code, section_num, op_statutes, op_chapter, op_section, effective_date,
            law_section_version_id, division, title_num, part_num, chapter_num, article_num,
            history, content_xml, content_text, active_flg, trans_uid, trans_update
        ) FROM STDIN
        """
    ) as copy:
        for row in iter_dat_rows(zf, "LAW_SECTION_TBL.dat"):
            lob_name = row[14]
            with zf.open(lob_name) as lob_handle:
                content_xml = lob_handle.read().decode("utf-8", "ignore")
            content_text = parse_content_xml(content_xml)
            copy.write_row(
                (
                    row[0],
                    row[1],
                    row[2],
                    parse_nullable(row[3]),
                    parse_nullable(row[4]),
                    parse_nullable(row[5]),
                    parse_timestamp(row[6]),
                    parse_nullable(row[7]),
                    parse_nullable(row[8]),
                    parse_nullable(row[9]),
                    parse_nullable(row[10]),
                    parse_nullable(row[11]),
                    parse_nullable(row[12]),
                    parse_nullable(row[13]),
                    content_xml,
                    content_text,
                    parse_nullable(row[15]),
                    parse_nullable(row[16]),
                    parse_timestamp(row[17]),
                )
            )
            count += 1
            if count % 10000 == 0:
                print(f"official_law_sections: {count} rows loaded", flush=True)
    return count


def main() -> None:
    args = build_parser().parse_args()
    zip_path = Path(args.zip).expanduser().resolve()
    if not zip_path.exists():
        raise SystemExit(f"ZIP file not found: {zip_path}")

    with zipfile.ZipFile(zip_path) as zf, psycopg.connect(args.pg_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
            if args.truncate:
                cur.execute(
                    """
                    TRUNCATE TABLE
                        official_law_toc_sections,
                        official_law_toc,
                        official_law_sections,
                        official_codes
                    RESTART IDENTITY CASCADE
                    """
                )
        conn.commit()

        with conn.cursor() as cur:
            code_count = load_codes(cur, zf)
            print(f"official_codes: {code_count} rows", flush=True)
        conn.commit()

        with conn.cursor() as cur:
            toc_count = load_law_toc(cur, zf)
            print(f"official_law_toc: {toc_count} rows", flush=True)
        conn.commit()

        with conn.cursor() as cur:
            toc_sections_count = load_law_toc_sections(cur, zf)
            print(f"official_law_toc_sections: {toc_sections_count} rows", flush=True)
        conn.commit()

        with conn.cursor() as cur:
            section_count = load_law_sections(cur, zf)
            print(f"official_law_sections: {section_count} rows", flush=True)
        conn.commit()

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM official_codes),
                    (SELECT COUNT(*) FROM official_law_toc),
                    (SELECT COUNT(*) FROM official_law_toc_sections),
                    (SELECT COUNT(*) FROM official_law_sections)
                """
            )
            counts = cur.fetchone()
            print(
                "official_counts:",
                {
                    "official_codes": counts[0],
                    "official_law_toc": counts[1],
                    "official_law_toc_sections": counts[2],
                    "official_law_sections": counts[3],
                },
                flush=True,
            )


if __name__ == "__main__":
    sys.exit(main())
