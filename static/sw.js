/**
 * Service Worker — JD Peptides
 *
 * Estrategia:
 * - install: precache del shell estático (CSS, JS, íconos, manifest, fonts CSS).
 * - fetch:
 *     · Static (/static/*): stale-while-revalidate — sirve cache instantáneo y
 *       actualiza en background. Cliente nunca espera.
 *     · HTML (navegación): network-first con timeout 3s; si red falla, sirve
 *       cache previo o /offline. No cacheamos /admin, /carrito, /checkout,
 *       /pedido, ni nada con cookies sensibles.
 *     · POST y cualquier otro: bypass — siempre red, nunca cache.
 * - activate: borra caches viejos.
 */
const CACHE_VERSION = 'jdp-v1';
const STATIC_CACHE  = `${CACHE_VERSION}-static`;
const HTML_CACHE    = `${CACHE_VERSION}-html`;

const PRECACHE = [
  '/static/css/style.css',
  '/static/js/main.js',
  '/static/manifest.json',
  '/static/img/icon-192.png',
  '/static/img/icon-512.png',
  '/static/img/apple-touch-icon.png',
];

// Paths que NUNCA cacheamos (datos sensibles o dinámicos críticos).
const NO_CACHE_PATHS = [
  '/admin', '/api/', '/cron/', '/checkout', '/carrito',
  '/pedido', '/tracking', '/login', '/logout', '/contacto',
];

const isNoCache = (url) => NO_CACHE_PATHS.some((p) => url.pathname.startsWith(p));

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => cache.addAll(PRECACHE)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => !k.startsWith(CACHE_VERSION)).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;
  if (isNoCache(url)) return;

  // Static: stale-while-revalidate
  if (url.pathname.startsWith('/static/') || url.pathname.startsWith('/media/')) {
    event.respondWith(
      caches.open(STATIC_CACHE).then(async (cache) => {
        const cached = await cache.match(req);
        const fetchPromise = fetch(req).then((resp) => {
          if (resp && resp.ok) cache.put(req, resp.clone());
          return resp;
        }).catch(() => cached);
        return cached || fetchPromise;
      })
    );
    return;
  }

  // HTML navigation: network-first con timeout, fallback a cache
  if (req.mode === 'navigate' || (req.headers.get('accept') || '').includes('text/html')) {
    event.respondWith(
      Promise.race([
        fetch(req).then((resp) => {
          if (resp && resp.ok) {
            const copy = resp.clone();
            caches.open(HTML_CACHE).then((c) => c.put(req, copy));
          }
          return resp;
        }),
        new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), 3000)),
      ]).catch(() =>
        caches.match(req).then((cached) => cached || caches.match('/'))
      )
    );
  }
});
