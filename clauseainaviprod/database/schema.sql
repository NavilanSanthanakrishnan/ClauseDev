create table if not exists bills (
    bill_id text primary key,
    identifier text not null,
    jurisdiction text not null,
    state_code text not null,
    session_name text not null,
    status text not null,
    outcome text not null,
    sponsor text not null,
    committee text not null,
    title text not null,
    summary text not null,
    excerpt text not null,
    full_text text not null,
    source_url text,
    latest_action_date text,
    topics_json text not null
);

create virtual table if not exists bill_fts using fts5 (
    bill_id unindexed,
    identifier,
    title,
    summary,
    full_text,
    sponsor,
    committee,
    jurisdiction,
    topics,
    tokenize = 'porter unicode61'
);

create table if not exists bill_vectors (
    bill_id text primary key references bills(bill_id) on delete cascade,
    embedding_json text not null
);

create index if not exists idx_bills_identifier on bills(identifier);
create index if not exists idx_bills_jurisdiction on bills(jurisdiction);
create index if not exists idx_bills_state_code on bills(state_code);
create index if not exists idx_bills_status on bills(status);
create index if not exists idx_bills_outcome on bills(outcome);
create index if not exists idx_bills_latest_action_date on bills(latest_action_date);

