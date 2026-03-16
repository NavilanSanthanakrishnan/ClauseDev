DROP VIEW IF EXISTS public.usc_sections;
DROP TABLE IF EXISTS public.usc_references;
DROP TABLE IF EXISTS public.usc_provisions;
DROP TABLE IF EXISTS public.usc_nodes;
DROP TABLE IF EXISTS public.usc_meta;

CREATE TABLE public.usc_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE public.usc_nodes (
    identifier TEXT NOT NULL,
    parent_identifier TEXT,
    title_number TEXT NOT NULL,
    kind TEXT NOT NULL,
    num_value TEXT,
    label TEXT NOT NULL,
    heading TEXT,
    citation TEXT NOT NULL,
    cornell_url TEXT,
    breadcrumb TEXT NOT NULL,
    breadcrumb_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    sort_order INTEGER NOT NULL DEFAULT 0,
    source_file TEXT NOT NULL,
    release_point TEXT NOT NULL,
    status TEXT,
    notes_text TEXT,
    source_credit_text TEXT,
    content_text TEXT,
    full_text TEXT,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE public.usc_provisions (
    identifier TEXT NOT NULL,
    section_identifier TEXT NOT NULL,
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
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE public.usc_references (
    source_table TEXT NOT NULL,
    source_identifier TEXT NOT NULL,
    target_href TEXT NOT NULL,
    target_identifier TEXT,
    target_citation TEXT,
    anchor_text TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ NOT NULL
);
