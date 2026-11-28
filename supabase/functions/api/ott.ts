// 영화를 볼 수 있는 OTT (서버 op: media.ott, 2026-11-28 사용자 지시)
// - 코스 영화 카드의 '아직' 옆에 넷플릭스·쿠팡플레이·웨이브 등 지금 구독으로 볼 수 있는 곳을 적는다.
// - Claude 웹 검색(web_search 도구)으로 확인한다. JustWatch 한국 페이지와 각 서비스 공식 페이지를 먼저 보게 한다.
//   TMDB(JustWatch 데이터 API)는 상업 이용이 유료라 쓰지 않는다(README 11-24 결정).
// - 결과는 제목·연도 기준 sys/ott_<해시>에 7일 캐시 → 7일이 지난 뒤 누군가 그 영화를 보면 그때 다시 확인한다(7일에 한 번 자동 업데이트).
//   검색이 실패하면 30분만 기억해 곧 다시 확인한다.
// - 서비스 이름은 아래 목록으로만 받아 적는다(AI가 다른 이름을 써도 같은 서비스로 맞추고, 목록 밖 이름은 버린다).
import { env, fail, sha256hex } from './lib.ts';
import type { BookIO } from './books.ts';
import { normT } from './media.ts';

const DAY = 86_400_000;
const clean = (s: unknown, n: number) => String(s ?? '').replace(/\s+/g, ' ').trim().slice(0, n);

/* 구독 서비스: [앱에 적는 이름, 알아볼 말들] */
const SUBS: [string, RegExp][] = [
  ['넷플릭스', /넷플릭스|netflix/i],
  ['디즈니플러스', /디즈니|disney/i],
  ['티빙', /티빙|tving/i],
  ['웨이브', /웨이브|wavve/i],
  ['쿠팡플레이', /쿠팡|coupang/i],
  ['왓챠', /왓챠|watcha/i],
  ['애플TV+', /애플\s*tv\s*\+|애플\s*tv\s*플러스|apple\s*tv\s*\+|apple\s*tv\s*plus/i],
  ['프라임비디오', /프라임\s*비디오|prime\s*video|amazon/i],
];
/* 편당 구매·대여 */
const RENT: [string, RegExp][] = [
  ['네이버 시리즈온', /시리즈\s*온|series\s*on|naver/i],
  ['구글 플레이', /구글|google/i],
  ['애플TV', /애플|apple|itunes/i],
  ['U+모바일tv', /u\+|유플러스|lg\s*u/i],
  ['쿠팡플레이', /쿠팡|coupang/i],
  ['티빙', /티빙|tving/i],
  ['웨이브', /웨이브|wavve/i],
  ['KT 지니TV', /지니|genie|\bkt\b/i],
  ['B tv', /\bb\s*tv|\bsk\b/i],
];
const norm = (xs: unknown, list: [string, RegExp][]) => {
  const out: string[] = [];
  for (const x of Array.isArray(xs) ? xs : []) {
    const s = clean(x, 40); if (!s) continue;
    const hit = list.find(([, re]) => re.test(s)); if (hit && !out.includes(hit[0])) out.push(hit[0]);
  }
  return out;
};
export const ottNorm = (o: { subs?: unknown; rent?: unknown }) => {
  const subs = norm(o.subs, SUBS);
  return { subs, rent: norm(o.rent, RENT).filter((r) => !subs.includes(r)) };
};

async function ask(title: string, year: string): Promise<{ subs: string[]; rent: string[] } | null> {
  const first = await ask1(title, year, env('MODEL_OTT', env('MODEL_QUICK', 'claude-haiku-5-5')));
  // 빠른 모델이 웹 검색 도구를 받지 않으면(400) 기본 모델로 한 번 더
  if (first === 'retry') { const r = await ask1(title, year, env('MODEL_DEFAULT', 'claude-sonnet-5-5')); return r === 'retry' ? null : r; }
  return first;
}
async function ask1(title: string, year: string, model: string): Promise<{ subs: string[]; rent: string[] } | null | 'retry'> {
  const key = env('ANTHROPIC_API_KEY'); if (!key) return null;
  const today = new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);
  const prompt = `영화 「${title}」${year ? `(${year}년)` : ''}을 오늘(${today}) 한국에서 어느 OTT로 볼 수 있는지 웹 검색으로 확인해라.
JustWatch 한국(justwatch.com/kr) 페이지와 각 서비스 공식 페이지를 먼저 본다. 같은 제목의 다른 영화(리메이크·다른 연도)와 헷갈리지 않는다.
검색 결과에서 확인한 것만 적고, 확인하지 못한 서비스는 넣지 않는다.
- subs: 월 구독만으로 추가 결제 없이 볼 수 있는 서비스. 넷플릭스·디즈니플러스·티빙·웨이브·쿠팡플레이·왓챠·애플TV+·프라임비디오 가운데서만.
- rent: 편당 구매·대여로 볼 수 있는 곳(네이버 시리즈온·구글 플레이·애플TV·U+모바일tv·KT 지니TV·B tv 등).
JSON 하나만 출력한다: {"subs":["넷플릭스"],"rent":["네이버 시리즈온"]}`;
  const thinking = /^claude-sonnet-5-5/.test(model) ? { type: 'between_tools' }
    : /^claude-(haiku-5-5|sonnet-5(?!-5)|opus-5(?!-5)|sonnet-4|opus-4|haiku-4)/.test(model) ? { type: 'disabled' } : null;
  const send = (th: unknown) => fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST', signal: AbortSignal.timeout(60_000),
    headers: { 'x-api-key': key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json' },
    body: JSON.stringify({
      model, max_tokens: 1500, messages: [{ role: 'user', content: prompt }],
      tools: [{ type: 'web_search_20250305', name: 'web_search', max_uses: 4, user_location: { type: 'approximate', country: 'KR', timezone: 'Asia/Seoul' } }],
      ...(th ? { thinking: th } : {}),
    }),
  });
  try {
    let r = await send(thinking); let j = await r.json().catch(() => null);
    if (thinking && r.status === 400 && /thinking/i.test(JSON.stringify(j ?? ''))) { r = await send(null); j = await r.json().catch(() => null); }
    if (!r.ok || !j) { console.log('ott http', model, r.status, JSON.stringify(j ?? '').slice(0, 300)); return r.status === 400 ? 'retry' : null; }
    const text = (j.content ?? []).filter((c: { type: string }) => c.type === 'text').map((c: { text: string }) => c.text).join('');
    const m = text.match(/\{[^{}]*"subs"[^{}]*\}/g); if (!m) { console.log('ott no json', text.slice(0, 200)); return null; }
    return ottNorm(JSON.parse(m[m.length - 1]));
  } catch (e) { console.log('ott err', String(e).slice(0, 200)); return null; }
}

export async function ottOp(uid: string, b: Record<string, unknown>, io: BookIO) {
  const title = clean(b.title, 80).replace(/\s*\(.*\)\s*$/, ''), year = /^\d{4}$/.test(String(b.year ?? '')) ? String(b.year) : '';
  if (normT(title).length < 1) fail('bad_request', '제목이 필요해요.');
  const fake = env('FAKE_OTT');
  if (!fake && !env('ANTHROPIC_API_KEY')) fail('ott_not_configured', '볼 수 있는 곳 찾기가 아직 설정되지 않았어요.', 503);
  const p = `sys/ott_${(await sha256hex('ott|' + normT(title) + '|' + year)).slice(0, 24)}`;
  const row = await io.read(p);
  if (row) {
    const at = Number(row.data.at) || 0, ttl = row.data.err ? 30 * 60e3 : 7 * DAY;
    if (Date.now() - at < ttl) return { subs: row.data.subs || [], rent: row.data.rent || [], at: row.data.err ? Number(row.data.ok) || 0 : at, cached: true };
  }
  // 회원당 하루 확인 수 (캐시로 답한 것은 세지 않음)
  const qp = `sys/ottuse_${uid}`; const qr = await io.read(qp);
  const day = new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);
  const n = qr && qr.data.day === day ? Number(qr.data.n) || 0 : 0;
  if (n >= Number(env('OTT_DAILY_LIMIT', '40'))) fail('rate_limited', '오늘 볼 수 있는 곳 찾기를 다 썼어요. 내일 다시 찾아요.', 429);
  await io.write(qp, { day, n: n + 1 }, null, qr);
  let res: { subs: string[]; rent: string[] } | null;
  if (fake) { // 시험용: {"제목": {"subs":[…],"rent":[…]}}
    const m = JSON.parse(fake) as Record<string, { subs?: string[]; rent?: string[] }>;
    res = m[title] ? ottNorm(m[title]) : { subs: [], rent: [] };
  } else res = await ask(title, year);
  // 실패하면 예전 결과가 있으면 그것을 30분 더 쓰고, 없으면 빈 결과를 30분 기억
  const old = row?.data ?? {};
  const now = Date.now();
  if (!res) {
    await io.write(p, { title, year, subs: old.subs || [], rent: old.rent || [], at: now, err: 1, ok: old.ok || 0 }, null, row);
    return { subs: old.subs || [], rent: old.rent || [], at: Number(old.ok) || 0, cached: false };
  }
  await io.write(p, { title, year, subs: res.subs, rent: res.rent, at: now, ok: now }, null, row);
  return { ...res, at: now, cached: false };
}
