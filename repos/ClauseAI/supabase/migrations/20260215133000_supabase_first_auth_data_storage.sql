create extension if not exists pgcrypto;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = timezone('utc', now());
    return new;
end;
$$;

create table if not exists public.app_users (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null unique references auth.users(id) on delete cascade,
    email text,
    username text,
    display_name text,
    approved boolean not null default false,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.user_workflows (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null unique references auth.users(id) on delete cascade,
    workflow_json jsonb not null default '{}'::jsonb,
    current_step text not null default '/',
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.workflow_history (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    title text not null default 'Untitled Workflow',
    reason text not null default 'manual',
    current_step text,
    summary jsonb not null default '{}'::jsonb,
    snapshot jsonb not null default '{}'::jsonb,
    saved_at timestamptz not null default timezone('utc', now())
);

create index if not exists workflow_history_user_saved_idx
    on public.workflow_history (user_id, saved_at desc);

create table if not exists public.user_files (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    bucket text not null,
    path text not null,
    original_name text,
    mime_type text,
    size_bytes bigint,
    created_at timestamptz not null default timezone('utc', now())
);

create unique index if not exists user_files_bucket_path_uidx
    on public.user_files (bucket, path);

create trigger app_users_set_updated_at
before update on public.app_users
for each row
execute function public.set_updated_at();

create trigger user_workflows_set_updated_at
before update on public.user_workflows
for each row
execute function public.set_updated_at();

alter table public.app_users enable row level security;
alter table public.user_workflows enable row level security;
alter table public.workflow_history enable row level security;
alter table public.user_files enable row level security;

drop policy if exists "app_users_select_own" on public.app_users;
create policy "app_users_select_own"
on public.app_users
for select
to authenticated
using (auth.uid() = user_id);

drop policy if exists "app_users_insert_own" on public.app_users;
create policy "app_users_insert_own"
on public.app_users
for insert
to authenticated
with check (auth.uid() = user_id);

drop policy if exists "app_users_update_own" on public.app_users;
create policy "app_users_update_own"
on public.app_users
for update
to authenticated
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

drop policy if exists "user_workflows_select_own" on public.user_workflows;
create policy "user_workflows_select_own"
on public.user_workflows
for select
to authenticated
using (auth.uid() = user_id);

drop policy if exists "user_workflows_insert_own" on public.user_workflows;
create policy "user_workflows_insert_own"
on public.user_workflows
for insert
to authenticated
with check (auth.uid() = user_id);

drop policy if exists "user_workflows_update_own" on public.user_workflows;
create policy "user_workflows_update_own"
on public.user_workflows
for update
to authenticated
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

drop policy if exists "workflow_history_select_own" on public.workflow_history;
create policy "workflow_history_select_own"
on public.workflow_history
for select
to authenticated
using (auth.uid() = user_id);

drop policy if exists "workflow_history_insert_own" on public.workflow_history;
create policy "workflow_history_insert_own"
on public.workflow_history
for insert
to authenticated
with check (auth.uid() = user_id);

drop policy if exists "workflow_history_delete_own" on public.workflow_history;
create policy "workflow_history_delete_own"
on public.workflow_history
for delete
to authenticated
using (auth.uid() = user_id);

drop policy if exists "user_files_select_own" on public.user_files;
create policy "user_files_select_own"
on public.user_files
for select
to authenticated
using (auth.uid() = user_id);

drop policy if exists "user_files_insert_own" on public.user_files;
create policy "user_files_insert_own"
on public.user_files
for insert
to authenticated
with check (auth.uid() = user_id);

drop policy if exists "user_files_delete_own" on public.user_files;
create policy "user_files_delete_own"
on public.user_files
for delete
to authenticated
using (auth.uid() = user_id);

insert into storage.buckets (id, name, public)
values ('business-data', 'business-data', false)
on conflict (id) do nothing;

insert into storage.buckets (id, name, public)
values ('user-files', 'user-files', false)
on conflict (id) do nothing;

drop policy if exists "user_files_storage_select" on storage.objects;
create policy "user_files_storage_select"
on storage.objects
for select
to authenticated
using (
    bucket_id = 'user-files'
    and split_part(name, '/', 1) = auth.uid()::text
);

drop policy if exists "user_files_storage_insert" on storage.objects;
create policy "user_files_storage_insert"
on storage.objects
for insert
to authenticated
with check (
    bucket_id = 'user-files'
    and split_part(name, '/', 1) = auth.uid()::text
);

drop policy if exists "user_files_storage_update" on storage.objects;
create policy "user_files_storage_update"
on storage.objects
for update
to authenticated
using (
    bucket_id = 'user-files'
    and split_part(name, '/', 1) = auth.uid()::text
)
with check (
    bucket_id = 'user-files'
    and split_part(name, '/', 1) = auth.uid()::text
);

drop policy if exists "user_files_storage_delete" on storage.objects;
create policy "user_files_storage_delete"
on storage.objects
for delete
to authenticated
using (
    bucket_id = 'user-files'
    and split_part(name, '/', 1) = auth.uid()::text
);