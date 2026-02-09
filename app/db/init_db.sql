create table articles (
    id         uuid primary key default gen_random_uuid(),
    url        text unique not null,
    title      text not null,
    summary    text,
    ai_score   int,
    is_sent    boolean default false,
    created_at timestamptz default now()
);
