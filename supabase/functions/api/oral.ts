// 구술 테스트 서버 처리 (3차 특허 명세서의 실시예를 그대로 구현)
// - 문항별 진행 상태(ST2 1차 평가 완료 → ST3 숙고 잠금 → ST4 2차 답변 가능 → ST5 성장 평가 완료)를 서버가 관리한다.
// - 따라 읽기 완료 시각은 서버 시계로 기록하고, 숙고 시간 전의 2차 답변 저장·평가 요청은 거부한다.
// - 모범 답안 유사도(고유 n-그램)·자기 답변 유지도·최장 연속 일치로 암기를 판정하고, 성장 점수를 산식으로 계산한다.
// - 생성형 언어 모델 응답은 구조·범위를 검증한다. 영역 점수는 수준 1~5를 40·55·70·85·100%로 환산하고 배점으로 가중 평균한다(2026-11 개정).
// - 성장 점수(α·β·γ 결합, 암기 감산)는 명세서 실시예대로 계산해 저장한다. 화면과 리포트의 대표 숫자는 점수 변화와 나아진 영역 수다.
import { env, fail } from './lib.ts';

type Row = { path: string; data: Record<string, unknown>; owner: string | null; version: number };
export type OralIO = {
  read: (p: string) => Promise<Row | null>;
  write: (p: string, d: Record<string, unknown>, owner: string | null, prev: Row | null) => Promise<unknown>;
};

export const ORAL = {
  N: 3,            // 문항 수
  n: 4,            // n-그램 길이
  TM: 0.6,         // 제1 임계값 τm (모범 답안 유사도)
  TO: 0.2,         // 제2 임계값 τo (자기 답변 유지도)
  TS: 0.5,         // 제3 임계값 τs (따라 읽기 일치도)
  L: 20,           // 최장 연속 일치 기준 글자 수
  LMARK: 8,        // 암기 구간 표시 기준 글자 수
  PEN: 15,         // 암기 판정 시 감산값 P
  A: 0.6, B: 0.25, G: 0.15,  // α, β, γ
  CSTAR: 300,      // 따라 읽기 예상 낭독 속도 (자/분): 음성 인식이 없을 때 따라 읽기 시간 판단에 쓴다
  CLO: 200, CHI: 330, // 적정 말 속도 범위 (자/분). 범위 안에서는 감점하지 않는다
  EMAX: 0.3,       // 수정 비율 기준값
  // 평가 영역과 배점 (2026-11 개정). 표현·전달은 음성 인식 품질이 나쁘면 채점 보류할 수 있다
  ITEMS: ['질문 이해와 작품 활용', '주장과 근거', '구성', '표현', '전달', '생각의 깊이'],
  W: [20, 30, 15, 10, 15, 10],
  HOLD: ['표현', '전달'],
};
const LP = [0, 40, 55, 70, 85, 100];
/* 평가 영역 설정(관리자 화면 config/rubric.oral). 영역 6개, 이름 1~20자(서로 다름), 배점 1~60 정수 합 100.
   c·l(기준 설명·수준 설명)은 앱이 AI 지시문을 만들 때 쓰고, 서버 채점은 이름·배점·보류 여부만 쓴다 */
export type RbItem = { k: string; w: number; h?: boolean; c?: string; l?: string };
export const RB_DEF: RbItem[] = ORAL.ITEMS.map((k, n) => ({ k, w: ORAL.W[n], h: ORAL.HOLD.includes(k) }));
export function rbValid(v: unknown): RbItem[] | null {
  if (!Array.isArray(v) || v.length !== 6) return null;
  const out: RbItem[] = []; const seen = new Set<string>(); let sum = 0;
  for (const x of v) {
    const o = (x ?? {}) as Record<string, unknown>;
    const k = String(o.k ?? '').trim(), w = Number(o.w);
    if (!k || k.length > 20 || seen.has(k) || !Number.isInteger(w) || w < 1 || w > 60) return null;
    seen.add(k); sum += w;
    out.push({ k, w, h: !!o.h, ...(o.c ? { c: String(o.c).slice(0, 300) } : {}), ...(o.l ? { l: String(o.l).slice(0, 900) } : {}) });
  }
  return sum === 100 ? out : null;
}
async function rbNow(io: OralIO): Promise<RbItem[]> {
  const r = await io.read('config/rubric');
  return rbValid((r?.data as Record<string, unknown> | undefined)?.oral) ?? RB_DEF;
}
/** 수준 1~5(또는 백분율·10점 척도)를 수준으로. 비어 있으면 0 */
export function lvl(v: unknown) {
  if (v == null || v === '' || v === '보류') return 0;
  let x = Number(v); if (!Number.isFinite(x) || x <= 0) return 0;
  if (x <= 5) return Math.max(1, Math.min(5, Math.round(x)));
  if (x <= 10) x *= 10;
  return x >= 93 ? 5 : x >= 78 ? 4 : x >= 63 ? 3 : x >= 48 ? 2 : 1;
}
/** 영역 점수(환산 %)·수준·채점 보류·가중 총점 */
export function rubric(sc: Record<string, unknown>, items: RbItem[] = RB_DEF) {
  const scores: Record<string, number> = {}, levels: Record<string, number> = {}, held: string[] = [];
  let s = 0, w = 0;
  items.forEach(({ k, w: wt, h }) => {
    const l = lvl(sc[k]);
    if (!l) { if (h) { held.push(k); return; } fail('bad_ai', '평가 점수가 비어 있어요.', 422); }
    levels[k] = l; scores[k] = LP[l]; s += wt * LP[l]; w += wt;
  });
  return { scores, levels, held, total: w ? Math.round(s / w) : 0 };
}
const THINK = () => Math.max(1, Number(env('ORAL_THINK_SEC', '180')));          // 숙고 시간 상한: 이 시간이 지나면 저절로 2차 답변이 열린다
const THINK_MIN = () => Math.min(THINK(), Math.max(1, Number(env('ORAL_THINK_MIN_SEC', '60')))); // 숙고 시간 하한: 이 시간 전에는 어떤 경우에도 2차 답변을 받지 않는다
/* 잠금 해제 시각: 하한이 지난 뒤 학생이 '생각 완료'를 누른 시각, 누르지 않으면 상한. 서버 시계로만 판단한다 */
const unlockAt = (sh: Record<string, unknown>, s: { think: number; thinkMin?: number }) => {
  const at = Number(sh.at), min = at + (s.thinkMin ?? THINK_MIN()) * 1000, max = at + s.think * 1000;
  return sh.doneAt ? Math.min(max, Math.max(min, Number(sh.doneAt))) : max;
};

/* ---------- 문자열 지표 ---------- */
const KEEP = /[0-9A-Za-z가-힣]/;
export const clean = (s: unknown) => String(s ?? '').replace(/[^0-9A-Za-z가-힣]/g, '');
type MS = Map<string, number>;
export function grams(s: string, n = ORAL.n): MS {
  const m: MS = new Map();
  for (let i = 0; i + n <= s.length; i++) { const g = s.slice(i, i + n); m.set(g, (m.get(g) ?? 0) + 1); }
  return m;
}
const size = (m: MS) => { let k = 0; for (const v of m.values()) k += v; return k; };
const inter = (a: MS, b: MS) => { let k = 0; for (const [g, c] of a) k += Math.min(c, b.get(g) ?? 0); return k; };
function minus(a: MS, ...bs: MS[]): MS {
  const o: MS = new Map(a);
  for (const b of bs) for (const [g, c] of b) { const v = (o.get(g) ?? 0) - c; if (v > 0) o.set(g, v); else o.delete(g); }
  return o;
}
/** 최장 공통 부분 수열 길이 */
export function lcs(a: string, b: string) {
  if (!a || !b) return 0;
  let prev = new Uint16Array(b.length + 1), cur = new Uint16Array(b.length + 1);
  for (let i = 1; i <= a.length; i++) {
    for (let j = 1; j <= b.length; j++) cur[j] = a[i - 1] === b[j - 1] ? prev[j - 1] + 1 : Math.max(prev[j], cur[j - 1]);
    [prev, cur] = [cur, prev]; cur.fill(0);
  }
  return prev[b.length];
}
/** a의 각 위치에서 끝나는, b와의 최장 공통 연속 부분 문자열 길이 */
function runEnds(a: string, b: string) {
  const out = new Uint16Array(a.length);
  let prev = new Uint16Array(b.length + 1), cur = new Uint16Array(b.length + 1);
  for (let i = 1; i <= a.length; i++) {
    let best = 0;
    for (let j = 1; j <= b.length; j++) { cur[j] = a[i - 1] === b[j - 1] ? prev[j - 1] + 1 : 0; if (cur[j] > best) best = cur[j]; }
    out[i - 1] = best; [prev, cur] = [cur, prev]; cur.fill(0);
  }
  return out;
}
export const lmax = (a: string, b: string) => { let m = 0; for (const v of runEnds(a, b)) if (v > m) m = v; return m; };
/** 2차 답변에서 모범 답안과 기준 글자 수 이상 연속 일치하는 구간을 [[ ]]로 감싼다 (원문 글자 위치 유지) */
export function markSpans(text: string, model: string, own = '', min = ORAL.LMARK) {
  const idx: number[] = []; let c = '';
  for (let i = 0; i < text.length; i++) if (KEEP.test(text[i])) { idx.push(i); c += text[i]; }
  const ends = runEnds(c, clean(model)); const cov = new Uint8Array(c.length);
  for (let j = 0; j < c.length; j++) if (ends[j] >= min) for (let k = j - ends[j] + 1; k <= j; k++) cov[k] = 1;
  // 1차 답변에도 있던 구간은 학생 자신의 말이므로 표시하지 않는다
  if (own) { const oe = runEnds(c, clean(own)); for (let j = 0; j < c.length; j++) if (oe[j] >= min) for (let k = j - oe[j] + 1; k <= j; k++) cov[k] = 0; }
  let out = '', last = 0, j = 0;
  while (j < c.length) {
    if (!cov[j]) { j++; continue; }
    let e = j; while (e + 1 < c.length && cov[e + 1]) e++;
    out += text.slice(last, idx[j]) + '[[' + text.slice(idx[j], idx[e] + 1) + ']]'; last = idx[e] + 1; j = e + 1;
  }
  return out + text.slice(last);
}
// 군말: 뜻 없이 쓰이는 소리만 센다. '그, 아, 약간, 막, 그러니까'는 뜻 있는 낱말로도 쓰여 세지 않는다(2026-11 개정)
const FILL = /(^|[\s,.])(음+|어+|으+|저기|뭐지|뭐랄까)(?=[\s,.?!]|$)/g;
/** 적정 말 속도 범위에서 벗어난 정도(자/분). 범위 안이면 0 */
export const speedDev = (c: number) => Math.max(0, ORAL.CLO - c, c - ORAL.CHI);
export const fillers = (t: string) => (String(t ?? '').match(FILL) ?? []).length;
const clip = (x: number, lo = 70, hi = 100) => Math.max(lo, Math.min(hi, x));
const r3 = (x: number) => Math.round(x * 1000) / 1000;

/** 수정 비율 E = 1 − LCS(Traw, Tedit) ÷ max(|Traw|, |Tedit|) */
export function editRatio(raw: unknown, text: unknown) {
  const a = clean(raw), b = clean(text);
  if (!a) return null; // 인식 원문이 없으면(직접 받아 적음) 계산하지 않음
  return 1 - lcs(a, b) / Math.max(a.length, b.length, 1);
}
/** 말하기 습관 지표: 인식 원문 기준(없으면 수정문) */
export function habit(raw: unknown, text: unknown, sec: unknown) {
  const base = String(raw ?? '').trim() || String(text ?? '');
  const s = Math.max(1, Number(sec) || 0);
  const chars = clean(base).length;
  return { f: fillers(base) / (s / 60), c: chars / (s / 60), chars, fills: fillers(base), fromRaw: !!String(raw ?? '').trim() };
}
/** 암기 판별 지표 (수학식 3·5, 최장 연속 일치) */
export function memo(a1: string, a2: string, M: string, Q: string) {
  const c1 = clean(a1), c2 = clean(a2), cm = clean(M), cq = clean(Q);
  const G1 = grams(c1), G2 = grams(c2), GM = grams(cm), GQ = grams(cq);
  const n2 = Math.max(1, size(G2)), n1 = Math.max(1, size(G1));
  const Sm = inter(G2, GM) / n2, Smu = inter(G2, minus(GM, G1, GQ)) / n2, So = inter(G2, G1) / n1;
  const Lmax = lmax(c2, cm);
  const copied = So < ORAL.TO && (Smu >= ORAL.TM || Lmax >= ORAL.L);
  return { Sm: r3(Sm), Smu: r3(Smu), So: r3(So), Lmax, copied };
}

/* ---------- 문서 ---------- */
const KEY = /^[bc]\d{1,3}$/;
export const checkKey = (k: unknown) => { const s = String(k ?? ''); if (!KEY.test(s)) fail('bad_request', '잘못된 요청이에요.'); return s; };
const checkN = (n: unknown) => { const v = Number(n); if (!Number.isInteger(v) || v < 0 || v >= ORAL.N) fail('bad_request', '잘못된 문항이에요.'); return v; };
const str = (v: unknown, max: number) => String(v ?? '').slice(0, max);
const arr = (v: unknown) => (Array.isArray(v) ? v : []);
type St = { uid: string; key: string; st: number[]; sh: (Record<string, unknown> | null)[]; ans2: (Record<string, unknown> | null)[]; tries: number[]; think: number; thinkMin?: number; at: number };

async function loadState(io: OralIO, uid: string, key: string) {
  const p = `oralst/${uid}_${key}`;
  const row = await io.read(p);
  if (row) return { row, st: row.data as unknown as St };
  const e1 = await io.read(`orals/${uid}_${key}`);
  if (!e1) return { row: null, st: null };
  // 서버 상태가 생기기 전의 기록을 이어받는다
  const a = (await io.read(`orals/${uid}_${key}_a`))?.data ?? {};
  const r2 = await io.read(`orals/${uid}_${key}_r2`);
  const sh = arr(a.sh).slice(0, ORAL.N) as (Record<string, unknown> | null)[];
  const ans2 = arr(a.ans2).slice(0, ORAL.N) as (Record<string, unknown> | null)[];
  const st = Array.from({ length: ORAL.N }, (_, n) => (r2 ? 5 : ans2[n] ? 4 : sh[n] ? 3 : 2));
  const s: St = { uid, key, st, sh: Array.from({ length: ORAL.N }, (_, n) => sh[n] ?? null), ans2: Array.from({ length: ORAL.N }, (_, n) => ans2[n] ?? null), tries: [0, 0, 0], think: THINK(), thinkMin: THINK_MIN(), at: Date.now() };
  await io.write(p, s as unknown as Record<string, unknown>, uid, null);
  return { row: await io.read(p), st: s };
}
async function saveState(io: OralIO, uid: string, key: string, s: St, prev: Row | null) {
  s.at = Date.now();
  await io.write(`oralst/${uid}_${key}`, s as unknown as Record<string, unknown>, uid, prev);
}

/* ---------- 요청 처리 ---------- */
export async function oralOp(op: string, uid: string, b: Record<string, unknown>, io: OralIO): Promise<unknown> {
  const key = checkKey(b.key);
  const p1 = `orals/${uid}_${key}`, pA = `orals/${uid}_${key}_a`, p2 = `orals/${uid}_${key}_r2`;

  if (op === 'oral.state') {
    const { st } = await loadState(io, uid, key);
    return { state: st, now: Date.now(), think: st?.think ?? THINK(), thinkMin: st?.thinkMin ?? THINK_MIN(), cfg: { TS: ORAL.TS, TM: ORAL.TM, TO: ORAL.TO, L: ORAL.L } };
  }

  if (op === 'oral.save1') {
    // 1차 평가 결과 저장: 생성형 언어 모델 응답을 검증하고 점수를 범위로 자른다. 한 번 저장하면 비교 기준이 고정된다.
    if (await io.read(p1)) fail('already', '1차 평가는 이미 저장됐어요.', 409);
    const rec = (b.rec ?? {}) as Record<string, unknown>;
    const A = (await io.read(pA))?.data ?? {};
    const ans = arr(A.ans);
    const answers = arr(rec.answers);
    if (answers.length !== ORAL.N) fail('bad_ai', '평가 결과의 답변 수가 맞지 않아요.', 422);
    const rbi = await rbNow(io);   // 이 시험에 쓴 평가 영역을 기록해 2차 평가도 같은 기준으로 매긴다
    const { scores, levels, held, total } = rubric((rec.scores ?? {}) as Record<string, unknown>, rbi);
    const outA = answers.map((x, n) => {
      const a = (x ?? {}) as Record<string, unknown>; const src = (ans[n] ?? {}) as Record<string, unknown>;
      if (!String(a.model ?? '').trim()) fail('bad_ai', '모범 답안이 비어 있어요.', 422);
      const text = str(src.text ?? a.text, 4000);
      if (!text.trim()) fail('bad_request', '말한 내용이 비어 있는 답변이 있어요.');
      return { ...a, no: n + 1, q: str(src.q ?? a.q, 400), text, raw: str(src.raw, 4000), sec: Number(src.sec ?? a.sec) || 0, model: str(a.model, 1200) };
    });
    const out = { ...rec, scores, levels, held, rb: 2, rbi, total, answers: outA, uid, round: 1, at: Date.now() };
    await io.write(p1, out, uid, null);
    const s: St = { uid, key, st: [2, 2, 2], sh: [null, null, null], ans2: [null, null, null], tries: [0, 0, 0], think: THINK(), thinkMin: THINK_MIN(), at: Date.now() };
    await io.write(`oralst/${uid}_${key}`, s as unknown as Record<string, unknown>, uid, await io.read(`oralst/${uid}_${key}`));
    return { rec: out };
  }

  const { row, st } = await loadState(io, uid, key);
  if (!st) fail('no_eval', '1차 구술 평가를 먼저 받아 주세요.', 409);
  const e1 = (await io.read(p1))!.data as Record<string, unknown>;
  const A1 = arr(e1.answers) as Record<string, unknown>[];
  const s = st!;

  if (op === 'oral.shadow') {
    // 따라 읽기: 서버가 일치도를 계산하고, 기준 이상일 때만 완료 시각(서버 시계)을 기록해 숙고 잠금을 시작한다
    const n = checkN(b.n);
    if (s.st[n] >= 4) fail('bad_state', '이미 다시 대답한 질문이에요.', 409);
    const M = String(A1[n]?.model ?? '');
    const text = str(b.text, 4000), raw = str(b.raw, 4000), sec = Math.max(0, Number(b.sec) || 0);
    let acc: number | null = null, ok: boolean;
    if (clean(text)) { acc = lcs(clean(M), clean(text)) / Math.max(1, clean(M).length); ok = acc >= ORAL.TS; }
    else ok = sec >= ORAL.TS * (clean(M).length / (ORAL.CSTAR / 60)); // 음성 인식이 없으면 예상 낭독 시간의 비율로 판단
    s.tries[n] = (s.tries[n] ?? 0) + 1;
    const accP = acc == null ? null : Math.round(acc * 100);
    if (!ok) { await saveState(io, uid, key, s, row); return { ok: false, acc: accP, need: Math.round(ORAL.TS * 100) }; }
    const at = Date.now();
    s.sh[n] = { at, acc: accP, sec, text, raw, mime: str(b.mime, 60), audio: !!b.audio, q: M.slice(0, 1200) };
    s.st[n] = 3;
    await saveState(io, uid, key, s, row);
    return { ok: true, acc: accP, at, think: s.think, thinkMin: s.thinkMin ?? THINK_MIN(), now: at };
  }

  if (op === 'oral.thinkDone') {
    // 생각 완료: 숙고 하한이 지났을 때만 받아들이고, 그 시각(서버 시계)을 잠금 해제 시각으로 기록한다
    const n = checkN(b.n);
    const sh = s.sh[n];
    if (!sh || s.st[n] !== 3) fail('bad_state', '생각 시간이 아니에요.', 409);
    const now = Date.now(); const min = Number(sh!.at) + (s.thinkMin ?? THINK_MIN()) * 1000;
    if (now < min) fail('think_lock', `최소 생각 시간이 ${Math.ceil((min - now) / 1000)}초 남았어요.`, 409, { left: Math.ceil((min - now) / 1000) });
    if (!sh!.doneAt) { sh!.doneAt = Math.min(now, Number(sh!.at) + s.think * 1000); sh!.thinkSec = Math.round((Number(sh!.doneAt) - Number(sh!.at)) / 1000); await saveState(io, uid, key, s, row); }
    return { ok: true, doneAt: sh!.doneAt, thinkSec: sh!.thinkSec, now };
  }

  if (op === 'oral.ans2') {
    // 2차 답변 저장: 서버 시각이 완료 시각 + 숙고 시간 이전이면 거부한다
    const n = checkN(b.n);
    if (await io.read(p2)) fail('bad_state', '2차 평가를 이미 마쳤어요.', 409);
    const sh = s.sh[n];
    if (!sh) fail('bad_state', '모범 답안 따라 읽기를 먼저 해 주세요.', 409);
    const now = Date.now(); const until = unlockAt(sh!, s);
    if (now < until) fail('think_lock', `생각 시간이 ${Math.ceil((until - now) / 1000)}초 남았어요. 생각을 마쳤으면 '생각 완료'를 눌러 주세요.`, 409, { left: Math.ceil((until - now) / 1000) });
    if (b.edit) {
      const cur = s.ans2[n]; if (!cur) fail('bad_state', '먼저 다시 대답해 주세요.', 409);
      s.ans2[n] = { ...cur!, text: str(b.text, 4000) };
    } else {
      s.ans2[n] = { at: now, q: str(A1[n]?.q, 400), text: str(b.text, 4000), raw: str(b.raw, 4000), sec: Math.max(0, Number(b.sec) || 0), mime: str(b.mime, 60), audio: !!b.audio };
    }
    s.st[n] = 4;
    await saveState(io, uid, key, s, row);
    return { ok: true, ans2: s.ans2[n] };
  }

  // 2차 평가 준비·마무리에 쓰는 문항별 지표
  const items = () => A1.map((a1, n) => {
    const a2 = s.ans2[n] ?? {}; const t2 = String(a2.text ?? ''); const M = String(a1.model ?? ''); const Q = String(a1.q ?? '');
    const m = memo(String(a1.text ?? ''), t2, M, Q);
    const h1 = habit(a1.raw, a1.text, a1.sec), h2 = habit(a2.raw, a2.text, a2.sec);
    const E1 = editRatio(a1.raw, a1.text), E2 = editRatio(a2.raw, a2.text);
    return { ...m, marked: markSpans(t2, M, String(a1.text ?? '')), E1: E1 == null ? null : r3(E1), E2: E2 == null ? null : r3(E2), f1: r3(h1.f), f2: r3(h2.f), c1: Math.round(h1.c), c2: Math.round(h2.c), fills2: h2.fills, chars2: h2.chars, rawOk: h1.fromRaw && h2.fromRaw };
  });
  const ready = () => {
    if (s.ans2.some((x) => !x || !String(x.text ?? '').trim())) fail('bad_state', '세 질문에 모두 다시 대답해 주세요.', 409);
    const now = Date.now();
    if (s.sh.some((x) => !x || now < unlockAt(x, s))) fail('think_lock', '생각 시간이 끝나지 않은 질문이 있어요.', 409);
  };

  if (op === 'oral.prep2') { ready(); return { items: items(), cfg: ORAL }; }

  if (op === 'oral.finalize') {
    // 2차 평가 마무리: 생성형 언어 모델 응답을 검증하고, 성장 점수는 서버가 산식으로 계산해 저장한다
    if (await io.read(p2)) fail('already', '2차 평가는 이미 저장됐어요.', 409);
    ready();
    const ev = (b.ev ?? {}) as Record<string, unknown>;
    const evA = arr(ev.answers) as Record<string, unknown>[];
    if (evA.length !== ORAL.N) fail('bad_ai', '평가 결과의 답변 수가 맞지 않아요.', 422);
    const rbi = rbValid(e1.rbi) ?? await rbNow(io);
    const { scores, levels, held, total: T2 } = rubric((ev.scores ?? {}) as Record<string, unknown>, rbi);
    const T1 = Number(e1.total) || 0;
    // 영역별 수준 변화: 1차와 이름이 같은 영역만 비교한다(개정 전 1차 기록은 비교하지 않음)
    const s1 = (e1.scores ?? {}) as Record<string, unknown>;
    const cmp = rbi.map((x) => x.k).filter((k) => s1[k] != null && levels[k] != null);
    const up = cmp.filter((k) => levels[k] > lvl(s1[k])).length, down = cmp.filter((k) => levels[k] < lvl(s1[k])).length;
    const Gd = clip(85 + 1.5 * (T2 - T1));
    const its = items();
    const answers = its.map((m, n) => {
      const x = evA.find((y) => Number(y?.no) === n + 1) ?? evA[n] ?? {};
      const gai = clip(Math.round(Number(x.growth)) || 70);
      const useH = m.rawOk && (m.E1 ?? 0) <= ORAL.EMAX && (m.E2 ?? 0) <= ORAL.EMAX;
      const Gh = clip(85 + 10 * (m.f1 - m.f2) / Math.max(m.f1, 1) + 5 * (speedDev(m.c1) - speedDev(m.c2)) / ((ORAL.CLO + ORAL.CHI) / 2));
      const P = m.copied ? ORAL.PEN : 0;
      const g = useH ? ORAL.A * gai + ORAL.B * Gd + ORAL.G * Gh - P
        : (ORAL.A / (ORAL.A + ORAL.B)) * gai + (ORAL.B / (ORAL.A + ORAL.B)) * Gd - P;
      const G = Math.round(clip(g));
      const a2 = s.ans2[n]!, sh = s.sh[n]!;
      return {
        no: n + 1, q: str(A1[n]?.q, 400), text: str(a2.text, 4000), sec: Number(a2.sec) || 0, chars: m.chars2, cpm: m.c2, fill: m.fills2, audio: !!a2.audio,
        summary: str(x.summary, 400), improved: str(x.improved, 600), still: str(x.still, 600), marks: arr(x.marks).slice(0, 8), sentences: arr(x.sentences).slice(0, 3),
        growth: G, calc: { gai, Gd: Math.round(Gd * 10) / 10, Gh: useH ? Math.round(Gh * 10) / 10 : null, P, Sm: m.Sm, Smu: m.Smu, So: m.So, Lmax: m.Lmax, E1: m.E1, E2: m.E2 },
        copied: m.copied, marked: m.marked, shAcc: sh.acc ?? null, shSec: Number(sh.sec) || 0, shAudio: !!sh.audio, thSec: sh.at ? Math.round((unlockAt(sh, s) - Number(sh.at)) / 1000) : null,
      };
    });
    const growth = Math.round(answers.reduce((x, a) => x + a.growth, 0) / answers.length);
    const keep = ['scoreWhy', 'growthWhy', 'growthComment', 'comment', 'praise', 'strengths', 'improvements', 'tags', 'cumulative', 'nextGoal', 'teacher'];
    const rec: Record<string, unknown> = {};
    for (const k of keep) if (ev[k] != null) rec[k] = ev[k];
    Object.assign(rec, {
      scores, levels, held, rb: 2, rbi, total: T2, delta: T2 - T1, up, down, growth, answers, firstTotal: T1, firstScores: e1.scores, at: Date.now(), firstAt: e1.at,
      title: e1.title, g: e1.g, m: e1.m, kw: e1.kw ?? '', uid, round: 2,
      calc: { version: 2, CLO: ORAL.CLO, CHI: ORAL.CHI, TM: ORAL.TM, TO: ORAL.TO, L: ORAL.L, PEN: ORAL.PEN, A: ORAL.A, B: ORAL.B, G: ORAL.G, think: s.think, thinkMin: s.thinkMin ?? THINK_MIN(), thinkSec: s.sh.map((x) => x ? Math.round((unlockAt(x, s) - Number(x.at)) / 1000) : null) },
    });
    await io.write(p2, rec, uid, null);
    s.st = s.st.map(() => 5);
    await saveState(io, uid, key, s, row);
    return { rec };
  }

  fail('bad_op', '알 수 없는 요청이에요.');
}
