-- 002BOOK 백엔드 스키마
-- 모든 테이블은 RLS를 켜고 정책을 두지 않는다 → 브라우저(anon 키)로는 아무것도 읽고 쓸 수 없고,
-- Edge Function(api)이 service_role 키로만 접근한다. 접근 규칙은 api 함수 안의 rules.ts에서 판단한다.

create table if not exists public.docs (
  path        text primary key,            -- 예: progress/kotang77
  parent      text not null,               -- 예: progress
  id          text not null,               -- 예: kotang77
  data        jsonb not null default '{}'::jsonb,
  owner       text,                         -- 처음 만든 회원 아이디 (수정·삭제 권한 판단용)
  version     integer not null default 1,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create index if not exists docs_parent_idx on public.docs (parent);
create index if not exists docs_parent_updated_idx on public.docs (parent, updated_at desc);

-- 로그인 비밀 정보 (members 문서에서 분리 보관, 브라우저로는 절대 내려가지 않음)
create table if not exists public.accounts (
  id          text primary key,            -- 앱 아이디 (예: kotang77)
  email       text,
  pw_hash     text not null,
  pw_algo     text not null default 'pbkdf2',  -- 'pbkdf2' | 'legacy-sha256' (이전 게시본에서 옮겨 온 계정)
  pw_salt     text not null,
  must_change boolean not null default false,  -- 임시 비밀번호로 로그인한 경우
  blocked     boolean not null default false,
  guardian_consent jsonb,                  -- 만 14세 미만 법정대리인 동의 기록
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create unique index if not exists accounts_email_idx on public.accounts (lower(email));

create table if not exists public.sessions (
  token_hash  text primary key,            -- sha256(토큰)
  uid         text not null references public.accounts(id) on delete cascade,
  created_at  timestamptz not null default now(),
  expires_at  timestamptz not null,
  user_agent  text
);
create index if not exists sessions_uid_idx on public.sessions (uid);

-- AI 호출량 (회원별 하루 사용량 제한)
create table if not exists public.ai_usage (
  uid   text not null,
  day   date not null default (now() at time zone 'Asia/Seoul')::date,
  calls integer not null default 0,
  input_tokens  bigint not null default 0,
  output_tokens bigint not null default 0,
  primary key (uid, day)
);

-- 결제 (토스페이먼츠)
create table if not exists public.payments (
  order_id    text primary key,
  uid         text not null,
  plan        text not null,
  amount      integer not null,
  status      text not null default 'READY',   -- READY | DONE | CANCELED | FAILED
  payment_key text,
  paid_until  timestamptz,
  raw         jsonb,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create index if not exists payments_uid_idx on public.payments (uid);

-- 업로드 사진은 Storage 버킷 'uploads' (비공개). api 함수가 서명 URL로 내려준다.
insert into storage.buckets (id, name, public)
values ('uploads', 'uploads', false)
on conflict (id) do nothing;

alter table public.docs      enable row level security;
alter table public.accounts  enable row level security;
alter table public.sessions  enable row level security;
alter table public.ai_usage  enable row level security;
alter table public.payments  enable row level security;

-- 원자적 AI 사용량 증가
create or replace function public.bump_ai_usage(p_uid text, p_in bigint, p_out bigint)
returns integer language sql security definer set search_path = public as $$
  insert into ai_usage (uid, day, calls, input_tokens, output_tokens)
  values (p_uid, (now() at time zone 'Asia/Seoul')::date, 1, p_in, p_out)
  on conflict (uid, day) do update
    set calls = ai_usage.calls + 1,
        input_tokens = ai_usage.input_tokens + excluded.input_tokens,
        output_tokens = ai_usage.output_tokens + excluded.output_tokens
  returning calls;
$$;
revoke all on function public.bump_ai_usage(text, bigint, bigint) from public, anon, authenticated;

-- 매일 정리: 만료 세션, 7일 지난 보호자 미동의 가입 신청, 1년 지난 AI 사용 기록
create or replace function public.purge_sessions() returns void language sql security definer set search_path = public as $$
  delete from sessions where expires_at < now();
  delete from docs where path in (select 'members/' || id from accounts where guardian_consent->>'status' = 'pending' and created_at < now() - interval '7 days');
  delete from accounts where guardian_consent->>'status' = 'pending' and created_at < now() - interval '7 days';
  delete from ai_usage where day < (now() - interval '1 year')::date;
$$;

-- pg_cron 이 켜져 있으면 매일 새벽 4시(KST)에 정리
do $$ begin
  if exists (select 1 from pg_extension where extname = 'pg_cron') then
    perform cron.schedule('002book-purge', '0 19 * * *', 'select public.purge_sessions()');
  end if;
end $$;
revoke all on function public.purge_sessions() from public, anon, authenticated;
