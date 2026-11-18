// 문서 경로별 읽기·쓰기 권한 (서버에서 강제)
// 이전 게시본은 "로그인한 가족이면 누구나 모든 문서를 읽고 쓸 수 있는" 구조였다.
// 일반 공개 서비스로 바꾸면서, 각 컬렉션을 아래 원칙으로 잠근다.
import { ADMIN_ID, sb } from './lib.ts';

export type Ctx = { uid: string | null; admin: boolean };
export type Row = { path: string; parent: string; id: string; data: Record<string, unknown>; owner: string | null; version: number; updated_at: string };

// 다른 회원에게 보여 주지 않는 회원 정보
const MEMBER_PRIVATE = ['email', 'prefs', 'mustChange', 'pw', 'salt', 'birth', 'guardian', 'gender', 'marketing', 'agreedAt'];
// 회원이 직접 바꿀 수 없는 필드 (서버만 바꿈)
const MEMBER_LOCKED = ['pw', 'salt', 'id', 'birth', 'guardian'];

const top = (path: string) => path.split('/')[0];
// 아이디에 '_'가 들어갈 수 있으므로(예: rich_claire) 잘라 내지 않고 앞뒤가 맞는지로 판단한다
const mineByPrefix = (id: string, me: string) => id.startsWith(me + '_');   // evals/<uid>_..., diaries/<uid>_..., works/<uid>_...
const mineBySuffix = (id: string, me: string) => id.endsWith('_' + me);     // essays/<hid>_<uid>, reviews/<hid>_<uid>
const ownerOf = (row: Row | null) => String((row?.data as Record<string, unknown>)?.uid ?? row?.owner ?? '');

/* ---------- 관계 (친구·가족) ---------- */
const relCache = new Map<string, { at: number; set: Set<string> }>();
export async function related(uid: string): Promise<Set<string>> {
  const c = relCache.get(uid);
  if (c && Date.now() - c.at < 30_000) return c.set;
  const set = new Set<string>();
  const { data: fam } = await sb.from('docs').select('data').eq('parent', 'family')
    .or(`data->>parent.eq.${uid},data->>child.eq.${uid}`);
  for (const r of fam ?? []) {
    const d = r.data as Record<string, string>;
    if (d.status === 'accepted') set.add(d.parent === uid ? d.child : d.parent);
  }
  const { data: fr } = await sb.from('docs').select('data').eq('parent', FRIENDS)
    .or(`data->>a.eq.${uid},data->>b.eq.${uid}`);
  for (const r of fr ?? []) {
    const d = r.data as Record<string, string>;
    if (d.status === 'accepted') set.add(d.a === uid ? d.b : d.a);
  }
  relCache.set(uid, { at: Date.now(), set });
  return set;
}
export const FRIENDS = 'friends';

/* ---------- 읽기 ---------- */
export async function canRead(ctx: Ctx, path: string, row: Row | null): Promise<boolean> {
  const t = top(path), id = path.split('/')[1] ?? '';
  if (t === 'config') return true;                        // 계획표·공지 등: 로그인 전에도 읽음
  if (!ctx.uid) return false;
  if (ctx.admin && t !== 'diaries' && t !== 'dykeys' && t !== 'msgs') return true; // 일기·친구 메시지는 관리자도 못 봄
  const me = ctx.uid, d = (row?.data ?? {}) as Record<string, unknown>;
  switch (t) {
    case 'members': case 'essays': case 'reviews': case 'info': case 'covers': case 'guides':
      return true;
    case 'progress':
      return id === me || (await related(me)).has(id);
    case 'custom': case 'subs':
      return id === me;
    case 'evals':
      return mineByPrefix(id, me) || (await related(me)).has(ownerOf(row));
    case 'works': case 'workimgs': {
      const o = ownerOf(row);
      return o === me || mineByPrefix(id, me) || (await related(me)).has(o);
    }
    case 'diaries': case 'dykeys':
      return id === me || mineByPrefix(id, me);
    case 'msgs': case 'alerts':
      return d.from === me || d.to === me;
    case 'family':
      return d.parent === me || d.child === me;
    case FRIENDS:
      return d.a === me || d.b === me || d.from === me || d.to === me;
    case 'resets':
      return false;
    default:
      return true;
  }
}

/** 읽기 결과를 다른 회원에게 보여 줄 모양으로 다듬는다 */
export function redact(ctx: Ctx, row: Row): Row {
  if (top(row.path) === 'members' && !(ctx.admin || row.id === ctx.uid)) {
    const data = { ...row.data };
    for (const k of MEMBER_PRIVATE) delete data[k];
    return { ...row, data };
  }
  if (top(row.path) === 'members') {
    const data = { ...row.data }; delete data.pw; delete data.salt;
    return { ...row, data };
  }
  return row;
}

/* ---------- 쓰기 ---------- */
export type WriteKind = 'set' | 'update' | 'delete';
export async function canWrite(ctx: Ctx, kind: WriteKind, path: string, existing: Row | null, next: Record<string, unknown> | null): Promise<boolean> {
  if (!ctx.uid) return false;
  const t = top(path), id = path.split('/')[1] ?? '', me = ctx.uid;
  const segs = path.split('/');
  if (segs.length !== 2) return ctx.admin;                // 하위 컬렉션은 쓰지 않음
  const nd = (next ?? {}) as Record<string, unknown>;
  const od = (existing?.data ?? {}) as Record<string, unknown>;
  const ownerOk = !existing || existing.owner === me || existing.owner == null;

  switch (t) {
    case 'config': case 'resets':
      return ctx.admin;
    case 'members':
      if (!existing && kind !== 'delete') return false;   // 가입은 서버(auth.signup)만
      if (kind === 'delete') return ctx.admin;
      return id === me || ctx.admin;
    case 'progress': case 'custom': case 'subs':
      if (t === 'subs' && kind !== 'delete' && !ctx.admin && ['active', 'ended'].includes(String(nd.status)) && od.status !== nd.status && !(od.status === 'cancel_requested' && nd.status === 'active')) return false;
      return id === me || ctx.admin;
    case 'evals': case 'diaries': case 'works':
      return mineByPrefix(id, me) || (ctx.admin && kind === 'delete');
    case 'dykeys':
      return id === me;
    case 'essays': case 'reviews':
      if (kind === 'delete') return mineBySuffix(id, me) || ctx.admin;
      return mineBySuffix(id, me) && (nd.uid === undefined || nd.uid === me);
    case 'workimgs':
      if (kind === 'delete') return String(od.uid ?? existing?.owner) === me || ctx.admin;
      return (nd.uid === undefined || nd.uid === me) && (!existing || String(od.uid ?? existing.owner) === me);
    case 'alerts': case 'msgs':
      if (kind === 'delete') return od.to === me || od.from === me || ctx.admin;
      if (!existing) return nd.from === me;
      return od.to === me || od.from === me;
    case 'family':
      if (kind === 'delete') return od.parent === me || od.child === me || ctx.admin;
      if (!existing) return (nd.parent === me || nd.child === me) && (nd.status === 'pending' || ctx.admin);
      return od.parent === me || od.child === me;
    case FRIENDS:
      if (kind === 'delete') return [od.a, od.b, od.from, od.to].includes(me) || ctx.admin;
      if (!existing) return [nd.a, nd.b, nd.from, nd.to].includes(me);
      return [od.a, od.b, od.from, od.to].includes(me);
    case 'info': case 'covers': case 'guides':           // 모두가 함께 쓰는 정보 캐시
      if (kind === 'delete') return ctx.admin || existing?.owner === me;
      return true;
    default:
      return ownerOk || ctx.admin;
  }
}

/** 쓰기 전에 잠긴 필드를 걸러 낸다 */
export function sanitize(ctx: Ctx, path: string, data: Record<string, unknown>): Record<string, unknown> {
  if (top(path) === 'members') {
    const d = { ...data };
    for (const k of MEMBER_LOCKED) delete d[k];
    if (!ctx.admin && d.mustChange === true) delete d.mustChange;
    return d;
  }
  return data;
}

export const isAdminId = (id: string | null) => id === ADMIN_ID;
