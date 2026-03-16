PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS code_books (
    id INTEGER PRIMARY KEY,
    code_abbrev TEXT NOT NULL UNIQUE,
    code_name TEXT NOT NULL,
    source_directory TEXT NOT NULL UNIQUE,
    toc_root_file_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS toc_files (
    id INTEGER PRIMARY KEY,
    code_id INTEGER NOT NULL REFERENCES code_books(id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL UNIQUE,
    division_name TEXT NOT NULL,
    division_url TEXT NOT NULL,
    file_sha256 TEXT NOT NULL,
    article_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_toc_files_code_id
    ON toc_files (code_id);

CREATE TABLE IF NOT EXISTS article_refs (
    id INTEGER PRIMARY KEY,
    code_id INTEGER NOT NULL REFERENCES code_books(id) ON DELETE CASCADE,
    toc_file_id INTEGER NOT NULL REFERENCES toc_files(id) ON DELETE CASCADE,
    ref_kind TEXT NOT NULL DEFAULT 'article',
    article_key TEXT NOT NULL,
    article_url TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    fetch_kind TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (toc_file_id, ref_kind, article_key, canonical_url)
);

CREATE INDEX IF NOT EXISTS idx_article_refs_canonical_url
    ON article_refs (canonical_url);

CREATE INDEX IF NOT EXISTS idx_article_refs_code_id
    ON article_refs (code_id);

CREATE INDEX IF NOT EXISTS idx_article_refs_kind
    ON article_refs (ref_kind, fetch_kind);

CREATE TABLE IF NOT EXISTS source_pages (
    canonical_url TEXT PRIMARY KEY,
    code_id INTEGER NOT NULL REFERENCES code_books(id) ON DELETE CASCADE,
    fetch_kind TEXT NOT NULL,
    http_status INTEGER,
    fetch_status TEXT NOT NULL DEFAULT 'pending',
    fetched_at TEXT,
    html_sha256 TEXT,
    error_message TEXT,
    parsed_section_count INTEGER NOT NULL DEFAULT 0,
    title_text TEXT,
    breadcrumb_text TEXT
);

CREATE INDEX IF NOT EXISTS idx_source_pages_code_status
    ON source_pages (code_id, fetch_status, fetch_kind);

CREATE TABLE IF NOT EXISTS sections (
    id INTEGER PRIMARY KEY,
    code_id INTEGER NOT NULL REFERENCES code_books(id) ON DELETE CASCADE,
    section_number TEXT NOT NULL,
    heading TEXT,
    division_name TEXT,
    chapter_name TEXT,
    article_name TEXT,
    hierarchy_path TEXT,
    display_url TEXT NOT NULL,
    source_page_url TEXT NOT NULL,
    body_text TEXT NOT NULL,
    history_text TEXT,
    text_hash TEXT NOT NULL,
    source_count INTEGER NOT NULL DEFAULT 1,
    first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (code_id, section_number)
);

CREATE INDEX IF NOT EXISTS idx_sections_code_section
    ON sections (code_id, section_number);

CREATE INDEX IF NOT EXISTS idx_sections_hierarchy
    ON sections (hierarchy_path);

CREATE TABLE IF NOT EXISTS section_sources (
    id INTEGER PRIMARY KEY,
    section_id INTEGER NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    source_page_url TEXT NOT NULL REFERENCES source_pages(canonical_url) ON DELETE CASCADE,
    article_ref_id INTEGER REFERENCES article_refs(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (section_id, source_page_url, article_ref_id)
);

CREATE TABLE IF NOT EXISTS section_collisions (
    id INTEGER PRIMARY KEY,
    code_id INTEGER NOT NULL REFERENCES code_books(id) ON DELETE CASCADE,
    section_number TEXT NOT NULL,
    existing_text_hash TEXT NOT NULL,
    incoming_text_hash TEXT NOT NULL,
    existing_source_url TEXT,
    incoming_source_url TEXT NOT NULL,
    observed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_section_collisions_code_section
    ON section_collisions (code_id, section_number);

CREATE VIRTUAL TABLE IF NOT EXISTS section_fts USING fts5(
    section_id UNINDEXED,
    code_abbrev,
    section_number,
    heading,
    hierarchy_path,
    body_text,
    history_text,
    tokenize = 'unicode61'
);

CREATE VIEW IF NOT EXISTS section_search AS
SELECT
    s.id AS section_id,
    c.code_abbrev,
    c.code_name,
    c.code_abbrev || ' ' || s.section_number AS citation,
    s.section_number,
    s.heading,
    s.division_name,
    s.chapter_name,
    s.article_name,
    s.hierarchy_path,
    s.display_url,
    s.source_page_url,
    s.body_text,
    s.history_text,
    s.source_count
FROM sections s
JOIN code_books c
  ON c.id = s.code_id;
