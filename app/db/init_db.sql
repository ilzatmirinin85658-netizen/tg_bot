create table articles (
    id         uuid primary key default gen_random_uuid(),
    url        text unique not null,
    title      text not null,
    meaningful_title text,
    summary    text,
    ai_score   int,
    is_sent    boolean default false,
    created_at timestamptz default now()
);

create table users (
    id         int8 primary key,  -- telegram user id
    created_at timestamptz default now()
);
