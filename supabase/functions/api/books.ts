// 도서 서지 조회: 국립중앙도서관 ISBN 서지정보 Open API (https://www.nl.go.kr/seoji/SearchApi.do)
// - 인증키는 서버 비밀값 NL_CERT_KEY 에만 둔다. 앱은 book.isbn / book.find 로만 묻는다.
// - 한국십진분류(KDC)와 ISBN 부가기호로 육각형 독서 분야, 만화·학습참고서 여부, 대상 독자를 정한다.
// - 결과는 sys/ 아래에 캐시한다(회원은 읽지 못함). 회원당 하루 조회 수를 제한한다.
import { env, fail, sha256hex } from './lib.ts';

type Row = { path: string; data: Record<string, unknown>; owner: string | null; version: number };
export type BookIO = {
  read: (p: string) => Promise<Row | null>;
  write: (p: string, d: Record<string, unknown>, owner: string | null, prev: Row | null) => Promise<unknown>;
};

const DAILY = () => Number(env('BOOK_DAILY_LIMIT', '200'));
const DAY = 86_400_000;

/** ISBN-10/13을 검사해 13자리로 바꾼다. 틀리면 null */
export function isbn13(v: unknown): string | null {
  const s = String(v ?? '').toUpperCase().replace(/[^0-9X]/g, '');
  if (s.length === 10) {
    let t = 0;
    for (let i = 0; i < 10; i++) { const c = s[i] === 'X' ? (i === 9 ? 10 : NaN) : Number(s[i]); if (Number.isNaN(c)) return null; t += c * (10 - i); }
    if (t % 11) return null;
    const b = '978' + s.slice(0, 9);
    return b + check13(b);
  }
  if (s.length === 13 && /^\d{13}$/.test(s) && /^97[89]/.test(s)) return check13(s.slice(0, 12)) === s[12] ? s : null;
  return null;
}
const check13 = (b: string) => String((10 - ([...b].reduce((a, c, i) => a + Number(c) * (i % 2 ? 3 : 1), 0) % 10)) % 10);

/* 분야 번호: 0 문학, 1 인문·사상, 2 사회·경제, 3 역사·지리, 4 과학·기술, 5 예술·언어 (-1 미정)
   KDC 주류 → 분야. 총류(0)는 컴퓨터(004·005)만 과학·기술, 건축(540)은 예술·언어로 본다 */
const MAIN: Record<string, number> = { '0': -1, '1': 1, '2': 1, '3': 2, '4': 4, '5': 4, '6': 5, '7': 5, '8': 0, '9': 3 };
export function kdcAx(kdc: unknown): number {
  const m = String(kdc ?? '').trim().match(/^(\d)(\d)?(\d)?/);
  if (!m) return -1;
  const d3 = m[0];
  if (/^00[45]/.test(d3)) return 4;
  if (/^54/.test(d3)) return 5;
  return MAIN[m[1]] ?? -1;
}
/** ISBN 부가기호(5자리): 독자 대상 · 발행 형태 · 내용 분류 */
export function addInfo(code: unknown) {
  const c = String(code ?? '').replace(/\D/g, '');
  if (c.length !== 5) return null;
  const reader = c[0], form = c[1];
  return {
    reader, form, ax: MAIN[c[2]] ?? -1,
    ref: reader === '5' || reader === '6',   // 학습참고서
    comic: form === '7',                      // 그림책·만화
    kid: reader === '7',                      // 아동
    teen: reader === '4',                     // 청소년
  };
}
const clean = (s: unknown, n: number) => String(s ?? '').replace(/\s+/g, ' ').trim().slice(0, n);
const author = (s: unknown) => clean(String(s ?? '').replace(/(지은이|글|저자|지음|옮긴이|옮김|그림|엮은이|저|역|공저)\s*[:：]?/g, ' ').split(/[;,]/)[0], 40);
const norm = (s: unknown) => String(s ?? '').replace(/\(.*?\)|\[.*?\]/g, '').replace(/[^0-9A-Za-z가-힣]/g, '').toLowerCase();

/** 국립중앙도서관 응답 한 건 → 앱이 쓰는 모양 */
export function toBook(d: Record<string, unknown>) {
  const kdc = clean(d.KDC, 20), add = clean(d.EA_ADD_CODE, 10), ai = addInfo(add);
  let main = kdcAx(kdc), from = 'kdc';
  if (main < 0 && ai && ai.ax >= 0) { main = ai.ax; from = 'add'; }
  if (main < 0) from = '';
  const cover = clean(d.TITLE_URL, 300);
  return {
    isbn: isbn13(d.EA_ISBN) ?? clean(d.EA_ISBN, 20), title: clean(d.TITLE, 120), author: author(d.AUTHOR), publisher: clean(d.PUBLISHER, 60),
    kdc, add, main, from, nc: ai ? (ai.comic ? '그림책·만화' : ai.ref ? '학습참고서' : '') : '', kid: !!ai?.kid, teen: !!ai?.teen,
    cover: /^https?:\/\//.test(cover) ? cover.replace(/^http:/, 'https:') : '', src: 'nl',
  };
}
export type Book = ReturnType<typeof toBook>;

export async function nl(params: Record<string, string>): Promise<Record<string, unknown>[]> {
  const fake = env('FAKE_NL');
  if (fake) { // 시험용: {"isbn:978…": 응답 한 건, "title:책 제목": [여러 건]}
    const m = JSON.parse(fake) as Record<string, unknown>;
    const v = params.isbn ? m['isbn:' + params.isbn] : m['title:' + params.title];
    return Array.isArray(v) ? v as Record<string, unknown>[] : v ? [v as Record<string, unknown>] : [];
  }
  const key = env('NL_CERT_KEY');
  if (!key) fail('isbn_not_configured', '도서 정보 조회가 아직 설정되지 않았어요.', 503);
  const q = new URLSearchParams({ cert_key: key, result_style: 'json', page_no: '1', page_size: params.isbn ? '3' : '10', ...params });
  let r: Response;
  try { r = await fetch('https://www.nl.go.kr/seoji/SearchApi.do?' + q, { signal: AbortSignal.timeout(7000) }); }
  catch { fail('isbn_unavailable', '국립중앙도서관 서지 조회가 응답하지 않아요. 잠시 뒤 다시 해 주세요.', 502); }
  if (!r!.ok) fail('isbn_unavailable', '국립중앙도서관 서지 조회에 실패했어요.', 502, r!.status);
  const j = await r!.json().catch(() => null) as Record<string, unknown> | null;
  if (!j) fail('isbn_unavailable', '국립중앙도서관 서지 조회 결과를 읽지 못했어요.', 502);
  if (j!.RESULT || j!.ERR_CODE || j!.result) console.log('nl error', JSON.stringify(j).slice(0, 300));
  const docs = (Array.isArray(j!.docs) ? j!.docs : Array.isArray(j!.result) ? j!.result : []) as Record<string, unknown>[];
  return docs;
}

/** 같은 책 고르기: 제목(괄호·띄어쓰기·문장부호 무시)이 같은 것, 저자가 맞는 것, 분류가 있는 것, 전자책이 아닌 것 순 */
export function pick(docs: Record<string, unknown>[], title: string, au = '') {
  const t = norm(title), a = norm(au);
  const sc = (d: Record<string, unknown>) => {
    const dt = norm(d.TITLE); if (!dt) return -1;
    let s = dt === t ? 10 : -1;   // 본표제가 같은 책만(부제·해설서·다른 책을 잘못 고르지 않도록)
    if (s < 0) return -1;
    if (a && norm(d.AUTHOR).includes(a)) s += 5;
    if (String(d.KDC ?? '').trim()) s += 2;
    if (String(d.EA_ADD_CODE ?? '').trim()) s += 1;
    if (String(d.EBOOK_YN ?? '') === 'Y') s -= 1;
    return s;
  };
  let best: Record<string, unknown> | null = null, bs = -1;
  for (const d of docs) { const s = sc(d); if (s > bs) { bs = s; best = d; } }
  return best;
}

async function quota(io: BookIO, uid: string) {
  const p = `sys/bkuse_${uid}`; const row = await io.read(p);
  const day = new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);
  const n = row && row.data.day === day ? Number(row.data.n) || 0 : 0;
  if (n >= DAILY()) fail('rate_limited', `오늘 도서 정보 조회(${DAILY()}회)를 다 썼어요. 내일 다시 해 주세요.`, 429);
  await io.write(p, { day, n: n + 1 }, null, row);
}
async function cached(io: BookIO, p: string, uid: string, get: () => Promise<Book | null>) {
  const row = await io.read(p);
  if (row) { const at = Number(row.data.at) || 0; const ttl = row.data.book ? 30 * DAY : DAY; if (Date.now() - at < ttl) return { book: (row.data.book as Book) ?? null, cached: true }; }
  await quota(io, uid);
  const book = await get();
  await io.write(p, { book, at: Date.now() }, null, row);
  return { book, cached: false };
}

export async function bookOp(op: string, uid: string, b: Record<string, unknown>, io: BookIO) {
  if (op === 'book.isbn') {
    const i = isbn13(b.isbn);
    if (!i) fail('bad_isbn', 'ISBN이 올바르지 않아요. 바코드 아래 13자리 숫자를 확인해 주세요.');
    return cached(io, `sys/isbn_${i}`, uid, async () => { const d = await nl({ isbn: i! }); return d.length ? toBook(d.find((x) => isbn13(x.EA_ISBN) === i) ?? d[0]) : null; });
  }
  if (op === 'book.find') {
    const title = clean(b.title, 80).replace(/\s*\(.*\)\s*$/, ''), au = clean(b.author, 40);
    if (norm(title).length < 2) fail('bad_request', '책 제목을 두 글자 이상 적어 주세요.');
    const key = (await sha256hex(norm(title) + '|' + norm(au))).slice(0, 24);
    return cached(io, `sys/bkt_${key}`, uid, async () => {
      let d = await nl({ title });
      let best = pick(d, title, au);
      if (!best && au) { d = await nl({ title, author: au }); best = pick(d, title, au); }
      return best ? toBook(best) : null;
    });
  }
  fail('bad_op', '알 수 없는 요청이에요.');
}
