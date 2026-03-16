CREATE EXTENSION IF NOT EXISTS pg_trgm;

DROP VIEW IF EXISTS legal_document_search;
DROP VIEW IF EXISTS legal_semantic_search;
DROP TABLE IF EXISTS legal_references;
DROP TABLE IF EXISTS legal_aliases;
DROP TABLE IF EXISTS legal_semantic_profiles;
DROP TABLE IF EXISTS legal_documents;

CREATE TABLE legal_documents (
    document_id TEXT PRIMARY KEY,
    source_system TEXT NOT NULL,
    source_family TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    jurisdiction TEXT NOT NULL,
    citation TEXT NOT NULL,
    normalized_citation TEXT NOT NULL,
    title_number TEXT,
    title_label TEXT,
    heading TEXT,
    hierarchy_path TEXT,
    source_url TEXT,
    body_text TEXT NOT NULL,
    effective_date TEXT,
    active_flag BOOLEAN,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    search_text TSVECTOR GENERATED ALWAYS AS (
        to_tsvector(
            'english',
            COALESCE(citation, '') || ' ' ||
            COALESCE(title_label, '') || ' ' ||
            COALESCE(heading, '') || ' ' ||
            COALESCE(hierarchy_path, '') || ' ' ||
            COALESCE(body_text, '')
        )
    ) STORED
);

CREATE INDEX idx_legal_documents_source ON legal_documents (source_system, source_family, source_kind);
CREATE INDEX idx_legal_documents_jurisdiction ON legal_documents (jurisdiction);
CREATE INDEX idx_legal_documents_normalized_citation ON legal_documents (normalized_citation);
CREATE INDEX idx_legal_documents_heading_trgm ON legal_documents USING GIN (heading gin_trgm_ops);
CREATE INDEX idx_legal_documents_search ON legal_documents USING GIN (search_text);

CREATE TABLE legal_aliases (
    document_id TEXT NOT NULL REFERENCES legal_documents(document_id) ON DELETE CASCADE,
    alias TEXT NOT NULL,
    normalized_alias TEXT NOT NULL,
    alias_kind TEXT NOT NULL DEFAULT 'citation',
    PRIMARY KEY (document_id, normalized_alias)
);

CREATE INDEX idx_legal_aliases_lookup ON legal_aliases (normalized_alias);

CREATE TABLE legal_references (
    document_id TEXT NOT NULL REFERENCES legal_documents(document_id) ON DELETE CASCADE,
    referenced_citation TEXT NOT NULL,
    normalized_referenced_citation TEXT NOT NULL,
    reference_text TEXT NOT NULL,
    reference_type TEXT NOT NULL DEFAULT 'citation'
);

CREATE INDEX idx_legal_references_document ON legal_references (document_id);
CREATE INDEX idx_legal_references_lookup ON legal_references (normalized_referenced_citation);

CREATE TABLE legal_semantic_profiles (
    document_id TEXT PRIMARY KEY REFERENCES legal_documents(document_id) ON DELETE CASCADE,
    domains JSONB NOT NULL DEFAULT '[]'::jsonb,
    risk_tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    obligations JSONB NOT NULL DEFAULT '[]'::jsonb,
    permissions JSONB NOT NULL DEFAULT '[]'::jsonb,
    thresholds JSONB NOT NULL DEFAULT '[]'::jsonb,
    profile_text TEXT NOT NULL,
    profile_search TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('english', COALESCE(profile_text, ''))
    ) STORED
);

CREATE INDEX idx_legal_semantic_profiles_search ON legal_semantic_profiles USING GIN (profile_search);
CREATE INDEX idx_legal_semantic_profiles_domains ON legal_semantic_profiles USING GIN (domains);
CREATE INDEX idx_legal_semantic_profiles_risk_tags ON legal_semantic_profiles USING GIN (risk_tags);

CREATE VIEW legal_document_search AS
SELECT
    document_id,
    source_system,
    source_family,
    source_kind,
    jurisdiction,
    citation,
    normalized_citation,
    title_number,
    title_label,
    heading,
    hierarchy_path,
    source_url,
    effective_date,
    active_flag,
    metadata,
    body_text,
    search_text
FROM legal_documents;

CREATE VIEW legal_semantic_search AS
SELECT
    d.document_id,
    d.source_system,
    d.source_family,
    d.source_kind,
    d.jurisdiction,
    d.citation,
    d.normalized_citation,
    d.title_number,
    d.title_label,
    d.heading,
    d.hierarchy_path,
    d.source_url,
    d.effective_date,
    d.active_flag,
    d.metadata,
    d.body_text,
    p.domains,
    p.risk_tags,
    p.obligations,
    p.permissions,
    p.thresholds,
    p.profile_text,
    p.profile_search
FROM legal_documents d
JOIN legal_semantic_profiles p
  ON p.document_id = d.document_id;
