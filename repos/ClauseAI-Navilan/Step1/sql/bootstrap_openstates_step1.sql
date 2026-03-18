CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE SCHEMA IF NOT EXISTS step1;

DROP TABLE IF EXISTS step1.bill_search_docs;

CREATE TABLE step1.bill_search_docs AS
WITH latest_searchable_bill AS (
    SELECT DISTINCT ON (sb.bill_id)
        sb.bill_id,
        sb.all_titles,
        sb.search_vector
    FROM public.opencivicdata_searchablebill sb
    WHERE sb.bill_id IS NOT NULL
      AND sb.is_error = false
    ORDER BY sb.bill_id, sb.created_at DESC NULLS LAST
)
SELECT
    b.id AS bill_id,
    b.identifier,
    b.title AS title_text,
    array_to_string(coalesce(b.subject, ARRAY[]::varchar[]), ' ') AS subject_text,
    coalesce(lsb.all_titles, b.title, '') AS all_titles,
    coalesce(b.latest_action_description, '') AS status_text,
    s.jurisdiction_id,
    CASE
        WHEN j.id LIKE '%/state:%' THEN lower(split_part(split_part(j.id, '/state:', 2), '/', 1))
        ELSE NULL
    END AS state_code,
    setweight(to_tsvector('english', coalesce(b.title, '')), 'A')
    || setweight(to_tsvector('english', array_to_string(coalesce(b.subject, ARRAY[]::varchar[]), ' ')), 'A')
    || setweight(to_tsvector('english', coalesce(lsb.all_titles, b.title, '')), 'A')
    || setweight(to_tsvector('english', coalesce(b.latest_action_description, '')), 'B')
    || setweight(coalesce(lsb.search_vector, ''::tsvector), 'B') AS search_vector
FROM public.opencivicdata_bill b
JOIN public.opencivicdata_legislativesession s
  ON s.id = b.legislative_session_id
JOIN public.opencivicdata_jurisdiction j
  ON j.id = s.jurisdiction_id
LEFT JOIN latest_searchable_bill lsb
  ON lsb.bill_id = b.id
WHERE 'bill' = ANY(b.classification);

CREATE INDEX IF NOT EXISTS idx_step1_bill_id
    ON public.opencivicdata_bill (id);

CREATE INDEX IF NOT EXISTS idx_step1_bill_legislative_session_id
    ON public.opencivicdata_bill (legislative_session_id);

CREATE INDEX IF NOT EXISTS idx_step1_bill_classification_gin
    ON public.opencivicdata_bill USING GIN (classification);

CREATE INDEX IF NOT EXISTS idx_step1_bill_subject_gin
    ON public.opencivicdata_bill USING GIN (subject);

CREATE INDEX IF NOT EXISTS idx_step1_bill_title_trgm
    ON public.opencivicdata_bill USING GIN (title gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_step1_searchablebill_search_vector
    ON public.opencivicdata_searchablebill USING GIN (search_vector)
    WHERE is_error = false;

CREATE INDEX IF NOT EXISTS idx_step1_searchablebill_bill_id
    ON public.opencivicdata_searchablebill (bill_id)
    WHERE bill_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_step1_bill_search_docs_bill_id
    ON step1.bill_search_docs (bill_id);

CREATE INDEX IF NOT EXISTS idx_step1_bill_search_docs_search_vector
    ON step1.bill_search_docs USING GIN (search_vector);

CREATE INDEX IF NOT EXISTS idx_step1_bill_search_docs_state_code
    ON step1.bill_search_docs (state_code);

CREATE INDEX IF NOT EXISTS idx_step1_bill_search_docs_jurisdiction_id
    ON step1.bill_search_docs (jurisdiction_id);

CREATE INDEX IF NOT EXISTS idx_step1_bill_search_docs_title_trgm
    ON step1.bill_search_docs USING GIN (title_text gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_step1_bill_search_docs_subject_trgm
    ON step1.bill_search_docs USING GIN (subject_text gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_step1_legislativesession_id
    ON public.opencivicdata_legislativesession (id);

CREATE INDEX IF NOT EXISTS idx_step1_legislativesession_jurisdiction_id
    ON public.opencivicdata_legislativesession (jurisdiction_id);

CREATE INDEX IF NOT EXISTS idx_step1_jurisdiction_id
    ON public.opencivicdata_jurisdiction (id);

CREATE INDEX IF NOT EXISTS idx_step1_billsource_bill_id
    ON public.opencivicdata_billsource (bill_id);

CREATE INDEX IF NOT EXISTS idx_step1_billversion_bill_id
    ON public.opencivicdata_billversion (bill_id);

CREATE INDEX IF NOT EXISTS idx_step1_billdocument_bill_id
    ON public.opencivicdata_billdocument (bill_id);

CREATE INDEX IF NOT EXISTS idx_step1_voteevent_bill_id
    ON public.opencivicdata_voteevent (bill_id);

CREATE INDEX IF NOT EXISTS idx_step1_votecount_vote_event_id
    ON public.opencivicdata_votecount (vote_event_id);

CREATE OR REPLACE VIEW step1.bill_lookup AS
SELECT
    b.id AS bill_id,
    b.identifier,
    b.title,
    b.classification,
    b.subject,
    s.id AS legislative_session_id,
    s.identifier AS session_identifier,
    s.name AS session_name,
    s.classification AS session_classification,
    s.start_date AS session_start_date,
    s.end_date AS session_end_date,
    j.id AS jurisdiction_id,
    j.name AS jurisdiction_name,
    j.classification AS jurisdiction_type,
    j.url AS jurisdiction_url,
    b.first_action_date,
    b.latest_action_date,
    b.latest_action_description,
    b.latest_passage_date,
    CASE
        WHEN lower(b.latest_action_description) LIKE '%chapter%'
          OR lower(b.latest_action_description) LIKE '%signed%'
          OR lower(b.latest_action_description) LIKE '%became law%'
          OR lower(b.latest_action_description) LIKE '%approved by governor%'
        THEN 'enacted'
        WHEN lower(b.latest_action_description) LIKE '%veto%'
        THEN 'vetoed'
        WHEN lower(b.latest_action_description) LIKE '%failed%'
          OR lower(b.latest_action_description) LIKE '%died%'
          OR lower(b.latest_action_description) LIKE '%dead%'
          OR lower(b.latest_action_description) LIKE '%indefinitely postponed%'
          OR lower(b.latest_action_description) LIKE '%defeated%'
          OR lower(b.latest_action_description) LIKE '%rejected%'
          OR lower(b.latest_action_description) LIKE '%withdrawn%'
        THEN 'failed_or_dead'
        WHEN b.latest_passage_date ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}'
        THEN 'passed_not_enacted'
        ELSE 'other_or_in_progress'
    END AS derived_status
FROM public.opencivicdata_bill b
JOIN public.opencivicdata_legislativesession s
  ON s.id = b.legislative_session_id
JOIN public.opencivicdata_jurisdiction j
  ON j.id = s.jurisdiction_id;
