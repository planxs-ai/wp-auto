-- deals_001 — 쿠팡 가격 데이터 딜 엔진 (30일 실증)
-- 밑그림: bid/docs/blueprints/20260907-shopping-affiliate-automation.md §9
-- 원칙: 모든 쓰기는 자연키 UNIQUE + ON CONFLICT (재실행해도 결과 동일) · 원본 보존 · TZ-aware(KST)
-- 적용: Supabase SQL Editor에 붙여넣기(1회). anon 권한은 주지 않는다 — 서비스 롤(GitHub Actions)만 쓴다.

create table if not exists deal_products (
  product_id    text primary key,
  name          text,
  category      text,
  url           text,
  image         text,
  source        text,
  first_seen_at timestamptz not null default now(),
  last_seen_at  timestamptz
);

create table if not exists deal_price_snapshots (
  id            bigserial primary key,
  product_id    text not null references deal_products(product_id) on delete cascade,
  ts            timestamptz not null,
  ts_hour       text not null,               -- 'YYYY-MM-DDTHH:00:00+09:00' — 시간당 1건 자연키
  price         integer not null check (price >= 0),
  discount_rate numeric,
  rocket        boolean,
  rank          integer,
  source        text,
  unique (product_id, ts_hour)
);
create index if not exists deal_snap_pid_ts on deal_price_snapshots (product_id, ts desc);
create index if not exists deal_snap_ts on deal_price_snapshots (ts desc);

create table if not exists deal_events (
  id            bigserial primary key,
  product_id    text not null references deal_products(product_id) on delete cascade,
  kind          text not null check (kind in ('new_low','discount_jump')),
  ts_day        date not null,               -- 같은 상품·같은 종류는 하루 1건
  ts            timestamptz not null default now(),
  channel       text not null check (channel in ('telegram','wordpress','shorts')),
  msg_id        text,
  price         integer,
  low_prev      integer,
  high_prev     integer,
  history_days  integer,
  deeplink      text,
  clicks        integer not null default 0,
  unique (product_id, kind, ts_day, channel)
);
create index if not exists deal_events_day on deal_events (ts_day desc, channel);

create table if not exists deal_runs (
  run_id        text primary key,
  mode          text not null,
  started_at    timestamptz not null,
  finished_at   timestamptz,
  status        text not null default 'RUNNING'
                check (status in ('RUNNING','OK','PARTIAL','ABORTED','UPSTREAM_DOWN')),
  calls         integer default 0,
  errors_count  integer default 0,
  items         integer default 0,
  note          text,
  stats         jsonb,
  version       text
);
create index if not exists deal_runs_started on deal_runs (started_at desc);

create table if not exists deal_api_calls (
  id            bigserial primary key,
  ts            timestamptz not null default now(),
  op            text not null,
  status        text not null,
  ms            integer,
  params        jsonb
);
create index if not exists deal_api_calls_ts_op on deal_api_calls (ts desc, op);

create table if not exists deal_raw_payloads (   -- 원본 보존: 매핑 실패가 데이터 유실이 되면 안 된다
  id            bigserial primary key,
  op            text not null,
  params        jsonb,
  fetched_at    timestamptz not null default now(),
  payload       jsonb
);
create index if not exists deal_raw_fetched on deal_raw_payloads (fetched_at desc);

-- 보안: anon/authenticated에는 아무 권한도 주지 않는다(대시보드 노출 전까지).
alter table deal_products         enable row level security;
alter table deal_price_snapshots  enable row level security;
alter table deal_events           enable row level security;
alter table deal_runs             enable row level security;
alter table deal_api_calls        enable row level security;
alter table deal_raw_payloads     enable row level security;
revoke all on deal_products, deal_price_snapshots, deal_events, deal_runs, deal_api_calls, deal_raw_payloads
  from anon, authenticated;
