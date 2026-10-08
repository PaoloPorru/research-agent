-- Esegui questo script nel SQL Editor di Supabase (una sola volta).

create table if not exists memories (
  id bigserial primary key,
  source text not null,
  kind text not null default 'nota',          -- 'nota' | 'documento'
  content text not null,
  created_at timestamptz not null default now(),
  fts tsvector generated always as (to_tsvector('italian', content)) stored
);

create index if not exists memories_fts_idx on memories using gin (fts);
create index if not exists memories_source_idx on memories (source);

-- Nessuna policy: solo la chiave "service role" (usata dal backend) può accedere.
alter table memories enable row level security;

create or replace function search_memories(q text, n int default 6)
returns table(id bigint, source text, kind text, content text, rank real)
language sql stable as $$
  select m.id, m.source, m.kind, m.content,
         ts_rank(m.fts, to_tsquery('italian', q)) as rank
  from memories m
  where m.fts @@ to_tsquery('italian', q)
  order by ts_rank(m.fts, to_tsquery('italian', q)) desc
  limit n;
$$;

create or replace function list_sources()
returns table(source text, kind text, chunks bigint, created_at timestamptz)
language sql stable as $$
  select m.source, m.kind, count(*), max(m.created_at)
  from memories m
  where m.kind <> 'nota'
  group by m.source, m.kind
  order by max(m.created_at) desc;
$$;
