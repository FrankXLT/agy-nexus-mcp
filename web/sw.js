const CACHE_NAME = "agy-nexus-v4.0.3";
const SHELL_ASSETS = [
  "/web/v9/v9_layers.css?v=4.0.3",
  "/web/v9/vendor/quiet-ui-tokens.css?v=4.0.3",
  "/web/v9/vendor/quiet-evidence-bundle.css?v=4.0.3",
  "/web/v9/v9_shell.css?v=4.0.3",
  "/web/v9/v9_rail.css?v=4.0.3",
  "/web/v9/v9_analytics.css?v=4.0.3",
  "/web/v9/v9_workspace.css?v=4.0.3",
  "/web/v9/v9_tables_and_rail.css?v=4.0.3",
  "/web/v9/vendor/echarts.min.js?v=4.0.3",
  "/web/v9/vendor/quiet-evidence-bundle.js?v=4.0.3",
  "/web/v9/vendor/echarts-layout-defaults.js?v=4.0.3",
  "/web/v9/vendor/echarts-quiet-adapter.js?v=4.0.3",
  "/web/demo_snapshot.js?v=4.0.3",
  "/web/gallery_select.js?v=4.0.3",
  "/web/sheet_builder.js?v=4.0.3",
  "/web/v9/v9_state.js?v=4.0.3",
  "/web/v9/v9_table_sort.js?v=4.0.3",
  "/web/v9/v9_demo_docs.js?v=4.0.3",
  "/web/v9/v9_demo_adapter.js?v=4.0.3",
  "/web/v9/v9_billing.js?v=4.0.3",
  "/web/v9/v9_charts.js?v=4.0.3",
  "/web/v9/v9_heatmap.js?v=4.0.3",
  "/web/v9/v9_project_view.js?v=4.0.3",
  "/web/v9/v9_analytics.js?v=4.0.3",
  "/web/v9/v9_hierarchy.js?v=4.0.3",
  "/web/v9/v9_markdown.js?v=4.0.3",
  "/web/v9/v9_workspace.js?v=4.0.3",
  "/web/v9/v9_gallery.js?v=4.0.3",
  "/web/v9/v9_lightbox.js?v=4.0.3",
  "/web/v9/v9_app.js?v=4.0.3",
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
  "v9/v9_layers.css",
  "v9/vendor/quiet-ui-tokens.css",
  "v9/vendor/quiet-evidence-bundle.css",
  "v9/v9_shell.css",
  "v9/v9_rail.css",
  "v9/v9_analytics.css",
  "v9/v9_workspace.css",
  "v9/v9_tables_and_rail.css",
  "v9/vendor/echarts.min.js",
  "v9/vendor/quiet-evidence-bundle.js",
  "v9/vendor/echarts-layout-defaults.js",
  "v9/vendor/echarts-quiet-adapter.js",
  "demo_snapshot.js",
  "gallery_select.js",
  "sheet_builder.js",
  "v9/v9_state.js",
  "v9/v9_table_sort.js",
  "v9/v9_demo_docs.js",
  "v9/v9_demo_adapter.js",
  "v9/v9_billing.js",
  "v9/v9_charts.js",
  "v9/v9_heatmap.js",
  "v9/v9_project_view.js",
  "v9/v9_analytics.js",
  "v9/v9_hierarchy.js",
  "v9/v9_markdown.js",
  "v9/v9_workspace.js",
  "v9/v9_gallery.js",
  "v9/v9_lightbox.js",
  "v9/v9_app.js",
  "manifest.webmanifest",
  "icon.svg",
  "icon-192.png",
  "icon-512.png",
  "demo_thumb_desktop.png",
  "demo_thumb_workspace.png",
  "demo_thumb_foldable.png",
  "demo_thumb_mobile.png",
  "demo_thumb_health.png",
]);

function isCacheableShellAsset(url, req) {
  if (url.origin !== self.location.origin || req.headers.has("X-Nexus-Passphrase")) return false;
  const webIdx = url.pathname.indexOf("/web/");
  if (webIdx === -1) return false;
  return SHELL_NAMES.has(url.pathname.slice(webIdx + 5));
}

function canonicalCacheKey(url) {
  const webIdx = url.pathname.indexOf("/web/");
  if (webIdx === -1) return url.href;
  return new URL(`${url.pathname.slice(webIdx)}${url.search || ""}`, self.location.origin).href;
}

self.addEventListener("install", (event) => {
  self.skipWaiting();
  const swPath = (self.location && self.location.pathname) || "/web/sw.js";
  const webBase = swPath.replace(/\/sw\.js$/, "") || "/web";
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) =>
      Promise.allSettled(
        SHELL_ASSETS.map((asset) => {
          const fetchUrl = new URL(`${webBase}${asset.slice(4)}`, self.location.origin).href;
          const canonUrl = new URL(asset, self.location.origin).href;
          return fetch(fetchUrl).then((resp) => (resp && resp.status === 200 ? cache.put(canonUrl, resp) : undefined));
        })
      )
    )
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
  const cacheKey = canonicalCacheKey(url);
  event.respondWith(
    fetch(req)
      .then((resp) => {
        if (resp && resp.status === 200) {
          const copy = resp.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(cacheKey, copy)).catch(() => {});
        }
        return resp;
      })
      .catch(() => caches.match(cacheKey))
  );
});
