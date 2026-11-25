// 책 표지·영화 포스터 자동 찾기 (서버 op: media.art)
// - 책: 국립중앙도서관 ISBN 서지정보(TITLE_URL, 인증키 NL_CERT_KEY) → 없으면 카카오(다음) 책 검색 thumbnail(KAKAO_REST_KEY)
// - 영화: TMDB 영화 검색 poster_path(TMDB_TOKEN, 한국어) → 없으면 한국영상자료원 KMDb posters(KMDB_KEY)
// - 결과는 제목 기준으로 sys/art_<해시>에 캐시한다(찾음 7일, 못 찾음 1일). 코스가 바뀌어 제목이 달라지면 새로 찾는다.
//   카카오는 저장한 검색 결과를 버퍼로만 쓰고 주기적으로 새로 받으라고 안내하므로 7일마다 다시 확인한다.
// - 이미지는 서버가 내려받지 않고 주소만 앱에 준다(앱이 원래 주소에서 바로 불러옴).
import { env, fail, sha256hex } from './lib.ts';
import { nl, pick, toBook, type BookIO } from './books.ts';

const DAY = 86_400_000;
const DAILY = () => Number(env('ART_DAILY_LIMIT', '300'));
const clean = (s: unknown, n: number) => String(s ?? '').replace(/\s+/g, ' ').trim().slice(0, n);
export const normT = (s: unknown) => String(s ?? '').replace(/<[^>]*>|!H[SE]/g, '').replace(/\(.*?\)|\[.*?\]/g, '').replace(/[^0-9A-Za-z가-힣]/g, '').toLowerCase();
const https = (u: unknown) => { const s = clean(u, 400); return /^https?:\/\//.test(s) ? s.replace(/^http:/, 'https:') : ''; };
/* 카카오 thumbnail은 120×174라 큰 화면에서 흐리다: 주소 안의 원본(다음 책 이미지, 보통 400px 넘음)을 https로 쓴다. 다음 이미지 주소가 아니면 그대로 */
export const bigCover = (u: string) => { const m = /[?&]fname=([^&]+)/.exec(u); if (!m) return u; let f = ''; try { f = decodeURIComponent(m[1]); } catch { return u; }
  return /^https?:\/\/[a-z0-9.-]*daumcdn\.net\//i.test(f) ? f.replace(/^http:/, 'https:') : u; };

type Art = { url: string; src: string; title?: string };

async function getJSON(url: string, headers: Record<string, string> = {}) {
  try {
    const r = await fetch(url, { headers, signal: AbortSignal.timeout(7000) });
    if (!r.ok) { console.log('art http', r.status, url.split('?')[0]); return null; }
    return await r.json().catch(() => null);
  } catch (e) { console.log('art fetch', String(e).slice(0, 120)); return null; }
}

/* ---------- 책 ---------- */
async function kakaoBook(title: string, author: string): Promise<Art | null> {
  const key = env('KAKAO_REST_KEY'); if (!key) return null;
  const q = new URLSearchParams({ query: title, target: 'title', size: '10' });
  const j = await getJSON('https://dapi.kakao.com/v3/search/book?' + q, { Authorization: 'KakaoAK ' + key }) as { documents?: Record<string, unknown>[] } | null;
  const docs = j?.documents ?? [];
  const t = normT(title), a = normT(author);
  let best: Record<string, unknown> | null = null, bs = -1;
  for (const d of docs) {
    if (normT(d.title) !== t || !https(d.thumbnail)) continue;
    let s = 1; const au = normT((d.authors as string[] | undefined)?.join(''));
    if (a && au.includes(a)) s += 2;
    if (s > bs) { bs = s; best = d; }
  }
  return best ? { url: bigCover(https(best.thumbnail)), src: 'kakao', title: clean(best.title, 120) } : null;
}
export async function bookArt(title: string, author: string): Promise<Art | null> {
  if (env('NL_CERT_KEY') || env('FAKE_NL')) {
    try {
      let d = await nl({ title }); let b = pick(d, title, author);
      if (!b && author) { d = await nl({ title, author }); b = pick(d, title, author); }
      const bk = b ? toBook(b) : null;
      if (bk?.cover) return { url: bk.cover, src: 'nl', title: bk.title };
    } catch { /* 국립중앙도서관이 안 되면 카카오로 */ }
  }
  return kakaoBook(title, author);
}

/* ---------- 영화 ---------- */
async function tmdb(title: string, year: string): Promise<Art | null> {
  const tok = env('TMDB_TOKEN'); if (!tok) return null;
  const q = new URLSearchParams({ query: title, language: 'ko-KR', region: 'KR', include_adult: 'false' });
  const j = await getJSON('https://api.themoviedb.org/3/search/movie?' + q, { Authorization: 'Bearer ' + tok, accept: 'application/json' }) as { results?: Record<string, unknown>[] } | null;
  const t = normT(title);
  let best: Record<string, unknown> | null = null, bs = -1;
  for (const m of j?.results ?? []) {
    if (!m.poster_path) continue;
    const same = normT(m.title) === t || normT(m.original_title) === t;
    const y = String(m.release_date ?? '').slice(0, 4);
    let s = same ? 10 : normT(m.title).includes(t) ? 3 : -1;
    if (s < 0) continue;
    if (year && y === year) s += 5; else if (year && y && Math.abs(+y - +year) <= 1) s += 2;
    s += Math.min(2, Number(m.popularity ?? 0) / 50);
    if (s > bs) { bs = s; best = m; }
  }
  return best ? { url: 'https://image.tmdb.org/t/p/w342' + best.poster_path, src: 'tmdb', title: clean(best.title, 120) } : null;
}
async function kmdb(title: string, year: string): Promise<Art | null> {
  const key = env('KMDB_KEY'); if (!key) return null;
  const q = new URLSearchParams({ collection: 'kmdb_new2', detail: 'Y', ServiceKey: key, title, listCount: '10' });
  const j = await getJSON('http://api.koreafilm.or.kr/openapi-data2/wisenut/search_api/search_json2.jsp?' + q) as { Data?: { Result?: Record<string, unknown>[] }[] } | null;
  const t = normT(title);
  for (const m of j?.Data?.[0]?.Result ?? []) {
    if (normT(m.title) !== t) continue;
    if (year && m.prodYear && Math.abs(Number(m.prodYear) - Number(year)) > 1) continue;
    const p = String(m.posters ?? '').split('|').map(https).find(Boolean);
    if (p) return { url: p, src: 'kmdb', title: clean(String(m.title).replace(/!H[SE]/g, ''), 120) };
  }
  return null;
}
export async function movieArt(title: string, year: string): Promise<Art | null> {
  return (await tmdb(title, year)) ?? (await kmdb(title, year));
}

/* ---------- op ---------- */
export async function artOp(uid: string, b: Record<string, unknown>, io: BookIO) {
  const kind = b.kind === 'movie' ? 'movie' : 'book';
  const title = clean(b.title, 80).replace(/\s*\(.*\)\s*$/, ''), au = clean(b.author, 40), year = /^\d{4}$/.test(String(b.year ?? '')) ? String(b.year) : '';
  if (normT(title).length < 1) fail('bad_request', '제목이 필요해요.');
  const fake = env('FAKE_ART');
  if (!fake && !(kind === 'book' ? env('NL_CERT_KEY') || env('KAKAO_REST_KEY') : env('TMDB_TOKEN') || env('KMDB_KEY')))
    fail('art_not_configured', '표지·포스터 자동 찾기가 아직 설정되지 않았어요.', 503);
  const p = `sys/art_${(await sha256hex(kind + '|' + normT(title) + '|' + year)).slice(0, 24)}`;
  const row = await io.read(p);
  if (row) {
    const at = Number(row.data.at) || 0, ok = !!row.data.url;
    if (Date.now() - at < (ok ? 7 : 1) * DAY) return { url: String(row.data.url || ''), src: String(row.data.src || ''), cached: true };
  }
  // 회원당 하루 조회 수 (캐시로 답한 것은 세지 않음)
  const qp = `sys/artuse_${uid}`; const qr = await io.read(qp);
  const day = new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);
  const n = qr && qr.data.day === day ? Number(qr.data.n) || 0 : 0;
  if (n >= DAILY()) fail('rate_limited', '오늘 표지·포스터 찾기를 다 썼어요. 내일 다시 찾아요.', 429);
  await io.write(qp, { day, n: n + 1 }, null, qr);
  let art: Art | null = null;
  if (fake) { // 시험용: {"book:제목": "https://…", "movie:제목": "https://…"}
    const m = JSON.parse(fake) as Record<string, string>; const u = m[kind + ':' + title];
    art = u ? { url: u, src: 'fake' } : null;
  } else art = kind === 'book' ? await bookArt(title, au) : await movieArt(title, year);
  await io.write(p, { url: art?.url ?? '', src: art?.src ?? '', kind, title, at: Date.now() }, null, row);
  return { url: art?.url ?? '', src: art?.src ?? '', cached: false };
}

/* ---------- 비전보드 공개 사진 (서버 op: media.pics, 2026-11-26) ----------
   학생이 사진을 올리지 않은 꿈 칸에 어울리는 공개 사진을 붙인다. Openverse(api.openverse.org, 키 없음)에서
   상업 이용 가능한 CC 라이선스(cc0·pdm·by·by-sa)만, 성인물 제외(mature=false)로 찾고 썸네일 주소와 출처(작가·라이선스)를 돌려준다.
   검색어는 앱이 AI로 만든 영어 2~3단어(사물·장소 위주). 검색어 기준 30일 캐시, 회원당 하루 60번. */
export async function picsOp(uid: string, b: Record<string, unknown>, io: BookIO) {
  const q = clean(b.q, 60).replace(/[^A-Za-z0-9 \-]/g, '').trim().toLowerCase();
  if (q.length < 2) fail('bad_request', '검색어가 필요해요.');
  const p = `sys/pic_${(await sha256hex('v1|' + q)).slice(0, 24)}`;
  const row = await io.read(p);
  if (row && Date.now() - (Number(row.data.at) || 0) < 30 * DAY) return { pics: row.data.pics || [], cached: true };
  const qp = `sys/picuse_${uid}`; const qr = await io.read(qp);
  const day = new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);
  const n = qr && qr.data.day === day ? Number(qr.data.n) || 0 : 0;
  if (n >= Number(env('PIC_DAILY_LIMIT', '60'))) fail('rate_limited', '오늘 사진 찾기를 다 썼어요. 내일 다시 찾아요.', 429);
  await io.write(qp, { day, n: n + 1 }, null, qr);
  let pics: { u: string; by: string; lic: string; src: string }[] = [];
  const fake = env('FAKE_PICS');
  if (fake) { const m = JSON.parse(fake) as Record<string, string>; const u = m[q] || m['*']; if (u) pics = [{ u, by: 'test', lic: 'CC0', src: '' }]; }
  else {
    const j = await getJSON(`https://api.openverse.org/v1/images/?q=${encodeURIComponent(q)}&license=cc0,pdm,by,by-sa&mature=false&page_size=6&aspect_ratio=square,wide`);
    const rs = Array.isArray(j?.results) ? j.results : [];
    pics = rs.map((r: Record<string, unknown>) => ({ u: https(r.thumbnail) || https(r.url), by: clean(r.creator, 40) || '알 수 없음', lic: (clean(r.license, 10).toUpperCase() + ' ' + clean(r.license_version, 6)).trim(), src: https(r.foreign_landing_url) }))
      .filter((x: { u: string }) => x.u).slice(0, 3);
  }
  await io.write(p, { q, pics, at: Date.now() }, null, row);
  return { pics, cached: false };
}
