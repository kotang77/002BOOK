-- 서버(Edge Function, service_role)만 테이블에 접근한다.
-- 새 Supabase 프로젝트는 public 스키마 테이블에 권한을 자동으로 주지 않아서 명시적으로 부여한다.
-- 브라우저용 anon / authenticated 에는 아무 권한도 주지 않는다 (RLS도 켜져 있고 정책이 없다).
grant usage on schema public to service_role;
grant all privileges on all tables in schema public to service_role;
grant all privileges on all sequences in schema public to service_role;
grant execute on all functions in schema public to service_role;
alter default privileges in schema public grant all on tables to service_role;
alter default privileges in schema public grant all on sequences to service_role;
alter default privileges in schema public grant execute on functions to service_role;

revoke all on all tables in schema public from anon, authenticated;
revoke execute on all functions in schema public from anon, authenticated, public;
grant execute on all functions in schema public to service_role;
