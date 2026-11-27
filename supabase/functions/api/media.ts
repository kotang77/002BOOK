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

/* 11-28: 외부 API가 실패(한도 초과·시간 초과·오류 응답)하면 '못 찾음'으로 하루 동안 캐시하던 것을 고친다.
   실패는 ER.n에 세어 두고, 실패가 있었던 '못 찾음'은 30분만 기억해 곧 다시 찾게 한다 */
const ER = { n: 0 };
async function getJSON(url: string, headers: Record<string, string> = {}) {
  try {
    const r = await fetch(url, { headers, signal: AbortSignal.timeout(7000) });
    if (!r.ok) { ER.n++; console.log('art http', r.status, url.split('?')[0]); return null; }
    const j = await r.json().catch(() => null);
    if (j === null) ER.n++;
    // KMDb는 한도 초과도 200으로 주고 본문에 오류를 적는다
    else if (/koreafilm/.test(url) && !(j as { Data?: unknown }).Data) { ER.n++; console.log('art kmdb err', JSON.stringify(j).slice(0, 160)); }
    return j;
  } catch (e) { ER.n++; console.log('art fetch', String(e).slice(0, 120)); return null; }
}

/* ---------- 책 ---------- */
async function kakaoBook(title: string, author: string): Promise<Art | null> {
  const key = env('KAKAO_REST_KEY'); if (!key) return null;
  const q = new URLSearchParams({ query: title, target: 'title', size: '10' });
  const j = await getJSON('https://dapi.kakao.com/v3/search/book?' + q, { Authorization: 'KakaoAK ' + key }) as { documents?: Record<string, unknown>[] } | null;
  const docs = j?.documents ?? [];
  const t = normT(title), a = normT(author);
  let best: Record<string, unknown> | null = null, bs = -1;
  /* 11-28: 서점 등록 제목이 앱 제목과 조금 다른 책(사피엔스 그래픽 히스토리 Vol.1 등)은 한쪽 제목이 다른 쪽을 포함하고 저자가 같으면 받는다 */
  for (const d of docs) {
    if (!https(d.thumbnail)) continue;
    const dt = normT(d.title), au = normT((d.authors as string[] | undefined)?.join(''));
    const same = dt === t, near = !same && t.length >= 2 && dt.length >= 2 && (dt.includes(t) || t.includes(dt)) && !!a && au.includes(a);
    if (!same && !near) continue;
    let s = same ? 3 : 1;
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
  const r = await kakaoBook(title, author);
  if (r) return r;
  for (const t of BOOK_AKA[normT(title)] ?? []) { const a = await kakaoBook(t, author); if (a) return a; }
  return null;
}
/* 서점에 앱 제목 그대로는 없는 책: 다른 이름으로 한 번 더(저자가 같아야 받음) */
const BOOK_AKA: Record<string, string[]> = { '청소년을위한월든': ['월든'], '사피엔스그래픽히스토리1인류의탄생': ['사피엔스 그래픽 히스토리'], '사피엔스그래픽히스토리vol1': ['사피엔스 그래픽 히스토리'] };

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
  /* 11-27: 같은 이름 속편이 많은 영화(터미네이터 등)는 원작이 앞 10개에 안 들어 못 찾았다 → 30개까지 받고, 연도를 알면 제작연도 ±1로 좁힌다.
     정확히 같은 제목이 없으면 한쪽 제목이 다른 쪽을 포함하는 것(루디 ↔ 루디 이야기)도 연도가 맞으면 받는다. 포스터가 없는 항목은 건너뛴다.
     시리즈 영화는 1편 기준(사용자 지시): 연도를 모르면 같은 제목·포함 제목 가운데 가장 먼저 나온 것 */
  const q = new URLSearchParams({ collection: 'kmdb_new2', detail: 'Y', ServiceKey: key, title, listCount: '30' });
  if (year) { q.set('createDts', String(+year - 1)); q.set('createDte', String(+year + 1)); }
  const j = await getJSON('http://api.koreafilm.or.kr/openapi-data2/wisenut/search_api/search_json2.jsp?' + q) as { Data?: { Result?: Record<string, unknown>[] }[] } | null;
  const t = normT(title);
  const rows = (j?.Data?.[0]?.Result ?? []).map((m) => ({ m, n: normT(m.title), y: Number(m.prodYear) || 0, p: String(m.posters ?? '').split('|').map(https).find(Boolean) || '' }))
    .filter((r) => r.p && !(year && r.y && Math.abs(r.y - Number(year)) > 1));
  const pick = rows.filter((r) => r.n === t).sort((a, b) => (a.y || 9999) - (b.y || 9999))[0]
    ?? (t.length >= 2 ? rows.filter((r) => r.n.length >= 2 && (r.n.includes(t) || t.includes(r.n)) && (year ? !!r.y : true)).sort((a, b) => (a.y || 9999) - (b.y || 9999) || Math.abs(a.n.length - t.length) - Math.abs(b.n.length - t.length))[0] : undefined);
  return pick ? { url: pick.p, src: 'kmdb', title: clean(String(pick.m.title).replace(/!H[SE]/g, ''), 120) } : null;
}
/* 영상자료원에 등록된 이름이 앱 제목과 다른 영화(루디 이야기 → 루디 등)는 다른 이름으로 한 번 더 찾는다 */
const MOVIE_AKA: Record<string, string[]> = { '알파위대한여정': ['알파'], '루디이야기': ['루디'],
  '바람을길들인풍차소년': ['바람을 길들인 풍차 소년', 'The Boy Who Harnessed the Wind'] };
export async function movieArt(title: string, year: string): Promise<Art | null> {
  const r = (await tmdb(title, year)) ?? (await kmdb(title, year));
  if (r) return r;
  for (const t of MOVIE_AKA[normT(title)] ?? []) { const a = (await tmdb(t, year)) ?? (await kmdb(t, year)); if (a) return a; }
  return null;
}

/* ---------- op ---------- */
export async function artOp(uid: string, b: Record<string, unknown>, io: BookIO, admin = false) {
  const kind = b.kind === 'movie' ? 'movie' : 'book';
  const title = clean(b.title, 80).replace(/\s*\(.*\)\s*$/, ''), au = clean(b.author, 40), year = /^\d{4}$/.test(String(b.year ?? '')) ? String(b.year) : '';
  if (normT(title).length < 1) fail('bad_request', '제목이 필요해요.');
  const fake = env('FAKE_ART');
  if (!fake && !(kind === 'book' ? env('NL_CERT_KEY') || env('KAKAO_REST_KEY') : env('TMDB_TOKEN') || env('KMDB_KEY')))
    fail('art_not_configured', '표지·포스터 자동 찾기가 아직 설정되지 않았어요.', 503);
  const p = `sys/art_${(await sha256hex(kind + '|' + normT(title) + '|' + year)).slice(0, 24)}`;
  const row = await io.read(p);
  if (row && !(admin && b.fresh && !row.data.url)) { // 관리자는 '못 찾음' 캐시를 건너뛰고 다시 찾을 수 있다
    const at = Number(row.data.at) || 0, ok = !!row.data.url, ttl = ok ? 7 * DAY : row.data.err ? 30 * 60e3 : DAY;
    if (Date.now() - at < ttl) return { url: String(row.data.url || ''), src: String(row.data.src || ''), title: String(row.data.found || ''), cached: true };
  }
  // 회원당 하루 조회 수 (캐시로 답한 것은 세지 않음)
  const qp = `sys/artuse_${uid}`; const qr = await io.read(qp);
  const day = new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);
  const n = qr && qr.data.day === day ? Number(qr.data.n) || 0 : 0;
  if (n >= DAILY()) fail('rate_limited', '오늘 표지·포스터 찾기를 다 썼어요. 내일 다시 찾아요.', 429);
  await io.write(qp, { day, n: n + 1 }, null, qr);
  let art: Art | null = null; const e0 = ER.n;
  if (fake) { // 시험용: {"book:제목": "https://…", "movie:제목": "https://…"}
    const m = JSON.parse(fake) as Record<string, string>; const u = m[kind + ':' + title];
    art = u ? { url: u, src: 'fake' } : null;
  } else art = kind === 'book' ? await bookArt(title, au) : await movieArt(title, year);
  const err = !art && ER.n > e0;
  await io.write(p, { url: art?.url ?? '', src: art?.src ?? '', found: art?.title ?? '', kind, title, year, at: Date.now(), ...(err ? { err: 1 } : {}) }, null, row);
  return { url: art?.url ?? '', src: art?.src ?? '', title: art?.title ?? '', cached: false };
}

/* ---------- 비전보드 공개 사진 (서버 op: media.pics, 2026-11-26) ----------
   학생이 사진을 올리지 않은 꿈 칸에 어울리는 공개 사진을 붙인다. Openverse(api.openverse.org, 키 없음)에서
   상업 이용 가능한 CC 라이선스(cc0·pdm·by·by-sa)만, 성인물 제외(mature=false)로 찾고 썸네일 주소와 출처(작가·라이선스)를 돌려준다.
   검색어는 앱이 AI로 만든 영어 2~3단어(사물·장소 위주). 검색어 기준 30일 캐시, 회원당 하루 60번. */
export async function picsOp(uid: string, b: Record<string, unknown>, io: BookIO) {
  const q = clean(b.q, 60).replace(/[^A-Za-z0-9 \-]/g, '').trim().toLowerCase();
  if (q.length < 2) fail('bad_request', '검색어가 필요해요.');
  const p = `sys/pic_${(await sha256hex('v2|' + q)).slice(0, 24)}`;
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
    // 1) Openverse (User-Agent가 없으면 거절되는 일이 있어 이름을 밝힌다)  2) 결과가 없거나 실패하면 위키미디어 공용(자유 라이선스만 실림)
    const UA = { 'User-Agent': '002BOOK/1.0 (https://002book.com; help@002book.com)', 'Accept': 'application/json' };
    const j = await getJSON(`https://api.openverse.org/v1/images/?q=${encodeURIComponent(q)}&license=cc0,pdm,by,by-sa&mature=false&page_size=6&aspect_ratio=square,wide`, UA);
    const rs = Array.isArray(j?.results) ? j.results : [];
    pics = rs.map((r: Record<string, unknown>) => ({ u: https(r.thumbnail) || https(r.url), by: clean(r.creator, 40) || '알 수 없음', lic: (clean(r.license, 10).toUpperCase() + ' ' + clean(r.license_version, 6)).trim(), src: https(r.foreign_landing_url) }))
      .filter((x: { u: string }) => x.u).slice(0, 3);
    if (!pics.length) {
      const w = await getJSON(`https://commons.wikimedia.org/w/api.php?action=query&format=json&generator=search&gsrnamespace=6&gsrlimit=8&gsrsearch=${encodeURIComponent('filetype:bitmap ' + q)}&prop=imageinfo&iiprop=url|extmetadata&iiurlwidth=640`, UA);
      const pg = Object.values((w?.query?.pages ?? {}) as Record<string, Record<string, unknown>>);
      const strip = (h: unknown) => clean(String(h ?? '').replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' '), 40);
      pics = pg.map(x => { const ii = (Array.isArray(x.imageinfo) ? x.imageinfo[0] : {}) as Record<string, unknown>; const em = (ii.extmetadata ?? {}) as Record<string, { value?: unknown }>;
        return { u: https(ii.thumburl), by: strip(em.Artist?.value) || '알 수 없음', lic: strip(em.LicenseShortName?.value), src: https(ii.descriptionurl) }; })
        .filter(x => x.u && /\.(jpe?g|png|webp)$/i.test(x.u.split('?')[0]) && /^(cc0|cc[ -]by|public domain|pd)/i.test(x.lic)).slice(0, 3);
    }
  }
  if (!pics.length) return { pics, cached: false };   // 못 찾은 결과는 기억하지 않는다(다음에 다시 찾음)
  await io.write(p, { q, pics, at: Date.now() }, null, row);
  return { pics, cached: false };
}
