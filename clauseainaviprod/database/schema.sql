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

create table if not exists users (
    user_id text primary key,
    email text not null unique,
    password_hash text not null,
    display_name text not null,
    created_at text not null,
    updated_at text not null
);

create table if not exists user_sessions (
    session_token text primary key,
    user_id text not null references users(user_id) on delete cascade,
    created_at text not null,
    expires_at text not null
);

create table if not exists projects (
    project_id text primary key,
    owner_user_id text not null references users(user_id) on delete cascade,
    title text not null,
    policy_goal text not null,
    jurisdiction text,
    status text not null,
    stage text not null,
    summary text not null,
    bill_text text not null,
    created_at text not null,
    updated_at text not null
);

create table if not exists project_insights (
    project_id text not null references projects(project_id) on delete cascade,
    insight_type text not null,
    payload_json text not null,
    updated_at text not null,
    primary key (project_id, insight_type)
);

create table if not exists project_messages (
    message_id text primary key,
    project_id text not null references projects(project_id) on delete cascade,
    role text not null,
    content text not null,
    tool_trace_json text not null,
    created_at text not null
);

create index if not exists idx_bills_identifier on bills(identifier);
create index if not exists idx_bills_jurisdiction on bills(jurisdiction);
create index if not exists idx_bills_state_code on bills(state_code);
create index if not exists idx_bills_status on bills(status);
create index if not exists idx_bills_outcome on bills(outcome);
create index if not exists idx_bills_latest_action_date on bills(latest_action_date);
create index if not exists idx_projects_owner_user_id on projects(owner_user_id);
create index if not exists idx_projects_updated_at on projects(updated_at);
create index if not exists idx_project_messages_project_id on project_messages(project_id, created_at);
