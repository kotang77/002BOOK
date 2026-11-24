// 빌드: app/source.html + web/ → dist/
//   node scripts/build.mjs
// 환경 변수(또는 site.config.json): SUPABASE_URL, SUPABASE_ANON_KEY
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import * as acorn from 'acorn';

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const DIST = path.join(ROOT, 'dist');
const cfgFile = path.join(ROOT, 'site.config.json');
const cfg = fs.existsSync(cfgFile) ? JSON.parse(fs.readFileSync(cfgFile, 'utf8')) : {};
const SUPA = process.env.SUPABASE_URL || cfg.supabaseUrl || '';
const ANON = process.env.SUPABASE_ANON_KEY || cfg.supabaseAnonKey || '';
const errors = [];

let html = fs.readFileSync(path.join(ROOT, 'app/source.html'), 'utf8');

/* ---------- 1) 메인 스크립트 찾기 ---------- */
function mainScript(h) {
  const re = /<script>([\s\S]*?)<\/script>/g; let m;
  while ((m = re.exec(h))) if (m[1].includes('(async function(){') && m[1].includes('function doLogin')) return { start: m.index + 8, end: m.index + 8 + m[1].length, code: m[1] };
  throw new Error('메인 스크립트를 찾지 못했어요');
}

/* ---------- 2) 원본 문법 확인 ---------- */
// (2026-11-21) 예전에는 Claude 게시본을 002book.com용으로 바꾸는 패치 30개를 여기서 적용했다. 지금은 app/source.html이 유일한 원본이다.
const FREE = process.env.FREE_LAUNCH ? process.env.FREE_LAUNCH === '1' : cfg.freeLaunch !== false; // 무료 출시 모드(기본 켜짐)
const biz = cfg.business || {};
// 전자상거래법 제10조·제13조: 상호, 대표자, 주소, 전화, 이메일, 사업자등록번호, 통신판매업 신고번호, 호스팅 제공자, 이용약관 연결
const bizLine = [biz.name && `상호 ${biz.name}`, biz.owner && `대표 ${biz.owner}`, biz.address && `주소 ${biz.address}`, biz.phone && `전화 ${biz.phone}`, biz.email && `이메일 ${biz.email}`,
  biz.regNo && `사업자등록번호 ${biz.regNo}` + (biz.regNo ? ` <a href="https://www.ftc.go.kr/bizCommPop.do?wrkr_no=${biz.regNo.replace(/\D/g, '')}" target="_blank" rel="noopener" style="color:inherit">[사업자정보 확인]</a>` : ''),
  biz.mailOrderNo && `통신판매업 신고 ${biz.mailOrderNo}${biz.mailOrderAgency ? ' (' + biz.mailOrderAgency + ')' : ''}`,
  `호스팅 제공 GitHub, Inc. · Supabase, Inc.`].filter(Boolean).join(' · ');
const opLine = FREE && !biz.name ? [biz.brand ? `서비스 운영자 ${biz.brand}` : '서비스 운영자 개인 운영 (무료 제공 · 사업자 등록 전)', (biz.email || biz.privacyEmail) && `문의 ${biz.email || biz.privacyEmail}`, '호스팅 제공 GitHub, Inc. · Supabase, Inc.'].filter(Boolean).join(' · ') : bizLine;
const missing = ['name', 'owner', 'address', 'phone', 'email', 'regNo', 'mailOrderNo'].filter((k) => !biz[k]);
if (missing.length && !FREE) console.warn('⚠ site.config.json 사업자 정보 비어 있음 (전자상거래법 표시 의무): ' + missing.join(', '));

/* ---------- 3) 남은 위험 패턴 검사 ---------- */
const main2 = mainScript(html).code;
for (const bad of ['sha(S.me.salt', "sha(d.salt+pw)", 'up.pw=', 'salt,pw:await sha']) if (main2.includes(bad)) errors.push(`비밀번호를 브라우저에서 다루는 코드가 남아 있음: ${bad}`);
try { acorn.parse(main2, { ecmaVersion: 'latest', allowAwaitOutsideFunction: true, allowReturnOutsideFunction: true }); }
catch (e) { errors.push('패치 후 문법 오류: ' + e.message); }

if (errors.length) { console.error('\n빌드 실패:\n - ' + errors.join('\n - ')); process.exit(1); }

/* ---------- 5) dist 만들기 ---------- */
fs.rmSync(DIST, { recursive: true, force: true });
fs.cpSync(path.join(ROOT, 'web'), DIST, { recursive: true });
// 아이콘 생성(6단계)에 쓸 로고 원본을 먼저 꺼내 둔다
const m = html.match(/LOGO_ICON='data:image\/png;base64,([A-Za-z0-9+/=]+)'/);
const m2 = html.match(/LOGO_FULL='data:image\/png;base64,([A-Za-z0-9+/=]+)'/);
// 앱 안에 글자로 들어 있는 큰 그림(로고·캐릭터)을 별도 파일로 꺼낸다. 이름에 내용 해시를 넣어 브라우저가 오래 저장해도 안전하다
{
  const dir = path.join(DIST, 'img'); fs.mkdirSync(dir, { recursive: true });
  let n = 0, saved = 0;
  html = html.replace(/data:image\/(png|jpeg|webp);base64,([A-Za-z0-9+/=]{4000,})/g, (all, ext, b64) => {
    const buf = Buffer.from(b64, 'base64');
    const name = crypto.createHash('sha256').update(buf).digest('hex').slice(0, 12) + '.' + (ext === 'jpeg' ? 'jpg' : ext);
    fs.writeFileSync(path.join(dir, name), buf); n++; saved += all.length - ('/img/' + name).length;
    return '/img/' + name;
  });
  console.log(`내장 그림 ${n}개를 파일로 분리 (HTML ${Math.round(saved / 1024)}KB 줄임)`);
}
fs.writeFileSync(path.join(DIST, 'index.html'), html);
fs.writeFileSync(path.join(DIST, '404.html'), html);
fs.writeFileSync(path.join(DIST, 'runtime/config.js'),
  `window.__002CFG=${JSON.stringify({ api: SUPA ? SUPA.replace(/\/$/, '') + '/functions/v1/api' : '', anon: ANON, toss: cfg.tossClientKey || '', free: FREE, google: process.env.GOOGLE_CLIENT_ID || cfg.googleClientId || '' })};\n`);
const brandIcon = path.join(ROOT, 'web/brand/app-icon.png'); // 아이콘이 바뀌어도 서비스 워커 캐시가 새로 만들어지게 빌드 번호에 넣는다
const buildId = crypto.createHash('sha256').update(html + fs.readFileSync(path.join(ROOT, 'web/runtime/claude-shim.js'))).update(fs.existsSync(brandIcon) ? fs.readFileSync(brandIcon) : '').digest('hex').slice(0, 10);
const sw = path.join(DIST, 'sw.js'); fs.writeFileSync(sw, fs.readFileSync(sw, 'utf8').replace('__BUILD_ID__', buildId));
// 아이콘·매니페스트 주소에 빌드 번호를 붙여, 휴대폰 크롬이 예전 아이콘을 캐시에서 다시 쓰지 않게 한다
{ const mf = path.join(DIST, 'manifest.webmanifest');
  if (fs.existsSync(mf)) fs.writeFileSync(mf, fs.readFileSync(mf, 'utf8').replace(/"src": "(\/icons\/[^"?]+\.png)"/g, `"src": "$1?v=${buildId}"`));
  for (const f of fs.readdirSync(DIST).filter((x) => x.endsWith('.html'))) {
    const p = path.join(DIST, f); const t = fs.readFileSync(p, 'utf8');
    const u = t.replace(/(href|src)="(\/icons\/[^"?]+\.png)"/g, `$1="$2?v=${buildId}"`).replace(/href="(\/manifest\.webmanifest)"/g, `href="$1?v=${buildId}"`);
    if (u !== t) fs.writeFileSync(p, u);
  } }
const REPL = {
  __BUSINESS_INFO__: opLine, __BIZ_NAME__: biz.name || (FREE ? (biz.brand || '002BOOK 운영자') : '002BOOK'), __BIZ_OWNER__: biz.owner || '(대표자명)', __BIZ_PHONE__: biz.phone || '(전화번호)',
  __PRIVACY_OFFICER__: biz.privacyOfficer || biz.owner || '(개인정보 보호책임자)', __PRIVACY_EMAIL__: biz.privacyEmail || biz.email || 'help@002book.com',
  __EFFECTIVE_DATE__: cfg.effectiveDate || '2026년 12월 1일', __POLICY_VERSION__: cfg.policyVersion || '2026-12-01',
};
for (const f of ['index.html', '404.html', 'terms.html', 'privacy.html', 'refund.html', 'delete-account.html', 'guardian.html', 'pay/checkout.html', 'pay/success.html', 'pay/fail.html']) {
  const p = path.join(DIST, f); if (!fs.existsSync(p)) continue;
  let t = fs.readFileSync(p, 'utf8');
  // 유료/무료 블록: 무료 출시 모드면 PAID 블록을 지우고 FREE 블록만 남긴다
  t = t.replace(/<!--PAID-->([\s\S]*?)<!--\/PAID-->/g, FREE ? '' : '$1').replace(/<!--FREE-->([\s\S]*?)<!--\/FREE-->/g, FREE ? '$1' : '');
  for (const [k, v] of Object.entries(REPL)) t = t.replaceAll(k, v); fs.writeFileSync(p, t);
}
if (FREE) fs.rmSync(path.join(DIST, 'pay'), { recursive: true, force: true }); // 무료 출시 모드: 결제 페이지는 내보내지 않는다
if (cfg.domain) fs.writeFileSync(path.join(DIST, 'CNAME'), cfg.domain + '\n');
fs.writeFileSync(path.join(DIST, '.nojekyll'), '');

/* ---------- 6) 아이콘 (앱 안의 로고에서 생성) ---------- */
try {
  const sharp = (await import('sharp')).default;
  const icon = Buffer.from(m[1], 'base64'); const full = Buffer.from(m2[1], 'base64');
  const bg = { r: 243, g: 236, b: 223, alpha: 1 };
  const dir = path.join(DIST, 'icons'); fs.mkdirSync(dir, { recursive: true });
  // 홈 화면·앱 설치 아이콘: web/brand/app-icon.png(투명 배경 원형 로고)를 흰 바탕에 올린다. 없으면 앱 안의 로고를 쓴다
  const brand = path.join(ROOT, 'web/brand/app-icon.png');
  const src = fs.existsSync(brand) ? fs.readFileSync(brand) : icon;
  const white = { r: 255, g: 255, b: 255, alpha: 1 };
  const onBg = async (size, ratio) => { const inner = Math.round(size * ratio); const lg = await sharp(src).resize(inner, inner, { fit: 'contain', background: { r: 255, g: 255, b: 255, alpha: 0 } }).png().toBuffer();
    return sharp({ create: { width: size, height: size, channels: 4, background: white } }).composite([{ input: lg, gravity: 'center' }]).flatten({ background: white }).png(); };
  for (const s of [192, 512]) await (await onBg(s, 0.92)).toFile(path.join(dir, `icon-${s}.png`));
  await (await onBg(180, 0.88)).toFile(path.join(dir, 'apple-touch-icon.png'));
  await (await onBg(512, 0.76)).toFile(path.join(dir, 'maskable-512.png')); // 마스크 안전 영역(지름 80%) 안에 들어가게
  const logo = await sharp(full).resize(null, 560, { fit: 'contain', background: bg }).png().toBuffer();
  await sharp({ create: { width: 1200, height: 630, channels: 4, background: bg } }).composite([{ input: logo, gravity: 'center' }]).png().toFile(path.join(dir, 'og.png'));
  await sharp({ create: { width: 1024, height: 500, channels: 4, background: bg } }).composite([{ input: await sharp(full).resize(null, 460).png().toBuffer(), gravity: 'center' }]).png().toFile(path.join(dir, 'play-feature.png'));
  fs.copyFileSync(path.join(dir, 'icon-192.png'), path.join(DIST, 'favicon.ico'));
} catch (e) { console.error('아이콘 생성 실패:', e.message); process.exit(1); }

/* ---------- 7) 안드로이드 앱 연결 (Digital Asset Links) ---------- */
const fps = [].concat(cfg.android?.sha256Fingerprints || [], (process.env.ANDROID_SHA256 || '').split(',')).map((x) => x.trim()).filter(Boolean);
fs.mkdirSync(path.join(DIST, '.well-known'), { recursive: true });
fs.writeFileSync(path.join(DIST, '.well-known/assetlinks.json'), JSON.stringify(fps.length ? [{
  relation: ['delegate_permission/common.handle_all_urls'],
  target: { namespace: 'android_app', package_name: cfg.android?.packageId || 'com.book002.app', sha256_cert_fingerprints: fps },
}] : [], null, 2));

console.log(`빌드 완료 → dist/ (build ${buildId}, ${FREE ? '무료 출시 모드' : '유료 모드'}${SUPA ? '' : ', ⚠ SUPABASE_URL 비어 있음'})`);
