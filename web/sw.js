/* 002BOOK 서비스 워커: 앱처럼 설치·빠른 재방문·오프라인 안내 */
const VERSION = '__BUILD_ID__';
const CORE = ['/', '/index.html', '/manifest.webmanifest', '/runtime/config.js', '/runtime/claude-shim.js', '/offline.html', '/icons/icon-192.png', '/icons/icon-512.png'];
const CACHE = '002book-' + VERSION;

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(CORE)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k.startsWith('002book-') && k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  // 서버 API·결제는 절대 캐시하지 않음
  if (url.pathname.includes('/functions/v1/') || url.hostname.endsWith('tosspayments.com')) return;

  // 페이지: 네트워크 우선 → 실패 시 캐시 → 오프라인 안내
  if (req.mode === 'navigate') {
    e.respondWith(fetch(req).then((r) => { const c = r.clone(); caches.open(CACHE).then((x) => x.put('/index.html', c)); return r; })
      .catch(async () => (await caches.match('/index.html')) || caches.match('/offline.html')));
    return;
  }
  // 글꼴·CDN 라이브러리·아이콘: 캐시 우선
  if (url.origin === location.origin || /fonts\.(googleapis|gstatic)\.com|cdnjs\.cloudflare\.com/.test(url.hostname)) {
    e.respondWith(caches.match(req).then((hit) => hit || fetch(req).then((r) => {
      if (r.ok || r.type === 'opaque') { const c = r.clone(); caches.open(CACHE).then((x) => x.put(req, c)); }
      return r;
    })));
  }
});

/* 휴대폰 알림 (구술 테스트 리포트 등) */
self.addEventListener('push', (e) => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch (x) { d = { body: e.data ? e.data.text() : '' }; }
  e.waitUntil(self.registration.showNotification(d.title || '002BOOK', {
    body: d.body || '새 알림이 있어요.', icon: '/icons/icon-192.png', badge: '/icons/icon-192.png', lang: 'ko',
    tag: d.tag || undefined, data: { url: d.url || '/' },
  }));
});
self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  const url = new URL((e.notification.data && e.notification.data.url) || '/', self.location.origin).href;
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((cs) => {
    for (const c of cs) { if (c.url.startsWith(self.location.origin) && 'focus' in c) return c.focus(); }
    return self.clients.openWindow(url);
  }));
});
