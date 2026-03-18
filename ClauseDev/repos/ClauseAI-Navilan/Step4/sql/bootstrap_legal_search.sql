\set ON_ERROR_STOP on

\echo 'Bootstrapping Step4 U.S. Code search objects'
\connect uscode_local

CREATE INDEX IF NOT EXISTS idx_step4_usc_sections_search
    ON public.usc_nodes
    USING GIN (
        to_tsvector(
            'english',
            COALESCE(citation, '') || ' ' ||
            COALESCE(label, '') || ' ' ||
            COALESCE(heading, '') || ' ' ||
            COALESCE(breadcrumb, '') || ' ' ||
            COALESCE(content_text, '') || ' ' ||
            COALESCE(full_text, '')
        )
    )
    WHERE kind = 'section';

CREATE INDEX IF NOT EXISTS idx_step4_usc_provisions_search
    ON public.usc_provisions
    USING GIN (
        to_tsvector(
            'english',
            COALESCE(citation, '') || ' ' ||
            COALESCE(heading, '') || ' ' ||
            COALESCE(direct_text, '') || ' ' ||
            COALESCE(full_text, '')
        )
    );

CREATE OR REPLACE VIEW public.step4_usc_section_search AS
SELECT
    s.identifier AS document_id,
    'section'::TEXT AS source_kind,
    s.identifier AS section_identifier,
    s.title_number,
    s.citation,
    s.heading,
    s.breadcrumb AS hierarchy_path,
    s.cornell_url AS source_url,
    COALESCE(s.full_text, s.content_text, '') AS body_text
FROM public.usc_sections s;

CREATE OR REPLACE VIEW public.step4_usc_provision_search AS
SELECT
    p.identifier AS document_id,
    'provision'::TEXT AS source_kind,
    p.section_identifier,
    p.title_number,
    p.citation,
    COALESCE(p.heading, s.heading) AS heading,
    s.breadcrumb AS hierarchy_path,
    s.cornell_url AS source_url,
    COALESCE(p.full_text, p.direct_text, '') AS body_text
FROM public.usc_provisions p
JOIN public.usc_sections s
  ON s.identifier = p.section_identifier;

\echo 'Verified objects'
SELECT to_regclass('public.idx_step4_usc_sections_search') AS usc_sections_search_index;
SELECT to_regclass('public.idx_step4_usc_provisions_search') AS usc_provisions_search_index;
SELECT EXISTS (
    SELECT 1
    FROM pg_views
    WHERE schemaname = 'public'
      AND viewname = 'step4_usc_section_search'
) AS has_step4_usc_section_search;
SELECT EXISTS (
    SELECT 1
    FROM pg_views
    WHERE schemaname = 'public'
      AND viewname = 'step4_usc_provision_search'
) AS has_step4_usc_provision_search;
