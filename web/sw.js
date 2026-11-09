const CACHE_NAME = "agy-nexus-overwatch-v2.4.1";
const SHELL_ASSETS = ["/web", "/web/styles.css?v=2.4.1",
  "/web/charts.js?v=2.4.1",
  "/web/hierarchy.js?v=2.4.1",
  "/web/app.js?v=2.4.1",
  "/web/manifest.webmanifest", "/web/icon.svg", "/web/icon-192.png", "/web/icon-512.png"];

self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_ASSETS).catch(() => {}))
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.pathname.endsWith("/web/api/stats")) {
    return;
  }
  event.respondWith(
    fetch(req)
      .then((resp) => {
        if (resp && resp.status === 200 && url.pathname.includes("/web")) {
          const copy = resp.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(req, copy)).catch(() => {});
        }
        return resp;
      })
      .catch(() => caches.match(req))
  );
});
