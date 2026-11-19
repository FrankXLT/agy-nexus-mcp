const CACHE_NAME = "agy-nexus-overwatch-v3.2.4-b1";
const SHELL_ASSETS = [
  "/web/styles.css?v=3.2.4",
  "/web/workspace.css?v=3.2.4",
  "/web/palettes.js?v=3.2.4",
  "/web/charts.js?v=3.2.4",
  "/web/demo_snapshot.js?v=3.2.4",
  "/web/demo_data.js?v=3.2.4",
  "/web/hierarchy.js?v=3.2.4",
  "/web/uploads.js?v=3.2.4",
  "/web/health.js?v=3.2.4",
  "/web/markdown_renderer.js?v=3.2.4",
  "/web/gallery_select.js?v=3.2.4",
  "/web/sheet_builder.js?v=3.2.4",
  "/web/gallery_view.js?v=3.2.4",
  "/web/workspace_resizer.js?v=3.2.4",
  "/web/explorer.js?v=3.2.4",
  "/web/heatmap.js?v=3.2.4",
  "/web/app.js?v=3.2.4",
  "/web/manifest.webmanifest",
  "/web/icon.svg",
  "/web/icon-192.png",
  "/web/icon-512.png",
  "/web/demo_thumb_desktop.png",
  "/web/demo_thumb_workspace.png",
  "/web/demo_thumb_foldable.png",
  "/web/demo_thumb_mobile.png",
  "/web/demo_thumb_health.png",
];
const SHELL_NAMES = new Set([
  "styles.css", "workspace.css", "palettes.js", "charts.js", "demo_snapshot.js", "demo_data.js", "hierarchy.js",
  "uploads.js", "health.js", "markdown_renderer.js", "gallery_select.js", "sheet_builder.js", "gallery_view.js",
  "workspace_resizer.js", "explorer.js", "heatmap.js", "app.js",
  "manifest.webmanifest", "icon.svg", "icon-192.png", "icon-512.png",
  "demo_thumb_desktop.png", "demo_thumb_workspace.png", "demo_thumb_foldable.png", "demo_thumb_mobile.png", "demo_thumb_health.png",
]);

function isCacheableShellAsset(url, req) {
  if (url.origin !== self.location.origin || req.headers.has("X-Nexus-Passphrase")) return false;
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
