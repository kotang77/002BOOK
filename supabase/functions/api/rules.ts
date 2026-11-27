// 문서 경로별 읽기·쓰기 권한 (서버에서 강제)
// 이전 게시본은 "로그인한 가족이면 누구나 모든 문서를 읽고 쓸 수 있는" 구조였다.
// 일반 공개 서비스로 바꾸면서, 각 컬렉션을 아래 원칙으로 잠근다.
import { ADMIN_ID, sb } from './lib.ts';

export type Ctx = { uid: string | null; admin: boolean };
export type Row = { path: string; parent: string; id: string; data: Record<string, unknown>; owner: string | null; version: number; updated_at: string };

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
/** 친구 맺기 학년 규칙(2026-11-27): 한쪽이라도 중학생(중1~중3)이면 두 사람 모두 같은 학년이어야 한다.
 *  부모·선생님이 자녀·학생과 친구로 잘못 이어지는 일을 막는다(가족 연결은 family로). */
export async function friendGradeOk(a: string, b: string): Promise<boolean> {
  const { data } = await sb.from('docs').select('id,data').eq('parent', 'members').in('id', [a, b]);
  const g = (id: string) => String(((data ?? []).find((r) => r.id === id)?.data as Record<string, unknown> | undefined)?.grade ?? '');
  const mid = (x: string) => /^중[1-3]$/.test(x);
  const ga = g(a), gb = g(b);
  return !(mid(ga) || mid(gb)) || ga === gb;
}
/** 가족(부모·자녀)으로 연결된 회원만 */
export async function familyOf(uid: string): Promise<Set<string>> {
  const set = new Set<string>();
  const { data: fam } = await sb.from('docs').select('data').eq('parent', 'family')
    .or(`data->>parent.eq.${uid},data->>child.eq.${uid}`);
  for (const r of fam ?? []) {
    const d = r.data as Record<string, string>;
    if (d.status === 'accepted') set.add(d.parent === uid ? d.child : d.parent);
  }
  return set;
}

/* ---------- 읽기 ---------- */
export async function canRead(ctx: Ctx, path: string, row: Row | null): Promise<boolean> {
  const t = top(path), id = path.split('/')[1] ?? '';
  if (t === 'config') return true;                        // 계획표·공지 등: 로그인 전에도 읽음
  if (t === 'sys') return false;                          // 서버 전용(푸시 키 등): 누구도 읽지 못함
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
    case 'evals': case 'orals': case 'oralst':           // 논술·구술 평가(구술 진행 상태 포함): 본인 + 친구·가족
      return mineByPrefix(id, me) || (await related(me)).has(ownerOf(row));
    case 'qimgs':                                        // 내 서가 인상적인 문구 사진: 본인 + 친구·가족(진도와 같은 범위)
      return mineByPrefix(id, me) || (await related(me)).has(ownerOf(row));
    case 'orauds':                                       // 구술 녹음(목소리): 본인과 가족(부모·선생님)만. 친구는 못 들음 (관리자는 위에서 허용)
      return mineByPrefix(id, me) || (await familyOf(me)).has(ownerOf(row));
    case 'pushsubs':
      return id === me;
    case 'works': case 'workimgs': {
      const o = ownerOf(row);
      return o === me || mineByPrefix(id, me) || (await related(me)).has(o);
    }
    case 'diaries': case 'dykeys':
      return id === me || mineByPrefix(id, me);
    case 'msgs': case 'alerts':
      // 라운지 엽서: 받는 사람(나에게 보낸 엽서 포함)은 배달 시각(deliverAt)이 지나야 읽는다. 보낸 사람은 남에게 보낸 엽서만 본다
      if (t === 'msgs' && d.kind === 'post') return d.to === me ? Date.now() >= Number(d.deliverAt ?? 0) : d.from === me;
      return d.from === me || d.to === me;
    case 'family':
      return d.parent === me || d.child === me;
    case FRIENDS:
      return d.a === me || d.b === me || d.from === me || d.to === me;
    case 'resets':
      return false;
    case 'archive':                                      // 재시험 때 보관한 예전 평가: 본인만 (관리자는 위에서 허용)
      return mineByPrefix(id, me);
    default:
      return true;
  }
}

/** 읽기 결과를 다른 회원에게 보여 줄 모양으로 다듬는다
 *  다른 회원에게는 닉네임(과 그림 캐릭터)만 기본 공개.
 *  회원이 '내 정보 → 공개 설정'에서 켠 항목(pub.bio / pub.grade / pub.region / pub.photo)만 추가로 보인다. */
export function redact(ctx: Ctx, row: Row): Row {
  if (top(row.path) !== 'members') return row;
  const src = { ...row.data } as Record<string, unknown>;
  delete src.pw; delete src.salt;
  if (ctx.admin || row.id === ctx.uid) return { ...row, data: src };
  const pub = (src.pub ?? {}) as Record<string, boolean>;
  const photo = src.avatar === 'custom';
  const out: Record<string, unknown> = { id: row.id, nick: src.nick ?? row.id, pub: { bio: !!pub.bio, grade: !!pub.grade, region: !!pub.region, photo: !!pub.photo } };
  if (!photo) out.avatar = src.avatar ?? '';                 // 앱이 주는 그림 캐릭터는 개인정보가 아님
  if (photo && pub.photo) { out.avatar = 'custom'; out.avatarImg = src.avatarImg; }
  if (pub.bio) out.bio = src.bio;
  if (pub.grade) out.grade = src.grade;
  if (pub.region) out.region = src.region;
  return { ...row, data: out };
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
    case 'sys':
      return false;
    case 'pushsubs':
      return id === me;
    case 'config': case 'resets':
      return ctx.admin;
    case 'members':
      if (!existing && kind !== 'delete') return false;   // 가입은 서버(auth.signup)만
      if (kind === 'delete') return ctx.admin;
      return id === me || ctx.admin;
    case 'progress': case 'custom': case 'subs':
      if (t === 'subs' && kind !== 'delete' && !ctx.admin && ['active', 'ended'].includes(String(nd.status)) && od.status !== nd.status && !(od.status === 'cancel_requested' && nd.status === 'active')) return false;
      return id === me || ctx.admin;
    case 'oralst':                                       // 구술 진행 상태: 서버(oral.*)만 쓴다
      return false;
    case 'archive':                                      // 재시험 보관본: 서버(admin.resetTest)만 쓰고 관리자만 지움
      return ctx.admin && kind === 'delete';
    case 'orals':                                        // 1차·2차 평가 결과는 서버가 검증해 저장. 회원은 답변 문서(_a)만
      return (mineByPrefix(id, me) && id.endsWith('_a')) || (ctx.admin && kind === 'delete');
    case 'evals': case 'orauds': case 'qimgs':
      return mineByPrefix(id, me) || (ctx.admin && kind === 'delete');
    case 'diaries': case 'works':                      // 2026-11-24 일기·책만들기 종료: 새로 쓰지 못하고 지우기만
      return kind === 'delete' && (mineByPrefix(id, me) || ctx.admin);
    case 'dykeys':
      return kind === 'delete' && (id === me || ctx.admin);
    case 'essays': case 'reviews':
      if (kind === 'delete') return mineBySuffix(id, me) || ctx.admin;
      return mineBySuffix(id, me) && (nd.uid === undefined || nd.uid === me);
    case 'workimgs':                                     // 책만들기 종료: 지우기만
      return kind === 'delete' && (String(od.uid ?? existing?.owner) === me || ctx.admin);
    case 'alerts': case 'msgs':
      if (t === 'msgs' && (od.kind === 'post' || nd.kind === 'post')) {   // 라운지 엽서
        // 발신 취소: 남에게 보낸 엽서를, 받는 사람이 열기 전에만(배달 중 포함). 나에게 보낸 엽서·받은 엽서는 지우지 않고 남긴다
        if (kind === 'delete') return (od.from === me && od.to !== me && !od.openedAt) || ctx.admin;
        if (!existing) return nd.from === me && typeof nd.to === 'string' && !!nd.to && !nd.openedAt && Number(nd.deliverAt) > Date.now();
        // 받는 사람만, 배달된 뒤에 '열어 봄'을 표시할 수 있고, 내용·보낸 사람·받는 사람·디자인·보낸 시각·배달 시각은 못 바꾼다
        return od.to === me && Date.now() >= Number(od.deliverAt ?? 0) && ['from', 'to', 'text', 'design', 'stamp', 'at', 'deliverAt', 'fromNick', 'kind'].every(k => nd[k] === od[k]);
      }
      if (kind === 'delete') return od.to === me || od.from === me || ctx.admin;
      if (!existing) return nd.from === me;
      return od.to === me || od.from === me;
    case 'family':
      if (kind === 'delete') return od.parent === me || od.child === me || ctx.admin;
      if (!existing) return (nd.parent === me || nd.child === me) && (nd.status === 'pending' || ctx.admin);
      return od.parent === me || od.child === me;
    case FRIENDS:
      if (kind === 'delete') return [od.a, od.b, od.from, od.to].includes(me) || ctx.admin;
      if (!existing) return [nd.a, nd.b, nd.from, nd.to].includes(me) && (ctx.admin || await friendGradeOk(String(nd.a), String(nd.b)));
      if (!([od.a, od.b, od.from, od.to].includes(me))) return false;
      return ctx.admin || nd.status !== 'accepted' || od.status === 'accepted' || await friendGradeOk(String(od.a), String(od.b));
    case 'info': case 'covers': case 'guides':           // 모두가 함께 쓰는 정보 캐시
      if (kind === 'delete') return ctx.admin || existing?.owner === me;
      return true;
    default:
      return ownerOk || ctx.admin;
  }
}

/** 쓰기 전에 잠긴 필드를 걸러 낸다 */
/** 라운지 엽서 배달 시간: 보내고 24시간 뒤(시험 서버는 POST_DELAY_SEC로 줄임) */
const POST_DELAY = Number(Deno.env.get('POST_DELAY_SEC') ?? 86400) * 1000;
const POST_MAX = 5 * 366 * 86400 * 1000;
export function sanitize(ctx: Ctx, path: string, data: Record<string, unknown>): Record<string, unknown> {
  if (top(path) === 'msgs' && data.kind === 'post') {     // 보낸 시각·배달 시각은 서버 시계로 정한다
    const d = { ...data }, now = Date.now();
    d.at = now; d.openedAt = 0;
    if (d.to === ctx.uid) d.deliverAt = Math.min(now + POST_MAX, Math.max(now + 1000, Number(d.deliverAt) || 0)); // 나에게: 고른 날
    else d.deliverAt = now + POST_DELAY;                                                                            // 남에게: 24시간 뒤
    return d;
  }
  if (top(path) === 'members') {
    const d = { ...data };
    for (const k of MEMBER_LOCKED) delete d[k];
    if (!ctx.admin && d.mustChange === true) delete d.mustChange;
    return d;
  }
  return data;
}

export const isAdminId = (id: string | null) => id === ADMIN_ID;
