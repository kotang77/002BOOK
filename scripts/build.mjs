// 빌드: app/source.html + web/ → dist/
//   node scripts/build.mjs
// 환경 변수(또는 site.config.json): SUPABASE_URL, SUPABASE_ANON_KEY
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import * as acorn from 'acorn';
import { FUNCTIONS, FUNCTION_EDITS, CONSTS, STRINGS } from './patches.mjs';

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

/* ---------- 2) 함수 단위 패치 (acorn) ---------- */
function findNodes(code) {
  const ast = acorn.parse(code, { ecmaVersion: 'latest', sourceType: 'script', allowAwaitOutsideFunction: true, allowReturnOutsideFunction: true });
  const fns = {}, consts = {};
  (function walk(n, depth) {
    if (!n || typeof n !== 'object') return;
    if (n.type === 'FunctionDeclaration' && n.id) (fns[n.id.name] ||= []).push(n);
    if (n.type === 'VariableDeclaration' && n.declarations.length === 1 && n.declarations[0].id.type === 'Identifier') (consts[n.declarations[0].id.name] ||= []).push(n);
    for (const k in n) { if (k === 'loc') continue; const v = n[k]; if (Array.isArray(v)) v.forEach((x) => walk(x, depth + 1)); else if (v && typeof v.type === 'string') walk(v, depth + 1); }
  })(ast, 0);
  return { fns, consts };
}
const wsRe = (s) => new RegExp(s.trim().split(/\s+/).map((p) => p.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('\\s*'));

let { start, end, code } = mainScript(html);
const edits = []; // [from, to, text]
{
  const { fns, consts } = findNodes(code);
  const one = (map, name) => { const a = map[name]; if (!a || a.length !== 1) { errors.push(`함수 ${name}: ${a ? a.length + '개' : '없음'}`); return null; } return a[0]; };
  for (const [name, text] of Object.entries(FUNCTIONS)) { const n = one(fns, name); if (n) edits.push([n.start, n.end, text]); }
  for (const [name, text] of Object.entries(CONSTS)) { const n = one(consts, name); if (n) edits.push([n.start, n.end, text]); }
  for (const [name, pairs] of Object.entries(FUNCTION_EDITS)) {
    const n = one(fns, name); if (!n) continue;
    let src = code.slice(n.start, n.end);
    for (const [from, to] of pairs) {
      const re = wsRe(from); const m = src.match(re);
      if (!m) { errors.push(`함수 ${name} 안의 고칠 부분을 찾지 못함: ${from.slice(0, 40)}…`); continue; }
      src = src.replace(re, () => to);
    }
    edits.push([n.start, n.end, src]);
  }
}
edits.sort((a, b) => b[0] - a[0]);
for (const [a, b, t] of edits) code = code.slice(0, a) + t + code.slice(b);
html = html.slice(0, start) + code + html.slice(end);

/* ---------- 3) 문자열 패치 ---------- */
for (const [label, from, to] of STRINGS) {
  const n = html.split(from).length - 1;
  if (n !== 1) { errors.push(`문자열 패치 "${label}": ${n}번 나옴 (1번이어야 함)`); continue; }
  html = html.replace(from, () => to);
}
const FREE = process.env.FREE_LAUNCH ? process.env.FREE_LAUNCH === '1' : cfg.freeLaunch !== false; // 무료 출시 모드(기본 켜짐)
const biz = cfg.business || {};
// 전자상거래법 제10조·제13조: 상호, 대표자, 주소, 전화, 이메일, 사업자등록번호, 통신판매업 신고번호, 호스팅 제공자, 이용약관 연결
const bizLine = [biz.name && `상호 ${biz.name}`, biz.owner && `대표 ${biz.owner}`, biz.address && `주소 ${biz.address}`, biz.phone && `전화 ${biz.phone}`, biz.email && `이메일 ${biz.email}`,
  biz.regNo && `사업자등록번호 ${biz.regNo}` + (biz.regNo ? ` <a href="https://www.ftc.go.kr/bizCommPop.do?wrkr_no=${biz.regNo.replace(/\D/g, '')}" target="_blank" rel="noopener" style="color:inherit">[사업자정보 확인]</a>` : ''),
  biz.mailOrderNo && `통신판매업 신고 ${biz.mailOrderNo}${biz.mailOrderAgency ? ' (' + biz.mailOrderAgency + ')' : ''}`,
  `호스팅 제공 GitHub, Inc. · Supabase, Inc.`].filter(Boolean).join(' · ');
const opLine = FREE && !biz.name ? ['서비스 운영자 개인 운영 (무료 제공 · 사업자 등록 전)', (biz.email || biz.privacyEmail) && `문의 ${biz.email || biz.privacyEmail}`, '호스팅 제공 GitHub, Inc. · Supabase, Inc.'].filter(Boolean).join(' · ') : bizLine;
const missing = ['name', 'owner', 'address', 'phone', 'email', 'regNo', 'mailOrderNo'].filter((k) => !biz[k]);
if (missing.length && !FREE) console.warn('⚠ site.config.json 사업자 정보 비어 있음 (전자상거래법 표시 의무): ' + missing.join(', '));

/* ---------- 4) 남은 위험 패턴 검사 ---------- */
const main2 = mainScript(html).code;
for (const bad of ['sha(S.me.salt', "sha(d.salt+pw)", 'up.pw=', 'salt,pw:await sha']) if (main2.includes(bad)) errors.push(`비밀번호를 브라우저에서 다루는 코드가 남아 있음: ${bad}`);
try { acorn.parse(main2, { ecmaVersion: 'latest', allowAwaitOutsideFunction: true, allowReturnOutsideFunction: true }); }
catch (e) { errors.push('패치 후 문법 오류: ' + e.message); }

if (errors.length) { console.error('\n빌드 실패:\n - ' + errors.join('\n - ')); process.exit(1); }

/* ---------- 5) dist 만들기 ---------- */
fs.rmSync(DIST, { recursive: true, force: true });
fs.cpSync(path.join(ROOT, 'web'), DIST, { recursive: true });
fs.writeFileSync(path.join(DIST, 'index.html'), html);
fs.writeFileSync(path.join(DIST, '404.html'), html);
fs.writeFileSync(path.join(DIST, 'runtime/config.js'),
  `window.__002CFG=${JSON.stringify({ api: SUPA ? SUPA.replace(/\/$/, '') + '/functions/v1/api' : '', anon: ANON, toss: cfg.tossClientKey || '', free: FREE })};\n`);
const buildId = crypto.createHash('sha256').update(html + fs.readFileSync(path.join(ROOT, 'web/runtime/claude-shim.js'))).digest('hex').slice(0, 10);
const sw = path.join(DIST, 'sw.js'); fs.writeFileSync(sw, fs.readFileSync(sw, 'utf8').replace('__BUILD_ID__', buildId));
const REPL = {
  __BUSINESS_INFO__: opLine, __BIZ_NAME__: biz.name || (FREE ? '002BOOK 운영자' : '002BOOK'), __BIZ_OWNER__: biz.owner || '(대표자명)', __BIZ_PHONE__: biz.phone || '(전화번호)',
  __PRIVACY_OFFICER__: biz.privacyOfficer || biz.owner || '(개인정보 보호책임자)', __PRIVACY_EMAIL__: biz.privacyEmail || biz.email || 'help@002book.com',
  __EFFECTIVE_DATE__: cfg.effectiveDate || '2026년 12월 1일', __POLICY_VERSION__: cfg.policyVersion || '2026-12-01',
};
for (const f of ['index.html', '404.html', 'terms.html', 'privacy.html', 'refund.html', 'delete-account.html', 'guardian.html', 'pay/checkout.html', 'pay/success.html', 'pay/fail.html', 'admin/import.html']) {
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
const m = html.match(/LOGO_ICON='data:image\/png;base64,([A-Za-z0-9+/=]+)'/);
const m2 = html.match(/LOGO_FULL='data:image\/png;base64,([A-Za-z0-9+/=]+)'/);
try {
  const sharp = (await import('sharp')).default;
  const icon = Buffer.from(m[1], 'base64'); const full = Buffer.from(m2[1], 'base64');
  const bg = { r: 243, g: 236, b: 223, alpha: 1 };
  const dir = path.join(DIST, 'icons'); fs.mkdirSync(dir, { recursive: true });
  for (const s of [192, 512]) await sharp(icon).resize(s, s, { fit: 'contain', background: bg }).flatten({ background: bg }).png().toFile(path.join(dir, `icon-${s}.png`));
  await sharp(icon).resize(180, 180, { fit: 'contain', background: bg }).flatten({ background: bg }).png().toFile(path.join(dir, 'apple-touch-icon.png'));
  const inner = await sharp(icon).resize(400, 400, { fit: 'contain', background: bg }).flatten({ background: bg }).png().toBuffer();
  await sharp({ create: { width: 512, height: 512, channels: 4, background: bg } }).composite([{ input: inner, gravity: 'center' }]).png().toFile(path.join(dir, 'maskable-512.png'));
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

console.log(`빌드 완료 → dist/ (build ${buildId}, 패치 ${edits.length + STRINGS.length}개, ${FREE ? '무료 출시 모드' : '유료 모드'}${SUPA ? '' : ', ⚠ SUPABASE_URL 비어 있음'})`);
