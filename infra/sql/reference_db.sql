create extension if not exists pg_trgm;
create extension if not exists postgres_fdw;

drop schema if exists search cascade;
drop schema if exists law cascade;
drop schema if exists bill cascade;

drop schema if exists ingest_openstates cascade;
drop schema if exists ingest_california cascade;
drop schema if exists ingest_legal_index cascade;
drop schema if exists ingest_uscode cascade;

drop server if exists openstates_src cascade;
drop server if exists california_code_src cascade;
drop server if exists legal_index_src cascade;
drop server if exists uscode_src cascade;

create schema bill;
create schema law;
create schema search;
create schema ingest_openstates;
create schema ingest_california;
create schema ingest_legal_index;
create schema ingest_uscode;

create server openstates_src foreign data wrapper postgres_fdw options (dbname 'openstates');
create server california_code_src foreign data wrapper postgres_fdw options (dbname 'california_code');
create server legal_index_src foreign data wrapper postgres_fdw options (dbname 'clause_legal_index');
create server uscode_src foreign data wrapper postgres_fdw options (dbname 'uscode_local');

do $$
begin
    execute format(
        'create user mapping for %I server openstates_src options (user %L)',
        current_user,
        current_user
    );
exception when duplicate_object then null;
end $$;

do $$
begin
    execute format(
        'create user mapping for %I server california_code_src options (user %L)',
        current_user,
        current_user
    );
exception when duplicate_object then null;
end $$;

do $$
begin
    execute format(
        'create user mapping for %I server legal_index_src options (user %L)',
        current_user,
        current_user
    );
exception when duplicate_object then null;
end $$;

do $$
begin
    execute format(
        'create user mapping for %I server uscode_src options (user %L)',
        current_user,
        current_user
    );
exception when duplicate_object then null;
end $$;

import foreign schema public limit to (
    opencivicdata_bill,
    opencivicdata_billabstract,
    opencivicdata_billaction,
    opencivicdata_billversion,
    opencivicdata_billversionlink,
    opencivicdata_billsource,
    opencivicdata_jurisdiction,
    opencivicdata_legislativesession,
    opencivicdata_organization,
    opencivicdata_searchablebill,
    opencivicdata_votecount,
    opencivicdata_voteevent
) from server openstates_src into ingest_openstates;

import foreign schema public limit to (
    official_codes,
    official_law_sections,
    official_law_toc
) from server california_code_src into ingest_california;

import foreign schema public limit to (
    legal_aliases,
    legal_documents,
    legal_references,
    legal_semantic_profiles
) from server legal_index_src into ingest_legal_index;

import foreign schema public limit to (
    usc_nodes,
    usc_provisions,
    usc_references
) from server uscode_src into ingest_uscode;

create table bill.bills as
with latest_source as (
    select distinct on (bill_id)
        bill_id,
        url
    from ingest_openstates.opencivicdata_billsource
    order by bill_id, id desc
),
abstracts as (
    select
        bill_id,
        string_agg(abstract, E'\n\n' order by id::text) as summary_text
    from ingest_openstates.opencivicdata_billabstract
    group by bill_id
),
searchable as (
    select
        bill_id,
        all_titles
    from ingest_openstates.opencivicdata_searchablebill
    where is_error = false
),
base as (
    select
        b.id as bill_id,
        j.id as jurisdiction_id,
        j.name as jurisdiction_name,
        j.classification as jurisdiction_type,
        case
            when j.id like '%/state:%' then lower(split_part(split_part(j.id, '/state:', 2), '/', 1))
            else null
        end as state_code,
        s.id::text as session_id,
        s.identifier as session_identifier,
        s.name as session_name,
        b.identifier,
        b.title,
        b.classification,
        b.subject as subject_terms,
        coalesce(a.summary_text, b.title) as summary_text,
        b.latest_action_description as status_text,
        case
            when lower(b.latest_action_description) like '%chapter%'
              or lower(b.latest_action_description) like '%signed%'
              or lower(b.latest_action_description) like '%became law%'
              or lower(b.latest_action_description) like '%approved by governor%'
            then 'enacted'
            when lower(b.latest_action_description) like '%veto%'
            then 'vetoed'
            when lower(b.latest_action_description) like '%failed%'
              or lower(b.latest_action_description) like '%died%'
              or lower(b.latest_action_description) like '%dead%'
              or lower(b.latest_action_description) like '%indefinitely postponed%'
              or lower(b.latest_action_description) like '%defeated%'
              or lower(b.latest_action_description) like '%rejected%'
              or lower(b.latest_action_description) like '%withdrawn%'
            then 'failed_or_dead'
            when b.latest_passage_date ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
            then 'passed_not_enacted'
            else 'other_or_in_progress'
        end as derived_status,
        case when b.first_action_date ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' then b.first_action_date::date end as first_action_date,
        case when b.latest_action_date ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' then b.latest_action_date::date end as latest_action_date,
        case when b.latest_passage_date ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' then b.latest_passage_date::date end as latest_passage_date,
        null::text as bill_url,
        ls.url as primary_source_url,
        null::text as full_text,
        md5(coalesce(a.summary_text, b.title)) as text_hash,
        jsonb_build_object(
            'all_titles', sb.all_titles,
            'extras', b.extras,
            'citations', b.citations
        ) as metadata_json,
        b.updated_at as updated_at
    from ingest_openstates.opencivicdata_bill b
    join ingest_openstates.opencivicdata_legislativesession s
      on s.id = b.legislative_session_id
    join ingest_openstates.opencivicdata_jurisdiction j
      on j.id = s.jurisdiction_id
    left join latest_source ls
      on ls.bill_id = b.id
    left join abstracts a
      on a.bill_id = b.id
    left join searchable sb
      on sb.bill_id = b.id
    where 'bill' = any(b.classification)
)
select *
from base;

alter table bill.bills add primary key (bill_id);
create index idx_bill_bills_identifier on bill.bills (identifier);
create index idx_bill_bills_state_code on bill.bills (state_code);
create index idx_bill_bills_status on bill.bills (derived_status);
create index idx_bill_bills_title_trgm on bill.bills using gin (title gin_trgm_ops);
create index idx_bill_bills_summary_trgm on bill.bills using gin (summary_text gin_trgm_ops);

create table bill.bill_versions as
with latest_version_link as (
    select distinct on (version_id)
        version_id,
        url,
        media_type
    from ingest_openstates.opencivicdata_billversionlink
    order by version_id, id desc
),
ranked_versions as (
    select
        v.id::text as version_id,
        v.bill_id,
        v.note,
        case when v.date ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' then v.date::date end as version_date,
        v.classification,
        vl.url as source_url,
        vl.media_type,
        row_number() over (
            partition by v.bill_id
            order by case when v.date ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' then v.date::date end desc nulls last, v.id desc
        ) as version_rank
    from ingest_openstates.opencivicdata_billversion v
    left join latest_version_link vl
      on vl.version_id = v.id
)
select
    version_id,
    bill_id,
    note,
    version_date,
    source_url,
    media_type,
    null::text as extracted_text,
    version_rank = 1 as is_latest
from ranked_versions;

alter table bill.bill_versions add primary key (version_id);
create index idx_bill_versions_bill_id on bill.bill_versions (bill_id);

create table bill.bill_actions as
select
    a.id::text as action_id,
    a.bill_id,
    case when a.date ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' then a.date::date end as action_date,
    a.description,
    a.classification,
    o.name as organization_name
from ingest_openstates.opencivicdata_billaction a
left join ingest_openstates.opencivicdata_organization o
  on o.id = a.organization_id;

create index idx_bill_actions_bill_id on bill.bill_actions (bill_id);

create table bill.bill_vote_summary as
with ranked_vote_events as (
    select
        ve.id,
        ve.bill_id,
        o.name as chamber,
        ve.result,
        case when ve.start_date ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' then ve.start_date::date end as vote_date,
        row_number() over (
            partition by ve.bill_id, coalesce(o.name, ve.organization_id)
            order by case when ve.start_date ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' then ve.start_date::date end desc nulls last, ve.updated_at desc
        ) as vote_rank
    from ingest_openstates.opencivicdata_voteevent ve
    left join ingest_openstates.opencivicdata_organization o
      on o.id = ve.organization_id
    where ve.bill_id is not null
)
select
    r.bill_id,
    coalesce(r.chamber, 'Unknown') as chamber,
    sum(case when lower(vc.option) in ('yes', 'aye', 'pass') then vc.value else 0 end)::integer as yes_count,
    sum(case when lower(vc.option) in ('no', 'nay', 'fail') then vc.value else 0 end)::integer as no_count,
    sum(case when lower(vc.option) not in ('yes', 'aye', 'pass', 'no', 'nay', 'fail') then vc.value else 0 end)::integer as other_count,
    max(r.vote_date) as vote_date,
    max(r.result) as result_text
from ranked_vote_events r
left join ingest_openstates.opencivicdata_votecount vc
  on vc.vote_event_id = r.id
where r.vote_rank = 1
group by r.bill_id, coalesce(r.chamber, 'Unknown');

create index idx_bill_vote_summary_bill_id on bill.bill_vote_summary (bill_id);

create table law.ca_sections as
with headings as (
    select
        s.id,
        div.heading as division_heading,
        tit.heading as title_heading,
        part.heading as part_heading,
        chap.heading as chapter_heading,
        art.heading as article_heading
    from ingest_california.official_law_sections s
    left join lateral (
        select t.heading
        from ingest_california.official_law_toc t
        where t.law_code = s.law_code
          and t.division is not distinct from s.division
          and t.title_num is null
          and t.part_num is null
          and t.chapter_num is null
          and t.article_num is null
        order by t.node_sequence
        limit 1
    ) div on true
    left join lateral (
        select t.heading
        from ingest_california.official_law_toc t
        where t.law_code = s.law_code
          and t.division is not distinct from s.division
          and t.title_num is not distinct from s.title_num
          and t.part_num is null
          and t.chapter_num is null
          and t.article_num is null
          and s.title_num is not null
        order by t.node_sequence
        limit 1
    ) tit on true
    left join lateral (
        select t.heading
        from ingest_california.official_law_toc t
        where t.law_code = s.law_code
          and t.division is not distinct from s.division
          and t.title_num is not distinct from s.title_num
          and t.part_num is not distinct from s.part_num
          and t.chapter_num is null
          and t.article_num is null
          and s.part_num is not null
        order by t.node_sequence
        limit 1
    ) part on true
    left join lateral (
        select t.heading
        from ingest_california.official_law_toc t
        where t.law_code = s.law_code
          and t.division is not distinct from s.division
          and t.title_num is not distinct from s.title_num
          and t.part_num is not distinct from s.part_num
          and t.chapter_num is not distinct from s.chapter_num
          and t.article_num is null
          and s.chapter_num is not null
        order by t.node_sequence
        limit 1
    ) chap on true
    left join lateral (
        select t.heading
        from ingest_california.official_law_toc t
        where t.law_code = s.law_code
          and t.division is not distinct from s.division
          and t.title_num is not distinct from s.title_num
          and t.part_num is not distinct from s.part_num
          and t.chapter_num is not distinct from s.chapter_num
          and t.article_num is not distinct from s.article_num
          and s.article_num is not null
        order by t.node_sequence
        limit 1
    ) art on true
)
select
    s.id as document_id,
    s.law_code,
    c.title as code_title,
    s.section_num,
    s.law_code || ' ' || s.section_num as citation,
    s.division,
    s.title_num,
    s.part_num,
    s.chapter_num,
    s.article_num,
    concat_ws(' > ', h.division_heading, h.title_heading, h.part_heading, h.chapter_heading, h.article_heading) as hierarchy_path,
    coalesce(h.article_heading, h.chapter_heading, h.part_heading, h.title_heading, h.division_heading) as heading_text,
    s.history as history_text,
    s.content_text as body_text,
    s.content_xml,
    s.effective_date,
    s.active_flg = 'Y' as active_flag,
    s.display_url as source_url,
    s.search_vector
from ingest_california.official_law_sections s
join ingest_california.official_codes c
  on c.code = s.law_code
join headings h
  on h.id = s.id;

alter table law.ca_sections add primary key (document_id);
create index idx_law_ca_sections_citation on law.ca_sections (citation);
create index idx_law_ca_sections_heading_trgm on law.ca_sections using gin (heading_text gin_trgm_ops);

create table law.usc_sections as
select
    identifier as document_id,
    title_number,
    citation,
    heading as heading_text,
    breadcrumb as hierarchy_path,
    cornell_url as source_url,
    coalesce(full_text, content_text, '') as body_text,
    updated_at
from ingest_uscode.usc_nodes
where kind = 'section';

alter table law.usc_sections add primary key (document_id);
create index idx_law_usc_sections_citation on law.usc_sections (citation);
create index idx_law_usc_sections_heading_trgm on law.usc_sections using gin (heading_text gin_trgm_ops);

create table law.legal_documents as
select *
from ingest_legal_index.legal_documents;

alter table law.legal_documents add primary key (document_id);
create index idx_law_legal_documents_jurisdiction on law.legal_documents (jurisdiction);
create index idx_law_legal_documents_citation on law.legal_documents (normalized_citation);
create index idx_law_legal_documents_heading_trgm on law.legal_documents using gin (heading gin_trgm_ops);
create index idx_law_legal_documents_search on law.legal_documents using gin (search_text);

create table law.legal_aliases as
select *
from ingest_legal_index.legal_aliases;

create index idx_law_legal_aliases_lookup on law.legal_aliases (normalized_alias);

create table law.legal_references as
select *
from ingest_legal_index.legal_references;

create index idx_law_legal_references_lookup on law.legal_references (normalized_referenced_citation);

create table law.legal_semantic_profiles as
select *
from ingest_legal_index.legal_semantic_profiles;

alter table law.legal_semantic_profiles add primary key (document_id);
create index idx_law_legal_semantic_profiles_search on law.legal_semantic_profiles using gin (profile_search);

create view search.bill_search_docs as
select
    bill_id,
    identifier,
    title,
    jurisdiction_name,
    state_code,
    derived_status,
    latest_action_date,
    coalesce(full_text, summary_text, title) as document_text
from bill.bills;

create view search.law_search_docs as
select
    document_id,
    citation,
    jurisdiction,
    coalesce(heading, hierarchy_path, citation) as display_title,
    body_text,
    source_url
from law.legal_documents;
