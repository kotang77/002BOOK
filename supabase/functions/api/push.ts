// 휴대폰 푸시 알림 (Web Push: VAPID 서명 + aes128gcm 암호화, RFC 8291/8292)
// 외부 라이브러리·비밀값 없이 WebCrypto만 쓴다. VAPID 키는 처음 쓸 때 서버가 만들어 docs 'sys/vapid'에 보관한다
// (sys 컬렉션은 rules.ts에서 누구도 읽거나 쓸 수 없게 막혀 있고, 서버만 service_role로 접근한다).
import { ADMIN_ID, env, sb } from './lib.ts';

const enc = new TextEncoder();
const b64u = (b: Uint8Array) => btoa(String.fromCharCode(...b)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
export const unb64u = (s: string) => { s = s.replace(/-/g, '+').replace(/_/g, '/'); while (s.length % 4) s += '='; return Uint8Array.from(atob(s), (c) => c.charCodeAt(0)); };
const cat = (...a: Uint8Array[]) => { const o = new Uint8Array(a.reduce((n, x) => n + x.length, 0)); let p = 0; for (const x of a) { o.set(x, p); p += x.length; } return o; };
const B = (u: Uint8Array) => u as unknown as BufferSource & BodyInit;
async function hmac(key: Uint8Array, data: Uint8Array) {
  const k = await crypto.subtle.importKey('raw', B(key), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return new Uint8Array(await crypto.subtle.sign('HMAC', k, B(data)));
}

type Vapid = { pub: string; jwk: JsonWebKey };
let cached: Vapid | null = null;
export async function vapid(): Promise<Vapid> {
  if (cached) return cached;
  const { data } = await sb.from('docs').select('data').eq('path', 'sys/vapid').maybeSingle();
  const d = data?.data as Vapid | undefined;
  if (d?.pub && d?.jwk) return (cached = d);
  const kp = await crypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, true, ['sign', 'verify']) as CryptoKeyPair;
  const pub = b64u(new Uint8Array(await crypto.subtle.exportKey('raw', kp.publicKey)));
  const jwk = await crypto.subtle.exportKey('jwk', kp.privateKey);
  const v = { pub, jwk };
  // 동시에 두 요청이 만들면 먼저 저장된 것을 쓴다
  const { error } = await sb.from('docs').insert({ path: 'sys/vapid', parent: 'sys', id: 'vapid', data: v, owner: ADMIN_ID });
  if (error) { const { data: again } = await sb.from('docs').select('data').eq('path', 'sys/vapid').maybeSingle(); if (again?.data) return (cached = again.data as Vapid); }
  return (cached = v);
}

async function vapidAuth(endpoint: string) {
  const v = await vapid();
  const key = await crypto.subtle.importKey('jwk', v.jwk, { name: 'ECDSA', namedCurve: 'P-256' }, false, ['sign']);
  const head = b64u(enc.encode(JSON.stringify({ typ: 'JWT', alg: 'ES256' })));
  const body = b64u(enc.encode(JSON.stringify({ aud: new URL(endpoint).origin, exp: Math.floor(Date.now() / 1000) + 12 * 3600, sub: 'mailto:' + env('PUSH_CONTACT', 'no-reply@002book.com') })));
  const sig = new Uint8Array(await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, key, B(enc.encode(head + '.' + body))));
  return `vapid t=${head}.${body}.${b64u(sig)}, k=${v.pub}`;
}

/** RFC 8291 aes128gcm: 받는 기기의 공개키(p256dh)와 auth 비밀값으로 내용을 암호화한다 */
export async function encryptPayload(p256dh: string, auth: string, text: string) {
  const uaPub = unb64u(p256dh), authSecret = unb64u(auth);
  const as = await crypto.subtle.generateKey({ name: 'ECDH', namedCurve: 'P-256' }, true, ['deriveBits']) as CryptoKeyPair;
  const asPub = new Uint8Array(await crypto.subtle.exportKey('raw', as.publicKey));
  const uaKey = await crypto.subtle.importKey('raw', B(uaPub), { name: 'ECDH', namedCurve: 'P-256' }, false, []);
  const shared = new Uint8Array(await crypto.subtle.deriveBits({ name: 'ECDH', public: uaKey }, as.privateKey, 256));
  const prkKey = await hmac(authSecret, shared);
  const ikm = (await hmac(prkKey, cat(enc.encode('WebPush: info\0'), uaPub, asPub, new Uint8Array([1])))).slice(0, 32);
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const prk = await hmac(salt, ikm);
  const cek = (await hmac(prk, cat(enc.encode('Content-Encoding: aes128gcm\0'), new Uint8Array([1])))).slice(0, 16);
  const nonce = (await hmac(prk, cat(enc.encode('Content-Encoding: nonce\0'), new Uint8Array([1])))).slice(0, 12);
  const key = await crypto.subtle.importKey('raw', B(cek), 'AES-GCM', false, ['encrypt']);
  const ct = new Uint8Array(await crypto.subtle.encrypt({ name: 'AES-GCM', iv: B(nonce) }, key, B(cat(enc.encode(text), new Uint8Array([2])))));
  const rs = new Uint8Array([0, 0, 16, 0]); // 4096
  return cat(salt, rs, new Uint8Array([asPub.length]), asPub, ct);
}

type Sub = { endpoint: string; keys: { p256dh: string; auth: string }; at?: number; ua?: string };
const subsPath = (uid: string) => 'pushsubs/' + uid;

export async function subsOf(uid: string): Promise<Sub[]> {
  const { data } = await sb.from('docs').select('data').eq('path', subsPath(uid)).maybeSingle();
  const l = (data?.data as { subs?: Sub[] } | undefined)?.subs;
  return Array.isArray(l) ? l : [];
}
async function saveSubs(uid: string, subs: Sub[]) {
  const { data: prev } = await sb.from('docs').select('version').eq('path', subsPath(uid)).maybeSingle();
  const row = { path: subsPath(uid), parent: 'pushsubs', id: uid, data: { uid, subs }, owner: uid, version: (prev?.version ?? 0) + 1, updated_at: new Date().toISOString() };
  await sb.from('docs').upsert(row);
}
const okEndpoint = (u: string) => { try { const x = new URL(u); return x.protocol === 'https:' && u.length < 1000; } catch { return false; } };

export async function addSub(uid: string, s: Sub, ua: string) {
  if (!s || !okEndpoint(String(s.endpoint)) || !s.keys?.p256dh || !s.keys?.auth) throw new Error('bad_sub');
  const subs = (await subsOf(uid)).filter((x) => x.endpoint !== s.endpoint);
  subs.push({ endpoint: s.endpoint, keys: { p256dh: String(s.keys.p256dh), auth: String(s.keys.auth) }, at: Date.now(), ua: String(ua || '').slice(0, 120) });
  await saveSubs(uid, subs.slice(-5)); // 한 사람당 기기 5대까지
}
export async function removeSub(uid: string, endpoint?: string) {
  const subs = endpoint ? (await subsOf(uid)).filter((x) => x.endpoint !== endpoint) : [];
  await saveSubs(uid, subs);
}

/** 회원의 모든 기기로 알림을 보낸다. 보낸 기기 수를 돌려준다. 만료된 구독은 지운다. */
export async function pushTo(uid: string, msg: { title: string; body: string; url?: string; tag?: string }): Promise<number> {
  const subs = await subsOf(uid);
  if (!subs.length) return 0;
  if (env('FAKE_PUSH')) { console.log('PUSH→', uid, subs.length, JSON.stringify(msg)); return subs.length; }
  const text = JSON.stringify({ title: msg.title, body: msg.body, url: msg.url ?? '/', tag: msg.tag ?? '' });
  let sent = 0; const dead: string[] = [];
  await Promise.all(subs.map(async (s) => {
    try {
      const body = await encryptPayload(s.keys.p256dh, s.keys.auth, text);
      const r = await fetch(s.endpoint, { method: 'POST', headers: { TTL: '86400', Urgency: 'normal', 'Content-Encoding': 'aes128gcm', 'Content-Type': 'application/octet-stream', Authorization: await vapidAuth(s.endpoint) }, body: B(body) });
      if (r.status === 404 || r.status === 410) dead.push(s.endpoint); else if (r.ok) sent++;
      else console.log('push failed', r.status, (await r.text()).slice(0, 200));
    } catch (e) { console.log('push error', String(e)); }
  }));
  if (dead.length) await saveSubs(uid, subs.filter((x) => !dead.includes(x.endpoint)));
  return sent;
}
