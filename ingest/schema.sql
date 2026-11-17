-- Raw layer: what the API said, one row per technology per day.
-- REE revises recent days (provisional figures become consolidated), so rows
-- are upserted and every change is counted in raw.load_runs.

create schema if not exists raw;

create table if not exists raw.ree_generation_daily (
    technology_id    text        not null,
    technology       text        not null,
    renewable_class  text        not null,
    day              date        not null,
    mwh              numeric     not null,
    share            numeric     not null,
    api_last_update  timestamptz,
    first_loaded_at  timestamptz not null default now(),
    updated_at       timestamptz not null default now(),
    primary key (technology_id, day)
);
-- No range checks here on purpose: REE publishes net generation, which can be
-- negative on days a plant's own consumption exceeds its output (coal does this).
-- Raw keeps what the source says; dbt tests decide what is acceptable downstream.

create table if not exists raw.load_runs (
    run_id         bigint generated always as identity primary key,
    started_at     timestamptz not null default now(),
    finished_at    timestamptz,
    start_day      date        not null,
    end_day        date        not null,
    rows_received  integer,
    rows_inserted  integer,
    rows_updated   integer,
    rows_unchanged integer
);
