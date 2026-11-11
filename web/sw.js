const CACHE_NAME = "agy-nexus-overwatch-v2.6.0d";
const SHELL_ASSETS = [
  "/web",
  "/web/styles.css?v=2.6.0d",
  "/web/palettes.js?v=2.6.0d",
  "/web/charts.js?v=2.6.0d",
  "/web/demo_data.js?v=2.6.0d",
  "/web/hierarchy.js?v=2.6.0d",
  "/web/uploads.js?v=2.6.0d",
  "/web/health.js?v=2.6.0d",
  "/web/app.js?v=2.6.0d",
  "/web/manifest.webmanifest",
  "/web/icon.svg",
  "/web/icon-192.png",
  "/web/icon-512.png",
];
const SHELL_NAMES = new Set([
  "styles.css", "palettes.js", "charts.js", "demo_data.js", "hierarchy.js",
  "uploads.js", "health.js", "app.js", "manifest.webmanifest", "icon.svg", "icon-192.png", "icon-512.png",
]);

function isCacheableShellAsset(url, req) {
  if (url.origin !== self.location.origin || req.headers.has("X-Nexus-Passphrase")) return false;
  if (url.pathname === "/web" || url.pathname === "/web/index.html") return true;
  return url.pathname.startsWith("/web/") && SHELL_NAMES.has(url.pathname.slice(5));
}

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
  if (!isCacheableShellAsset(url, req)) return;
  event.respondWith(
    fetch(req)
      .then((resp) => {
        if (resp && resp.status === 200) {
          const copy = resp.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(req, copy)).catch(() => {});
        }
        return resp;
      })
      .catch(() => caches.match(req))
  );
});
