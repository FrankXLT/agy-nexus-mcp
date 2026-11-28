/* SPDX-License-Identifier: Apache-2.0 */
/* AGY-Nexus /web/v9 — Offline & Static Showcase Session Bucket + Markdown Docs Helper */
(() => {
  const V9 = window.AgyV9;

  const DEMO_THUMBS_TUPLES = [
    ["demo_thumb_desktop.png", "desktop_analytics_1440x900.png", "desktop", 1440, 900],
    ["demo_thumb_workspace.png", "workspace_split_reader.png", "desktop", 1440, 900],
    ["demo_thumb_foldable.png", "foldable_unfolded_900x1000.png", "foldable", 820, 1080],
    ["demo_thumb_mobile.png", "mobile_viewport_390x844.png", "mobile", 390, 844],
  ];

  function assetUrl(rel) {
    if (V9 && typeof V9.toAssetUrl === "function") return V9.toAssetUrl(rel);
    const clean = String(rel || "").replace(/^\.?\/+/, "").replace(/^web\/+/, "");
    return `/web/${clean}`;
  }

  function findSessionInTree(tree, sessionId) {
    for (const proj of (tree && tree.projects) || []) {
      for (const s of proj.sessions || []) {
        if (s.conversation_id === sessionId) return { proj, session: s };
      }
    }
    return null;
  }

  function buildFallbackVisuals(cid, capCount) {
    const showCount = capCount > 0 ? Math.min(DEMO_THUMBS_TUPLES.length, capCount) : 0;
    return DEMO_THUMBS_TUPLES.slice(0, showCount).map((row) => ({
      name: row[1],
      scope: `demo-${cid}`,
      rel_path: row[1],
      category: row[2],
      size: 64000,
      width: row[3],
      height: row[4],
      signed_url: assetUrl(row[0]),
    }));
  }

  function mapVisualItem(it, cid) {
    const rel = it.asset_rel || it.signed_url || "demo_thumb_desktop.png";
    return Object.assign({}, it, {
      scope: it.scope || `demo-${cid}`,
      signed_url: assetUrl(rel),
    });
  }

  async function getDemoSessionBucket(sessionId, tree) {
    const hit = findSessionInTree(tree, sessionId);
    const sess = hit ? hit.session : null;
    const proj = hit ? hit.proj : null;
    const cid = (sess && sess.conversation_id) || sessionId || "demo-session";
    const snap = window.DEMO_SNAPSHOT || {};
    const bundled = snap.demo_sessions && snap.demo_sessions[cid];

    const capCount = sess ? Number(sess.capture_count || 0) : 0;
    const visual_artifacts = bundled && Array.isArray(bundled.visual_artifacts) && bundled.visual_artifacts.length
      ? bundled.visual_artifacts.map((it) => mapVisualItem(it, cid))
      : buildFallbackVisuals(cid, capCount);

    const repo_visual_assets = bundled && Array.isArray(bundled.repo_visual_assets) && bundled.repo_visual_assets.length
      ? bundled.repo_visual_assets.map((it) => mapVisualItem(it, cid))
      : [{
          name: "code-health-watchlist.png",
          scope: "repo-demo",
          rel_path: "docs/assets/code-health-watchlist.png",
          category: "repo_asset",
          size: 51200,
          width: 960,
          height: 600,
          signed_url: assetUrl("demo_thumb_health.png"),
        }];

    const artifacts = bundled && Array.isArray(bundled.artifacts) && bundled.artifacts.length
      ? bundled.artifacts.map((a) => Object.assign({}, a))
      : [{ name: "session-summary.md", rel_path: "session-summary.md", size: 220, type: "artifact" }];

    return {
      ok: true,
      conversation_id: cid,
      title: (sess && sess.title) || (proj && proj.project_name) || cid.slice(0, 8),
      project_id: (proj && proj.project_id) || "",
      project_name: (proj && proj.project_name) || "Demo Project",
      repo_slug: (bundled && bundled.repo_slug) || (proj && proj.project_id) || "agy-nexus-mcp",
      rollover: {
        posture: (sess && sess.rollover_posture) || "FRESH",
        reason: sess ? `${sess.step_count || 0} steps · ${sess.relative_age || "snapshot"}` : "snapshot",
        should_rollover: false,
      },
      artifacts,
      uploads: bundled && Array.isArray(bundled.uploads) ? bundled.uploads.map((u) => Object.assign({}, u)) : [],
      visual_artifacts,
      repo_visual_assets,
    };
  }

  function rewriteShowcaseImageLinks(mdText) {
    return String(mdText || "").replace(/(?:\/web\/|\.\/)(demo_thumb_[a-z0-9_]+\.png)/g, (_m, fname) => assetUrl(fname));
  }

  async function getDemoDocFile(relPath, bucket) {
    const cid = (bucket && bucket.conversation_id) || "";
    const snap = window.DEMO_SNAPSHOT || {};
    const bundled = cid && snap.demo_sessions ? snap.demo_sessions[cid] : null;
    const files = (bundled && bundled.files) || {};
    let chosenPath = String(relPath || "").trim();
    if (!chosenPath || !Object.prototype.hasOwnProperty.call(files, chosenPath)) {
      const base = chosenPath.split("/").pop();
      const alt = Object.keys(files).find((k) => k === base || k.endsWith(`/${base}`));
      chosenPath = alt || Object.keys(files)[0] || chosenPath || "session-summary.md";
    }
    if (Object.prototype.hasOwnProperty.call(files, chosenPath)) {
      const md = rewriteShowcaseImageLinks(files[chosenPath]);
      return { ok: true, rel_path: chosenPath, content: md, raw_content: md, size: md.length };
    }
    const title = (bucket && bucket.title) || "Showcase Session";
    const repo = (bucket && bucket.repo_slug) || (bucket && bucket.project_name) || "workspace";
    const reason = (bucket && bucket.rollover && bucket.rollover.reason) || "snapshot";
    const md = [
      `# ${title}`,
      "",
      `- **Repository**: \`${repo}\``,
      `- **Session Status**: ${reason}`,
      `- **Artifact Preview**: Select one of the top-listed bundled showcase sessions in the tree for full multi-tab \`task.md\`, \`implementation_plan.md\`, and \`walkthrough.md\` artifacts.`,
      "",
      "> Read-only depersonalized showcase — unlock a live workstation to browse full filesystem artifacts.",
      "",
    ].join("\n");
    return { ok: true, rel_path: relPath || "session-summary.md", content: md, raw_content: md, size: md.length };
  }

  V9.DemoDocs = { DEMO_THUMBS_TUPLES, getDemoSessionBucket, getDemoDocFile };
})();
