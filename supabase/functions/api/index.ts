// 002BOOK 서버 API (Supabase Edge Function)
// 배포: supabase functions deploy api --no-verify-jwt
import {
  ADMIN_ID, cors, env, escHtml, fail, HttpErr, mailShell, pbkdf2, randHex, randToken, safeEq, sb, sendMail, sha256hex, SITE, tempPassword,
} from './lib.ts';
import { canRead, canWrite, Ctx, redact, Row, sanitize } from './rules.ts';
import { sampleAI } from './ai.ts';
import { payConfirm, payPlans, payReady } from './pay.ts';
import { addSub, pushTo, removeSub, vapid } from './push.ts';
import { oralOp } from './oral.ts';

const SESSION_DAYS = 60;
const PBKDF2_ITER = 120000;
const MAX_DOC = 2_500_000;
const ID_RE = /^[a-z0-9_-]{3,20}$/;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const GUARDIAN_AGE = 14;

/* ================================================================
 * 세션
 * ================================================================ */
async function getCtx(req: Request): Promise<Ctx> {
  const t = req.headers.get('x-session');
  if (!t) return { uid: null, admin: false };
  const { data } = await sb.from('sessions').select('uid, expires_at').eq('token_hash', await sha256hex(t)).maybeSingle();
  if (!data || new Date(data.expires_at) < new Date()) return { uid: null, admin: false };
  return { uid: data.uid, admin: data.uid === ADMIN_ID };
}
const need = (ctx: Ctx) => { if (!ctx.uid) fail('unauthenticated', '다시 로그인해 주세요.', 401); return ctx.uid!; };
const needAdmin = (ctx: Ctx) => { need(ctx); if (!ctx.admin) fail('forbidden', '관리자만 할 수 있어요.', 403); };

async function newSession(uid: string, ua: string | null) {
  const token = randToken();
  await sb.from('sessions').insert({
    token_hash: await sha256hex(token), uid, user_agent: (ua ?? '').slice(0, 200),
    expires_at: new Date(Date.now() + SESSION_DAYS * 864e5).toISOString(),
  });
  return { token, uid, admin: uid === ADMIN_ID };
}

/* ================================================================
 * 문서 도우미
 * ================================================================ */
const norm = (p: string) => String(p ?? '').replace(/^\/+|\/+$/g, '');
function splitPath(p: string) {
  const path = norm(p); const segs = path.split('/');
  if (segs.length < 2 || segs.length % 2 || segs.some((s) => !s || s.length > 300)) fail('bad_path', '잘못된 경로예요.');
  return { path, parent: segs.slice(0, -1).join('/'), id: segs[segs.length - 1] };
}
async function readRow(path: string): Promise<Row | null> {
  const { data } = await sb.from('docs').select('*').eq('path', path).maybeSingle();
  return (data as Row) ?? null;
}
async function writeRow(path: string, data: Record<string, unknown>, owner: string | null, prev: Row | null) {
  const s = JSON.stringify(data);
  if (s.length > MAX_DOC) fail('too_large', '저장할 내용이 너무 커요. 사진 크기를 줄여 주세요.', 413);
  const { parent, id } = splitPath(path);
  const row = { path, parent, id, data, owner: prev?.owner ?? owner, version: (prev?.version ?? 0) + 1, updated_at: new Date().toISOString() };
  const { error } = await sb.from('docs').upsert(row);
  if (error) fail('db_error', '저장하지 못했어요.', 500, error.message);
  return { version: row.version, updated_at: row.updated_at };
}
const isObj = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
function deepMerge(a: Record<string, unknown>, b: Record<string, unknown>) {
  const o: Record<string, unknown> = { ...a };
  for (const k of Object.keys(b)) o[k] = isObj(o[k]) && isObj(b[k]) ? deepMerge(o[k] as Record<string, unknown>, b[k] as Record<string, unknown>) : b[k];
  return o;
}
function applyUpdate(a: Record<string, unknown>, upd: Record<string, unknown>) {
  const o = structuredClone(a);
  for (const [k, v] of Object.entries(upd)) {
    const ks = k.split('.'); let cur = o as Record<string, unknown>;
    for (let i = 0; i < ks.length - 1; i++) { if (!isObj(cur[ks[i]])) cur[ks[i]] = {}; cur = cur[ks[i]] as Record<string, unknown>; }
    if (v === null && ks.length > 1) delete cur[ks[ks.length - 1]]; else cur[ks[ks.length - 1]] = v;
  }
  return o;
}
const getField = (d: Record<string, unknown>, f: string) => f.split('.').reduce<unknown>((o, k) => (isObj(o) ? (o as Record<string, unknown>)[k] : undefined), d);
function test(v: unknown, op: string, x: unknown) {
  switch (op) {
    case '==': return v === x; case '!=': return v !== x;
    case '<': return (v as number) < (x as number); case '<=': return (v as number) <= (x as number);
    case '>': return (v as number) > (x as number); case '>=': return (v as number) >= (x as number);
    case 'in': return Array.isArray(x) && x.includes(v); case 'not-in': return Array.isArray(x) && !x.includes(v);
    case 'array-contains': return Array.isArray(v) && v.includes(x);
    case 'array-contains-any': return Array.isArray(v) && Array.isArray(x) && x.some((y) => v.includes(y));
    default: return false;
  }
}
const outRow = (r: Row) => ({ id: r.id, data: r.data, version: r.version, updated_at: r.updated_at });

/* ================================================================
 * 플랜 (유료·정지) — config/plans 문서
 * ================================================================ */
async function plans() {
  const r = await readRow('config/plans');
  const d = (r?.data ?? {}) as { paid?: Record<string, { at: number; until?: number }>; blocked?: Record<string, unknown> };
  return { row: r, paid: d.paid ?? {}, blocked: d.blocked ?? {} };
}
async function isPaid(uid: string) {
  if (uid === ADMIN_ID) return true;
  const p = await plans(); const e = p.paid[uid];
  if (!e) return false;
  if (e.until && e.until < Date.now()) {       // 이용 기간이 끝나면 자동으로 무료회원
    const paid = { ...p.paid }; delete paid[uid];
    await writeRow('config/plans', { ...(p.row?.data ?? {}), paid }, ADMIN_ID, p.row);
    const s = await readRow('subs/' + uid);
    if (s) await writeRow('subs/' + uid, { ...s.data, status: 'ended', endedAt: Date.now() }, uid, s);
    return false;
  }
  return true;
}

/* ================================================================
 * 계정
 * ================================================================ */
async function hashNew(pw: string) { const salt = randHex(16); return { pw_salt: salt, pw_hash: await pbkdf2(pw, salt, PBKDF2_ITER), pw_algo: 'pbkdf2' }; }
async function checkPw(acc: { pw_hash: string; pw_salt: string; pw_algo: string }, pw: string) {
  return safeEq(await pbkdf2(pw, acc.pw_salt, PBKDF2_ITER), acc.pw_hash);
}
async function account(id: string) {
  const { data } = await sb.from('accounts').select('*').eq('id', id).maybeSingle();
  return data;
}
function ageFrom(birth: string) {
  const m = /^(\d{4})-(\d{2})$/.exec(String(birth ?? ''));
  if (!m) return null;
  const y = +m[1], mo = +m[2], now = new Date(Date.now() + 9 * 3600e3);
  let a = now.getUTCFullYear() - y; if (now.getUTCMonth() + 1 < mo) a--;
  return a >= 0 && a < 120 ? a : null;
}
async function guardianMail(id: string, nick: string, gName: string, gEmail: string) {
  const token = randToken();
  const { data: acc } = await sb.from('accounts').select('guardian_consent').eq('id', id).single();
  await sb.from('accounts').update({ guardian_consent: { ...(acc?.guardian_consent ?? {}), status: 'pending', name: gName, email: gEmail, token_hash: await sha256hex(token), requested_at: Date.now() } }).eq('id', id);
  const link = `${SITE}/guardian.html?t=${encodeURIComponent(token)}`;
  await sendMail(gEmail, '[002BOOK] 자녀 회원가입 동의 요청', mailShell('보호자 동의 요청',
    `<p>${escHtml(gName)} 님, 안녕하세요.</p><p>자녀(닉네임 <b>${escHtml(nick)}</b>, 아이디 <b>${escHtml(id)}</b>)가 002BOOK 가입을 신청했어요.
     만 14세 미만 아동의 개인정보 수집에는 「개인정보 보호법」 제22조의2에 따라 법정대리인의 동의가 필요해요.</p>
     <p>수집 항목: 아이디, 닉네임, 이메일, 거주지역(시·도), 학년, 성별, 출생 연월, 독서·논술·일기 기록<br>이용 목적: 독서·영화 학습 서비스와 AI 첨삭 제공<br>보관 기간: 회원 탈퇴 시까지 (탈퇴 즉시 삭제)</p>
     <p><a href="${SITE}/privacy.html" style="color:#8A5024">개인정보처리방침 전문 보기</a></p>
     <p style="margin:22px 0"><a href="${link}" style="background:#3E2F26;color:#FBF6EC;padding:10px 18px;border-radius:8px;text-decoration:none">동의 내용 확인하기</a></p>
     <p style="font-size:13px;color:#6F6155">링크를 열면 동의 내용을 확인하고 [동의] 또는 [동의하지 않음]을 고를 수 있어요. 링크는 7일 동안 쓸 수 있어요.</p>
     <p style="font-size:13px;color:#6F6155">동의하지 않으시면 이 메일을 무시해 주세요. 7일 뒤 신청이 자동으로 지워져요.</p>`));
}

async function signup(req: Request, b: Record<string, unknown>) {
  const id = String(b.id ?? '').trim().toLowerCase();
  const pw = String(b.pw ?? '');
  const email = String(b.email ?? '').trim().slice(0, 120);
  if (!ID_RE.test(id)) fail('bad_id', '아이디는 영문 소문자와 숫자로 3~20자여야 해요.');
  if (pw.length < 8) fail('weak_password', '비밀번호는 8자 이상이어야 해요.');
  if (!EMAIL_RE.test(email)) fail('bad_email', '이메일 주소를 정확히 적어 주세요.');
  if (!b.agreeTerms || !b.agreePrivacy) fail('need_agree', '이용약관과 개인정보 수집·이용에 동의해 주세요.');
  const age = ageFrom(String(b.birth ?? ''));
  if (age === null) fail('bad_birth', '태어난 연도와 월을 골라 주세요.');
  const minor = age! < GUARDIAN_AGE;
  const gName = String(b.guardianName ?? '').trim().slice(0, 30), gEmail = String(b.guardianEmail ?? '').trim().slice(0, 120);
  if (minor && (!gName || !EMAIL_RE.test(gEmail))) fail('need_guardian', '만 14세 미만은 보호자 이름과 이메일이 필요해요.');
  if (minor && gEmail.toLowerCase() === email.toLowerCase()) fail('need_guardian', '보호자 이메일은 본인 이메일과 달라야 해요.');
  if (await account(id) || await readRow('members/' + id)) fail('id_taken', '이미 있는 아이디예요. 다른 아이디를 써 주세요.');
  const { data: dupe } = await sb.from('accounts').select('id').ilike('email', email).maybeSingle();
  if (dupe) fail('email_taken', '이미 가입한 이메일이에요. 아이디 찾기를 이용해 주세요.');

  const h = await hashNew(pw);
  const { error } = await sb.from('accounts').insert({ id, email, ...h, guardian_consent: minor ? { status: 'pending' } : null });
  if (error) fail('id_taken', '이미 있는 아이디예요. 다른 아이디를 써 주세요.');
  const str = (k: string, n: number) => String(b[k] ?? '').trim().slice(0, n);
  const member = {
    id, nick: str('nick', 12) || id, region: str('region', 10), grade: str('grade', 6) || '중1', gender: str('gender', 4),
    bio: str('bio', 40), buddy: str('buddy', 10), buddyAv: str('buddyAv', 20), buddyImg: String(b.buddyImg ?? '').slice(0, 60000),
    email, birth: String(b.birth), mode: 'base', prefs: {}, pub: {}, at: Date.now(), agreedAt: Date.now(), policyVersion: env('POLICY_VERSION', '2026-12-01'),
    marketing: !minor && !!b.agreeMarketing, aiNoticeAt: Date.now(),
  };
  await writeRow('members/' + id, member, id, null);
  if (minor) {
    await guardianMail(id, member.nick, gName, gEmail);
    return { pending: 'guardian', member: null, session: null };
  }
  return { member, session: await newSession(id, req.headers.get('user-agent')) };
}

async function login(req: Request, b: Record<string, unknown>) {
  const id = String(b.id ?? '').trim().toLowerCase(), pw = String(b.pw ?? '');
  const acc = await account(id);
  if (!acc) fail('no_user', '없는 아이디예요. 아이디를 다시 확인해 주세요.');
  if (!(await checkPw(acc, pw))) fail('bad_password', '비밀번호가 맞지 않아요.');
  if (acc.guardian_consent?.status === 'pending') fail('guardian_pending', '보호자 동의를 기다리고 있어요. 보호자 이메일의 승인 버튼을 눌러 주세요.');
  const p = await plans();
  if (acc.blocked || (id !== ADMIN_ID && p.blocked[id])) fail('blocked', '이용이 정지된 계정이에요. 관리자에게 문의해 주세요.');
  const m = await readRow('members/' + id);
  const member = { ...(m?.data ?? { id, nick: id }), mustChange: acc.must_change };
  delete (member as Record<string, unknown>).pw; delete (member as Record<string, unknown>).salt;
  await isPaid(id);
  return { member, session: await newSession(id, req.headers.get('user-agent')) };
}

async function resetPw(b: Record<string, unknown>) {
  const id = String(b.id ?? '').trim().toLowerCase(), email = String(b.email ?? '').trim().toLowerCase();
  const acc = await account(id);
  // 아이디가 없어도 같은 답을 줘서 회원 여부를 알 수 없게 한다
  if (acc && acc.email && acc.email.toLowerCase() === email) {
    const tmp = tempPassword();
    await sb.from('accounts').update({ ...(await hashNew(tmp)), must_change: true, updated_at: new Date().toISOString() }).eq('id', id);
    await sb.from('sessions').delete().eq('uid', id);
    await sendMail(acc.email, '[002BOOK] 임시 비밀번호 안내', mailShell('임시 비밀번호',
      `<p>${escHtml(id)} 님의 임시 비밀번호는 아래와 같아요.</p><p style="font-size:22px;letter-spacing:.08em;font-weight:700">${tmp}</p>
       <p>로그인한 뒤 위쪽의 아이디를 눌러 새 비밀번호로 바꿔 주세요.</p>
       <p style="font-size:13px;color:#6F6155">일기를 잠가 두었다면, 새 비밀번호로 바꾼 뒤 일기 화면에서 '복구 코드로 열기'를 써 주세요.</p>`));
  }
  return { ok: true };
}

async function deleteAll(id: string) {
  // 회원이 만든 모든 문서와 회원이 관련된 공유 문서를 지운다
  const del = (q: ReturnType<typeof sb.from>) => q;
  await sb.from('docs').delete().in('path', ['members/' + id, 'progress/' + id, 'custom/' + id, 'dykeys/' + id, 'subs/' + id, 'resets/' + id, 'pushsubs/' + id]);
  for (const col of ['evals', 'orals', 'oralst', 'orauds', 'qimgs', 'diaries', 'works', 'essays', 'reviews']) {
    const { data } = await sb.from('docs').select('path, id').eq('parent', col);
    const mine = (data ?? []).filter((r: { id: string }) => (col === 'essays' || col === 'reviews') ? r.id.endsWith('_' + id) : r.id.startsWith(id + '_'));
    for (let i = 0; i < mine.length; i += 100) await sb.from('docs').delete().in('path', mine.slice(i, i + 100).map((r: { path: string }) => r.path));
  }
  for (const col of ['reviews', 'essays', 'diaries', 'works', 'workimgs']) await sb.from('docs').delete().eq('parent', col).eq('data->>uid', id);
  for (const [col, f] of [['friends', 'from'], ['friends', 'to'], ['friends', 'a'], ['friends', 'b'], ['msgs', 'from'], ['msgs', 'to'], ['family', 'parent'], ['family', 'child'], ['alerts', 'from'], ['alerts', 'to']]) {
    await sb.from('docs').delete().eq('parent', col).eq(`data->>${f}`, id);
  }
  await sb.from('docs').delete().eq('owner', id).in('parent', ['workimgs']);
  const p = await plans();
  if (p.paid[id] || p.blocked[id]) {
    const paid = { ...p.paid }, blocked = { ...p.blocked }; delete paid[id]; delete blocked[id];
    await writeRow('config/plans', { ...(p.row?.data ?? {}), paid, blocked }, ADMIN_ID, p.row);
  }
  await sb.storage.from('uploads').list(id).then(async ({ data }) => { if (data?.length) await sb.storage.from('uploads').remove(data.map((f) => `${id}/${f.name}`)); });
  await sb.from('ai_usage').delete().eq('uid', id);
  await sb.from('accounts').delete().eq('id', id); // sessions는 cascade로 함께 삭제
  void del;
}

/* ================================================================
 * 구술 테스트 최종 리포트: 가족으로 연결된 부모·선생님에게 메일(PDF 첨부) + 휴대폰 푸시 + 앱 알림
 * ================================================================ */
async function familyAdults(uid: string): Promise<string[]> {
  const { data } = await sb.from('docs').select('data').eq('parent', 'family').eq('data->>child', uid);
  const ids = (data ?? []).map((r: { data: Record<string, string> }) => r.data).filter((d) => d.status === 'accepted' && d.parent && d.parent !== uid).map((d) => d.parent);
  return [...new Set(ids)];
}
async function oralReport(ctx: Ctx, b: Record<string, unknown>) {
  const uid = need(ctx);
  const key = String(b.key ?? '');
  if (!/^[bc]\d{1,3}$/.test(key)) fail('bad_request', '잘못된 요청이에요.');
  const ev = await readRow(`orals/${uid}_${key}_r2`);
  if (!ev) fail('not_found', '2차 구술 평가를 먼저 마쳐 주세요.', 404);
  const ids = await familyAdults(uid);
  const mems = await Promise.all(ids.map((id) => readRow('members/' + id)));
  const to = ids.map((id, n) => ({ id, nick: String(mems[n]?.data?.nick ?? id) }));
  if (b.check) return { to: to.map((x) => x.nick) };
  if (!to.length) return { to: [], mailed: 0, pushed: 0 };
  const d = ev!.data as Record<string, unknown>;
  const sentN = Number(d.sentN ?? 0);
  if (sentN >= 5) fail('rate_limited', '이 리포트는 이미 여러 번 보냈어요.', 429);
  const pdf = String(b.pdf ?? '');
  if (!pdf.startsWith('JVBER') || pdf.length > 9_000_000) fail('bad_request', '리포트 파일이 올바르지 않아요.');
  const me = await readRow('members/' + uid);
  const nick = String(me?.data?.nick ?? uid);
  const title = String(d.title ?? ''), gm = `${d.g ?? ''} ${d.m ?? ''}`.trim();
  const t1 = Number(d.firstTotal ?? 0), t2 = Number(d.total ?? 0), gr = Number(d.growth ?? 0);
  const fname = String(b.filename ?? 'oral-report.pdf').replace(/[\\/:*?"<>|]/g, '').slice(0, 80) || 'oral-report.pdf';
  const accs = await Promise.all(ids.map((id) => account(id)));
  const emails = accs.map((a) => a?.email).filter((e): e is string => !!e && EMAIL_RE.test(e));
  let mailed = 0, mailErr = '';
  if (emails.length) try {
    await sendMail(emails, `[002BOOK] ${nick}의 구술 테스트 리포트 (${gm} 「${title}」)`, mailShell('구술 테스트 최종 리포트',
      `<p><b>${escHtml(nick)}</b> 학생이 ${escHtml(gm)} 「${escHtml(title)}」 구술 테스트를 마쳤어요.</p>
       <table style="border-collapse:collapse;margin:10px 0;font-size:15px"><tr><td style="padding:6px 12px;border:1px solid #DCCFBB">1차 총점</td><td style="padding:6px 12px;border:1px solid #DCCFBB"><b>${t1}</b>점</td></tr>
       <tr><td style="padding:6px 12px;border:1px solid #DCCFBB">2차 총점</td><td style="padding:6px 12px;border:1px solid #DCCFBB"><b>${t2}</b>점 (${t2 - t1 >= 0 ? '+' : ''}${t2 - t1})</td></tr>
       <tr><td style="padding:6px 12px;border:1px solid #DCCFBB">대답 성장 점수</td><td style="padding:6px 12px;border:1px solid #DCCFBB"><b>${gr}</b>점</td></tr></table>
       ${d.teacher ? `<p style="background:#EEF5EC;padding:10px 12px;border-radius:8px">${escHtml(d.teacher)}</p>` : ''}
       <p>1차·2차 대답 첨삭과 성장 분석은 <b>첨부한 PDF 리포트</b>에 있어요. 002BOOK에 로그인하면 자녀 화면에서 녹음도 들어 볼 수 있어요.</p>
       <p style="font-size:12px;color:#6F6155">이 리포트는 생성형 AI(Anthropic Claude)가 작성한 평가예요. 가족으로 연결된 보호자에게만 보내요.</p>`),
      [{ filename: fname, content: pdf }]);
    mailed = emails.length;
  } catch (e) { mailErr = e instanceof HttpErr ? e.code : 'mail_failed'; console.log('oral report mail failed', String(e)); }
  const at = Date.now(); let pushed = 0;
  for (const x of to) {
    const text = `${nick} 학생의 ${gm} 「${title}」 구술 테스트: 1차 ${t1}점 → 2차 ${t2}점, 성장 점수 ${gr}점`;
    await writeRow(`alerts/${x.id}_${uid}_${at}_oral`, { to: x.id, from: uid, fromNick: nick, title: '구술 테스트 리포트', text, at }, uid, null);
    pushed += await pushTo(x.id, { title: '002BOOK 구술 테스트 리포트', body: text, url: '/', tag: 'oral-' + uid + '-' + key });
  }
  await writeRow(ev!.path, { ...d, sentN: sentN + 1, sentAt: at, sentTo: to.map((x) => x.nick) }, uid, ev);
  return { to: to.map((x) => x.nick), mailed, pushed, mailErr };
}

/* ================================================================
 * 라우터
 * ================================================================ */
async function handle(req: Request, b: Record<string, unknown>) {
  const ctx = await getCtx(req);
  switch (String(b.op)) {
    /* ---- 계정 ---- */
    case 'auth.signup': return signup(req, b);
    case 'auth.login': return login(req, b);
    case 'auth.logout': { const t = req.headers.get('x-session'); if (t) await sb.from('sessions').delete().eq('token_hash', await sha256hex(t)); return { ok: true }; }
    case 'auth.me': { const uid = need(ctx); const acc = await account(uid); return { uid, admin: ctx.admin, paid: await isPaid(uid), mustChange: !!acc?.must_change }; }
    case 'auth.verify': { const uid = need(ctx); const acc = await account(uid); if (!acc || !(await checkPw(acc, String(b.pw ?? '')))) fail('bad_password', '비밀번호가 맞지 않아요.'); return { ok: true }; }
    case 'auth.reset': return resetPw(b);
    case 'auth.guardianInfo': return guardianInfo(String(b.token ?? ''));
    case 'auth.guardianConsent': return guardianConsent(req, b);
    case 'auth.findId': {
      const email = String(b.email ?? '').trim();
      const { data } = await sb.from('accounts').select('id').ilike('email', email).maybeSingle();
      if (data) await sendMail(email, '[002BOOK] 아이디 안내', mailShell('아이디 안내', `<p>가입하신 아이디는 <b>${escHtml(data.id)}</b> 예요.</p>`));
      return { ok: true };
    }
    case 'auth.changePassword': {
      const uid = need(ctx); const acc = await account(uid);
      if (!acc || !(await checkPw(acc, String(b.oldPw ?? '')))) fail('bad_password', '현재 비밀번호가 맞지 않아요.');
      if (String(b.newPw ?? '').length < 8) fail('weak_password', '새 비밀번호는 8자 이상이어야 해요.');
      await sb.from('accounts').update({ ...(await hashNew(String(b.newPw))), must_change: false, updated_at: new Date().toISOString() }).eq('id', uid);
      const m = await readRow('members/' + uid); if (m) await writeRow('members/' + uid, { ...m.data, mustChange: false }, uid, m);
      return { ok: true };
    }
    case 'auth.withdraw': {
      const uid = need(ctx); if (uid === ADMIN_ID) fail('forbidden', '관리자 계정은 탈퇴할 수 없어요.');
      const acc = await account(uid);
      if (!acc || !(await checkPw(acc, String(b.pw ?? '')))) fail('bad_password', '비밀번호가 맞지 않아요.');
      await deleteAll(uid); return { ok: true };
    }
    case 'auth.guardianResend': {
      const id = String(b.id ?? '').trim().toLowerCase(); const acc = await account(id);
      if (acc && acc.guardian_consent?.status === 'pending' && acc.guardian_consent.email && (await checkPw(acc, String(b.pw ?? '')))) {
        const m = await readRow('members/' + id);
        await guardianMail(id, String(m?.data?.nick ?? id), acc.guardian_consent.name, acc.guardian_consent.email);
      }
      return { ok: true };
    }

    /* ---- 관리자 ---- */
    case 'admin.setPassword': {
      needAdmin(ctx); const id = String(b.id ?? ''); const pw = String(b.pw ?? '');
      if (pw.length < 8) fail('weak_password', '비밀번호는 8자 이상이어야 해요.');
      if (!(await account(id))) fail('no_user', '회원을 찾지 못했어요.');
      await sb.from('accounts').update({ ...(await hashNew(pw)), must_change: !!b.temp, updated_at: new Date().toISOString() }).eq('id', id);
      await sb.from('sessions').delete().eq('uid', id);
      return { ok: true };
    }
    case 'admin.deleteMember': { needAdmin(ctx); const id = String(b.id ?? ''); if (id === ADMIN_ID) fail('forbidden', '관리자는 지울 수 없어요.'); await deleteAll(id); return { ok: true }; }
    case 'admin.mail': {
      needAdmin(ctx);
      const to = (Array.isArray(b.to) ? b.to : [b.to]).map(String).filter((x) => EMAIL_RE.test(x)).slice(0, 50);
      if (!to.length) fail('bad_request', '받는 사람이 없어요.');
      await sendMail(to, '[002BOOK] ' + String(b.subject ?? '').slice(0, 100), mailShell(escHtml(b.subject), `<div style="white-space:pre-wrap">${escHtml(b.text)}</div>`));
      return { ok: true, sent: to.length };
    }
    case 'admin.usage': {
      needAdmin(ctx);
      const { data } = await sb.from('ai_usage').select('*').order('day', { ascending: false }).limit(200);
      return data ?? [];
    }

    /* ---- 문서 ---- */
    case 'db.get': {
      const { path } = splitPath(String(b.path));
      const row = await readRow(path);
      if (!(await canRead(ctx, path, row))) { if (!ctx.uid) fail('unauthenticated', '다시 로그인해 주세요.', 401); return null; }
      return row ? outRow(redact(ctx, row)) : null;
    }
    case 'db.query': {
      const col = norm(String(b.collection));
      if (!col || col.split('/').length % 2 === 0) fail('bad_path', '잘못된 경로예요.');
      if (!ctx.uid && col !== 'config') fail('unauthenticated', '다시 로그인해 주세요.', 401);
      const q = (b.query ?? {}) as { where?: [string, string, unknown][]; orderBy?: [string, string][]; limit?: number };
      let sel = sb.from('docs').select('*').eq('parent', col).limit(5000);
      for (const [f, op, v] of q.where ?? []) if (op === '==' && typeof v === 'string' && !f.includes('.')) sel = sel.eq(`data->>${f}`, v);
      const { data, error } = await sel;
      if (error) fail('db_error', '불러오지 못했어요.', 500, error.message);
      let rows = (data ?? []) as Row[];
      rows = rows.filter((r) => (q.where ?? []).every(([f, op, v]) => test(getField(r.data, f), op, v)));
      const ok: Row[] = [];
      for (const r of rows) if (await canRead(ctx, r.path, r)) ok.push(redact(ctx, r));
      for (const [f, dir] of [...(q.orderBy ?? [])].reverse()) {
        ok.sort((x, y) => { const a = getField(x.data, f) as number, c = getField(y.data, f) as number; return (a > c ? 1 : a < c ? -1 : 0) * (dir === 'desc' ? -1 : 1); });
      }
      return (q.limit ? ok.slice(0, q.limit) : ok).map(outRow);
    }
    case 'db.set': case 'db.update': {
      const uid = need(ctx); const { path } = splitPath(String(b.path));
      if (!isObj(b.data)) fail('bad_request', '저장할 내용이 없어요.');
      const prev = await readRow(path);
      if (b.op === 'db.update' && !prev) fail('not_found', '문서를 찾지 못했어요.', 404);
      const incoming = sanitize(ctx, path, b.data as Record<string, unknown>);
      const next = b.op === 'db.update' ? applyUpdate(prev!.data, incoming) : b.merge && prev ? deepMerge(prev.data, incoming) : incoming;
      if (path.startsWith('members/') && prev) { delete next.pw; delete next.salt; for (const k of ['id', 'birth']) if (prev.data[k] !== undefined) next[k] = prev.data[k]; }
      if (!(await canWrite(ctx, b.op === 'db.update' ? 'update' : 'set', path, prev, next))) fail('permission_denied', '이 기록을 바꿀 권한이 없어요.', 403);
      return writeRow(path, next, uid, prev);
    }
    case 'db.delete': {
      need(ctx); const { path } = splitPath(String(b.path));
      const prev = await readRow(path);
      if (!prev) return { ok: true };
      if (!(await canWrite(ctx, 'delete', path, prev, null))) fail('permission_denied', '이 기록을 지울 권한이 없어요.', 403);
      await sb.from('docs').delete().eq('path', path);
      return { ok: true };
    }

    /* ---- 휴대폰 알림·구술 리포트 ---- */
    case 'push.key': { need(ctx); return { pub: (await vapid()).pub }; }
    case 'push.sub': {
      const uid = need(ctx);
      try { await addSub(uid, b.sub as never, String(b.ua ?? '')); } catch { fail('bad_request', '알림 정보를 저장하지 못했어요.'); }
      return { ok: true };
    }
    case 'push.unsub': { const uid = need(ctx); await removeSub(uid, b.endpoint ? String(b.endpoint) : undefined); return { ok: true }; }
    case 'push.test': { const uid = need(ctx); return { sent: await pushTo(uid, { title: '002BOOK 알림 확인', body: '이제 이 기기에서 002BOOK 알림을 받을 수 있어요.', url: '/' }) }; }
    case 'oral.state': case 'oral.save1': case 'oral.shadow': case 'oral.thinkDone': case 'oral.ans2': case 'oral.prep2': case 'oral.finalize':
      return oralOp(String(b.op), need(ctx), b, { read: readRow, write: writeRow });
    case 'oral.report': return oralReport(ctx, b);

    /* ---- AI ---- */
    case 'ai.sample': {
      const uid = need(ctx);
      return sampleAI(uid, await isPaid(uid), b as never);
    }

    /* ---- 결제 ---- */
    case 'pay.plans': return payPlans();
    case 'pay.ready': { const uid = need(ctx); return payReady(uid, String(b.plan ?? '')); }
    case 'pay.confirm': {
      const uid = need(ctx);
      return payConfirm(uid, b as never, async (until: number, orderId: string) => {
        const p = await plans();
        const paid = { ...p.paid, [uid]: { at: Date.now(), until, orderId } };
        await writeRow('config/plans', { ...(p.row?.data ?? {}), paid, blocked: p.blocked }, ADMIN_ID, p.row);
        const m = await readRow('members/' + uid); const s = await readRow('subs/' + uid);
        await writeRow('subs/' + uid, { ...(s?.data ?? {}), id: uid, nick: m?.data?.nick ?? uid, status: 'active', since: Date.now(), until, orderId, at: (s?.data?.at as number) ?? Date.now() }, uid, s);
      });
    }
    default: fail('bad_op', '알 수 없는 요청이에요.');
  }
}

/* ---------- 보호자 동의 (개인정보 보호법 제22조의2, 시행령 제17조의2) ----------
 * 메일 링크는 002book.com/guardian.html(동의 내용을 보여 주는 페이지)만 연다. 메일 보안 검사기가 링크를 미리 열어도 동의되지 않도록
 * 실제 동의는 페이지의 [동의] 버튼(POST op=auth.guardianConsent)으로만 처리하고, 처리 결과를 보호자 메일로 다시 알린다. */
async function pendingByToken(token: string) {
  const { data } = await sb.from('accounts').select('id, email, created_at, guardian_consent').eq('guardian_consent->>token_hash', await sha256hex(token)).maybeSingle();
  if (!data || data.guardian_consent?.status !== 'pending') return null;
  if (Date.now() - Number(data.guardian_consent.requested_at ?? 0) > 7 * 864e5) return null;
  return data;
}

async function guardianInfo(token: string) {
  const acc = await pendingByToken(token);
  if (!acc) fail('expired', '링크가 만료되었거나 이미 처리됐어요. 자녀가 다시 가입 신청을 하면 새 메일이 가요.');
  const m = await readRow('members/' + acc!.id);
  return { id: acc!.id, nick: String(m?.data?.nick ?? acc!.id), grade: String(m?.data?.grade ?? '') };
}

async function guardianConsent(req: Request, b: Record<string, unknown>) {
  const acc = await pendingByToken(String(b.token ?? ''));
  if (!acc) fail('expired', '링크가 만료되었거나 이미 처리됐어요.');
  const gc = acc!.guardian_consent;
  if (!b.agree) {
    await sb.from('docs').delete().eq('path', 'members/' + acc!.id);
    await sb.from('accounts').delete().eq('id', acc!.id);
    await sendMail(gc.email, '[002BOOK] 가입 신청이 취소됐어요', mailShell('가입 신청 취소', `<p>동의하지 않으셔서 자녀(${escHtml(acc!.id)})의 가입 신청과 입력한 정보를 모두 삭제했어요.</p>`)).catch(() => {});
    return { message: '동의하지 않으셔서 가입 신청과 입력한 정보를 모두 삭제했어요.' };
  }
  const name = String(b.name ?? '').trim().slice(0, 30), rel = String(b.rel ?? '').slice(0, 20);
  if (!name || !rel) fail('bad_request', '보호자 이름과 관계를 적어 주세요.');
  const rec = { status: 'agreed', name, relation: rel, email: gc.email, agreed_at: Date.now(), requested_at: gc.requested_at,
    ip_hash: (await sha256hex(req.headers.get('x-forwarded-for') ?? '')).slice(0, 16), method: 'email-link+web-consent+email-notice', policy_version: env('POLICY_VERSION', '2026-12-01') };
  await sb.from('accounts').update({ guardian_consent: rec }).eq('id', acc!.id);
  await sendMail(gc.email, '[002BOOK] 보호자 동의가 확인됐어요', mailShell('보호자 동의 확인',
    `<p>${escHtml(name)} 님(${escHtml(rel)})의 동의로 자녀(아이디 <b>${escHtml(acc!.id)}</b>)의 가입이 완료됐어요. (${new Date().toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' })})</p>
     <p>본인이 동의하지 않았다면 바로 ${escHtml(env('PRIVACY_CONTACT', 'anji01204@gmail.com'))} 로 알려 주세요. 자녀 정보는 언제든지 열람·정정·삭제를 요청할 수 있어요.</p>`)).catch(() => {});
  return { message: '동의가 완료됐어요. 이제 자녀가 002BOOK에 로그인할 수 있어요. 확인 메일도 보내 드렸어요.' };
}

Deno.serve(async (req) => {
  const h = cors(req);
  if (req.method === 'OPTIONS') return new Response('ok', { headers: h });
  if (req.method !== 'POST') return new Response('002BOOK API', { headers: h });
  try {
    const b = await req.json();
    const result = await handle(req, b);
    return new Response(JSON.stringify({ result: result ?? null }), { headers: { ...h, 'content-type': 'application/json' } });
  } catch (e) {
    const err = e instanceof HttpErr ? e : new HttpErr('server_error', '잠시 뒤 다시 시도해 주세요.', 500);
    if (!(e instanceof HttpErr)) console.error(e);
    return new Response(JSON.stringify({ error: { code: err.code, message: err.message } }), { status: err.status, headers: { ...h, 'content-type': 'application/json' } });
  }
});
