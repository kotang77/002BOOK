// 공통 도구: 응답, 해시, 토큰, 메일
import { createClient, SupabaseClient } from 'npm:@supabase/supabase-js@2';

export const env = (k: string, d = '') => Deno.env.get(k) ?? d;

export const ADMIN_ID = env('ADMIN_ID', 'kotang77');
export const SITE = env('SITE_URL', 'https://002book.com');

// 테스트(FAKE_DB=1)에서는 메모리 DB를 쓴다. 배포본에는 포함되지 않음.
export const sb: SupabaseClient = env('FAKE_DB')
  ? (await import(new URL('../../../tests/fakesb.ts', import.meta.url).href)).fake()
  : createClient(env('SUPABASE_URL'), env('SUPABASE_SERVICE_ROLE_KEY'), { auth: { persistSession: false } });

const ALLOWED = env('ALLOWED_ORIGINS', 'https://002book.com,https://www.002book.com,http://localhost:8080')
  .split(',').map((s) => s.trim()).filter(Boolean);

export function cors(req: Request): Record<string, string> {
  const o = req.headers.get('origin') ?? '';
  return {
    'access-control-allow-origin': ALLOWED.includes(o) ? o : ALLOWED[0],
    'access-control-allow-headers': 'authorization, apikey, content-type, x-session',
    'access-control-allow-methods': 'POST, GET, OPTIONS',
    'vary': 'origin',
  };
}

export class HttpErr extends Error {
  constructor(public code: string, message: string, public status = 400, public extra?: unknown) { super(message); }
}
export const fail = (code: string, msg: string, status = 400, extra?: unknown) => { throw new HttpErr(code, msg, status, extra); };

/* ---------- 해시 ---------- */
const enc = new TextEncoder();
export const hex = (b: ArrayBuffer) => [...new Uint8Array(b)].map((x) => x.toString(16).padStart(2, '0')).join('');
export async function sha256hex(s: string) { return hex(await crypto.subtle.digest('SHA-256', enc.encode(s))); }
export function randHex(n = 16) { const a = new Uint8Array(n); crypto.getRandomValues(a); return hex(a.buffer); }
export function randToken() {
  const a = new Uint8Array(32); crypto.getRandomValues(a);
  return btoa(String.fromCharCode(...a)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
export async function pbkdf2(pw: string, salt: string, iter = 210000) {
  const key = await crypto.subtle.importKey('raw', enc.encode(pw), 'PBKDF2', false, ['deriveBits']);
  const bits = await crypto.subtle.deriveBits({ name: 'PBKDF2', hash: 'SHA-256', salt: enc.encode(salt), iterations: iter }, key, 256);
  return hex(bits);
}
export function safeEq(a: string, b: string) {
  if (a.length !== b.length) return false;
  let r = 0; for (let i = 0; i < a.length; i++) r |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return r === 0;
}
export function tempPassword() {
  const c = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789';
  const a = new Uint8Array(10); crypto.getRandomValues(a);
  return [...a].map((x) => c[x % c.length]).join('');
}

/* ---------- 메일 (Resend) ---------- */
export async function sendMail(to: string | string[], subject: string, html: string) {
  if (env('FAKE_MAIL')) { console.log('MAIL→', to, subject, '|', [...html.matchAll(/href="([^"]+)"/g)].map((m) => m[1]).join(' '), '|', html.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').slice(0, 400)); return; }
  const key = env('RESEND_API_KEY');
  if (!key) fail('mail_not_configured', '메일 발송이 아직 설정되지 않았어요.', 503);
  const r = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: { authorization: `Bearer ${key}`, 'content-type': 'application/json' },
    body: JSON.stringify({ from: env('MAIL_FROM', '002BOOK <no-reply@002book.com>'), to, subject, html }),
  });
  if (!r.ok) fail('mail_failed', '메일을 보내지 못했어요.', 502, await r.text());
}
export const mailShell = (title: string, body: string) => `<!doctype html><html><body style="margin:0;background:#F3ECDF;font-family:'Apple SD Gothic Neo','Noto Sans KR',sans-serif;color:#2B241F">
<div style="max-width:520px;margin:0 auto;padding:28px 20px"><div style="background:#FFFDF8;border:1px solid #DCCFBB;border-radius:12px;padding:24px">
<h2 style="margin:0 0 14px;font-family:'Nanum Myeongjo',serif">${title}</h2>${body}
<p style="margin-top:22px;font-size:12px;color:#6F6155">002BOOK · <a href="${SITE}" style="color:#8A5024">${SITE.replace('https://', '')}</a></p></div></div></body></html>`;

export const escHtml = (s: unknown) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]!));
