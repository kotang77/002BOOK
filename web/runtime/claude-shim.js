/*
 * 002BOOK 런타임 어댑터
 * ─────────────────────────────────────────────────────────────
 * 기존 앱은 Claude 게시 페이지의 window.claude.use('db'|'sample'|'downloads'|'user')
 * API 위에서 동작한다. 이 파일은 같은 모양의 API를 002book.com 백엔드
 * (Supabase Edge Function 'api')로 구현해서, 앱 코드를 거의 그대로 쓸 수 있게 한다.
 *
 *  - db        : Firestore 모양의 doc/collection API → POST /api {op:'db.*'}
 *  - sample    : Claude 호출 → POST /api {op:'ai.sample'} (서버가 API 키 보관)
 *  - downloads : 브라우저 다운로드
 *  - user      : 로그인 세션 정보
 *  - window.__002.auth : 회원가입·로그인·비밀번호 찾기 (앱 로그인 화면이 호출)
 */
(function () {
  'use strict';
  var CFG = window.__002CFG || {};
  var API = CFG.api;
  var ANON = CFG.anon || '';
  var SKEY = '002.session';

  /* ---------- 세션 ---------- */
  function getSession() { try { return JSON.parse(localStorage.getItem(SKEY) || 'null'); } catch (e) { return null; } }
  function setSession(s) { try { s ? localStorage.setItem(SKEY, JSON.stringify(s)) : localStorage.removeItem(SKEY); } catch (e) {} }

  function ApiError(code, message, extra) {
    var e = new Error(message || code); e.code = code; if (extra) for (var k in extra) e[k] = extra[k]; return e;
  }

  async function call(op, body, opt) {
    if (!API) throw ApiError('not_configured', '서버 주소가 설정되지 않았어요.');
    var s = getSession();
    var headers = { 'content-type': 'application/json', apikey: ANON, authorization: 'Bearer ' + ANON };
    if (s && s.token) headers['x-session'] = s.token;
    var res, json;
    try {
      res = await fetch(API, { method: 'POST', headers: headers, body: JSON.stringify(Object.assign({ op: op }, body || {})), signal: opt && opt.signal });
    } catch (e) {
      if (e && e.name === 'AbortError') throw e;
      throw ApiError('network', '인터넷 연결을 확인해 주세요.');
    }
    try { json = await res.json(); } catch (e) { json = null; }
    if (!res.ok || !json || json.error) {
      var err = (json && json.error) || {};
      if (err.code === 'unauthenticated' && s) { setSession(null); fire('session-expired'); }
      throw ApiError(err.code || ('http_' + res.status), err.message || '요청을 처리하지 못했어요.', err.extra);
    }
    return json.result;
  }

  /* ---------- 이벤트 (세션 만료 등) ---------- */
  var listeners = {};
  function on(name, fn) { (listeners[name] = listeners[name] || []).push(fn); }
  function fire(name, v) { (listeners[name] || []).forEach(function (f) { try { f(v); } catch (e) {} }); }

  /* ---------- 공통: 파일/Blob → base64 ---------- */
  function blobToB64(b) {
    return new Promise(function (resolve, reject) {
      var r = new FileReader();
      r.onload = function () { var s = String(r.result); resolve({ media_type: b.type || 'image/jpeg', data: s.slice(s.indexOf(',') + 1) }); };
      r.onerror = reject; r.readAsDataURL(b);
    });
  }

  /* ================================================================
   * db
   * ================================================================ */
  function clone(v) { return v === undefined ? undefined : JSON.parse(JSON.stringify(v)); }
  function snapDoc(path, row) {
    var id = path.split('/').pop();
    var data = row ? row.data : undefined;
    return {
      id: id, ref: makeDoc(path), exists: !!row,
      version: row ? row.version : 0,
      updatedAt: row ? row.updated_at : null,
      data: function () { return row ? clone(data) : undefined; },
      get: function (f) { return row && data ? clone(data[f]) : undefined; }
    };
  }
  function snapQuery(col, rows) {
    var docs = rows.map(function (r) { return snapDoc(col + '/' + r.id, r); });
    return { docs: docs, size: docs.length, empty: !docs.length, forEach: function (f) { docs.forEach(f); } };
  }

  // 실시간 구독: 서버 부하를 줄이려고 폴링(화면이 보일 때 6초, 숨겨지면 멈춤)
  var POLL_MS = 6000;
  function poller(fetcher, onNext, onErr) {
    var stopped = false, timer = null, last = null;
    async function tick() {
      if (stopped) return;
      if (document.hidden) { timer = setTimeout(tick, POLL_MS); return; }
      try {
        var r = await fetcher();
        var sig = JSON.stringify(r.sig);
        if (sig !== last) { last = sig; onNext(r.snap); }
      } catch (e) { if (onErr) try { onErr(e); } catch (x) {} }
      if (!stopped) timer = setTimeout(tick, POLL_MS);
    }
    tick();
    var vis = function () { if (!document.hidden && !stopped) { clearTimeout(timer); tick(); } };
    document.addEventListener('visibilitychange', vis);
    return function () { stopped = true; clearTimeout(timer); document.removeEventListener('visibilitychange', vis); };
  }
  var bump = { n: 0 }; // 쓰기 직후 구독을 바로 새로고침
  function afterWrite() { bump.n++; fire('db-write'); }

  function makeDoc(path) {
    path = String(path).replace(/^\/+|\/+$/g, '');
    var segs = path.split('/');
    return {
      id: segs[segs.length - 1], path: path,
      parent: makeCol(segs.slice(0, -1).join('/')),
      collection: function (c) { return makeCol(path + '/' + c); },
      get: async function () { var r = await call('db.get', { path: path }); return snapDoc(path, r); },
      set: async function (data, opts) { var r = await call('db.set', { path: path, data: clone(data), merge: !!(opts && opts.merge) }); afterWrite(); return r; },
      update: async function (data) { var r = await call('db.update', { path: path, data: clone(data) }); afterWrite(); return r; },
      delete: async function () { var r = await call('db.delete', { path: path }); afterWrite(); return r; },
      onSnapshot: function (next, err) {
        if (typeof next === 'object' && next) { err = next.error; next = next.next; }
        return poller(async function () { var r = await call('db.get', { path: path }); return { sig: r ? [r.version, r.updated_at] : null, snap: snapDoc(path, r) }; }, next, err);
      }
    };
  }
  function makeQuery(col, q) {
    var api = {
      path: col,
      where: function (f, op, v) { return makeQuery(col, Object.assign({}, q, { where: (q.where || []).concat([[f, op, v]]) })); },
      orderBy: function (f, dir) { return makeQuery(col, Object.assign({}, q, { orderBy: (q.orderBy || []).concat([[f, dir || 'asc']]) })); },
      limit: function (n) { return makeQuery(col, Object.assign({}, q, { limit: n })); },
      get: async function () { var r = await call('db.query', { collection: col, query: q }); return snapQuery(col, r); },
      onSnapshot: function (next, err) {
        if (typeof next === 'object' && next) { err = next.error; next = next.next; }
        return poller(async function () { var r = await call('db.query', { collection: col, query: q }); return { sig: r.map(function (x) { return [x.id, x.version]; }), snap: snapQuery(col, r) }; }, next, err);
      }
    };
    return api;
  }
  function makeCol(col) {
    col = String(col).replace(/^\/+|\/+$/g, '');
    var base = makeQuery(col, {});
    base.id = col.split('/').pop();
    base.doc = function (id) { return makeDoc(col + '/' + (id || (Date.now().toString(36) + Math.random().toString(36).slice(2, 8)))); };
    base.add = async function (data) { var d = base.doc(); await d.set(data); return d; };
    return base;
  }
  var db = Object.freeze({ doc: makeDoc, collection: makeCol });

  /* ================================================================
   * sample (Claude)
   * ================================================================ */
  function stripFence(t) {
    t = String(t || '').trim();
    var m = t.match(/```(?:json)?\s*([\s\S]*?)```/i); if (m) t = m[1].trim();
    var a = t.search(/[\[{]/); if (a > 0) t = t.slice(a);
    var z = Math.max(t.lastIndexOf('}'), t.lastIndexOf(']')); if (z >= 0) t = t.slice(0, z + 1);
    return t;
  }
  async function sample(input, opts) {
    opts = opts || {};
    var images = [];
    if (opts.images && opts.images.length) images = await Promise.all([].slice.call(opts.images, 0, 8).map(blobToB64));
    var messages = typeof input === 'string' ? [{ role: 'user', content: input }] : input;
    if (opts.onText) { try { opts.onText({ text: '생각하는 중…', delta: '' }); } catch (e) {} }
    var r = await call('ai.sample', { messages: messages, images: images, tier: opts.modelTier || 'default', json: !!opts.__json }, { signal: opts.signal });
    if (opts.onText) { try { opts.onText({ text: r.text, delta: r.text }); } catch (e) {} }
    return { text: r.text, truncated: !!r.truncated, modelApplied: r.model };
  }
  sample.json = async function (input, opts) {
    var r = await sample(input, Object.assign({}, opts, { __json: true }));
    try { return JSON.parse(stripFence(r.text)); }
    catch (e) { throw ApiError('bad_json', 'AI 응답을 읽지 못했어요. 다시 시도해 주세요.', { text: r.text }); }
  };
  sample.limits = async function () { return { images: true }; };

  /* ================================================================
   * downloads
   * ================================================================ */
  var downloads = Object.freeze({
    save: async function (o) {
      var data = o && o.data, name = (o && o.filename) || 'download';
      var blob = data instanceof Blob ? data : new Blob([data], { type: (o && o.type) || 'application/octet-stream' });
      var url = URL.createObjectURL(blob), a = document.createElement('a');
      a.href = url; a.download = name; document.body.appendChild(a); a.click();
      setTimeout(function () { URL.revokeObjectURL(url); a.remove(); }, 4000);
      return { ok: true };
    }
  });

  /* ================================================================
   * user
   * ================================================================ */
  var user = Object.freeze({
    id: async function () { var s = getSession(); return s ? s.uid : null; },
    me: async function () { var s = getSession(); return { id: s ? s.uid : null, name: s ? s.uid : '' }; },
    isOwner: function () { var s = getSession(); return !!(s && s.admin); },
    canEdit: function () { var s = getSession(); return !!(s && s.admin); },
    can: async function (name) { return name === 'data.write' ? true : null; },
    profiles: async function (ids) { var o = {}; (ids || []).forEach(function (i) { o[i] = { id: i, name: '' }; }); return o; }
  });

  /* ================================================================
   * auth (앱 로그인 화면에서 호출)
   * ================================================================ */
  var auth = Object.freeze({
    session: getSession,
    signup: async function (p) { var r = await call('auth.signup', p); setSession(r.session); return r; },
    login: async function (id, pw) { var r = await call('auth.login', { id: id, pw: pw }); setSession(r.session); return r; },
    google: async function (p) { var r = await call('auth.google', p); if (r.session) setSession(r.session); return r; },
    logout: async function () { try { await call('auth.logout', {}); } catch (e) {} setSession(null); },
    resume: async function () { var s = getSession(); if (!s) return null; try { var r = await call('auth.me', {}); return r; } catch (e) { return null; } },
    resetPassword: function (id, email) { return call('auth.reset', { id: id, email: email }); },
    findId: function (email) { return call('auth.findId', { email: email }); },
    changePassword: function (oldPw, newPw) { return call('auth.changePassword', { oldPw: oldPw, newPw: newPw }); },
    withdraw: async function (pw, credential) { var r = await call('auth.withdraw', credential ? { credential: credential } : { pw: pw }); setSession(null); return r; },
    guardianRequest: function (p) { return call('auth.guardianRequest', p); }
  });

  /* ================================================================
   * 기타 서버 기능 (관리자 메일, 결제)
   * ================================================================ */
  var server = Object.freeze({
    call: call,
    adminMail: function (p) { return call('admin.mail', p); },
    adminMembers: function () { return call('admin.members', {}); },
    adminSetPassword: function (id) { return call('admin.resetPassword', { id: id }); },
    adminDelete: function (id) { return call('admin.deleteMember', { id: id }); },
    payReady: function (plan) { return call('pay.ready', { plan: plan }); },
    payConfirm: function (p) { return call('pay.confirm', p); },
    plans: function () { return call('pay.plans', {}); }
  });

  window.__002 = { auth: auth, server: server, on: on, isPlayApp: /android-app:\/\/com\.book002\.app/.test(document.referrer) || /[?&]source=twa/.test(location.search) || sessionStorage.getItem('002.twa') === '1' };
  if (window.__002.isPlayApp) try { sessionStorage.setItem('002.twa', '1'); } catch (e) {}

  /* ---------- window.claude.use ---------- */
  var NS = { db: db, sample: sample, downloads: downloads, user: user };
  window.claude = Object.freeze({
    use: function (name) {
      return new Promise(function (resolve) { setTimeout(function () { resolve(NS[name] || null); }, 0); });
    }
  });
})();
