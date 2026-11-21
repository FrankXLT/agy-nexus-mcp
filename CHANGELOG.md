# Changelog

All notable changes to **AGY-Nexus MCP** (`agy-nexus-mcp`) are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.2.5] — 2026-11-20

### Added
- **Cloud MCP Header-Only Visual Fast Path (`src/agy_nexus/media_discovery.py`, `src/agy_nexus/tools_media.py`)**:
  - Added `<2ms` zero-pixel header dimension extraction (`read_image_dimensions_fast`) supporting PNG, JPEG SOFn, WebP (`VP8`/`VP8L`/`VP8X`), and GIF with lazy Pillow fallback.
  - Updated `inspect_visual_artifacts(..., include_thumbnails=False)` to skip WebP encoding on Cloud MCP / Gemini Mobile callers when `region="full"` (`cloud_fast_path=True`, `returned_images=0`, `<4 KB` JSON with `original_px` and **7-day** signed `/web/media/` links), while still returning budgeted WebP `ImageContent` blocks for local callers, region crops, or `include_thumbnails=True`.
- **100% `<= 500L` Modular Compliance (`src/agy_nexus/polyglot_lang_outliners.py`, `src/agy_nexus/handoff_queue_store.py`, `src/agy_nexus/bucket_scanner.py`)**:
  - Extracted markup/config outliners (`polyglot_lang_outliners.py`), atomic flock ticket storage/slugifiers (`handoff_queue_store.py`), and session upload/artifact scanners + Markdown media rewriters (`bucket_scanner.py`) with full backward-compatible exports in `polyglot_outline.py`, `handoff_queue.py`, and `bucket_api.py` — achieving `0` modules above `500` lines across `src/agy_nexus/`, `host_bridge/`, and `web/`.

### Changed
- **Strict `< 20 KB` Outer JSON-Escaped Wire Caps & `tools/list` Compaction (`src/agy_nexus/hygiene.py`, `src/agy_nexus/middleware.py`, `src/agy_nexus/tools_workspace.py`, `src/agy_nexus/tools_session.py`, `src/agy_nexus/tools_ops.py`)**:
  - Added dual raw/escaped wire enforcement (`within_wire_budget`, `compact_payload_to_wire_budget`: `<= 18.5 KB` inner UTF-8 / `<= 19.8 KB` JSON-escaped outer) across `ask_workspace_readonly`, `inspect_git_diff`, `load_session_into_gemini`, and `list_models_and_agents`.
  - Added `_compact_tools_list_body()` in `BridgeCompatMiddleware` stripping empty FastMCP `_meta.fastmcp.tags` and redundant auto-generated `title` fields alongside trimmed tool docstrings, reducing `tools/list` to `<= 8.6 KB`.
- **Multi-Feature `plan` Mode Coercion & Deferred Closeout Retirement (`src/agy_nexus/handoff_templates.py`, `src/agy_nexus/handoff.py`, `src/agy_nexus/retirement.py`)**:
  - Added `resolve_execution_mode_with_reason()` coercing accidental `execution_mode="fast"` back to `"plan"` (`coerced_from_fast=True`) for `new_project` and multi-deliverable/complex `feature_update` handoffs (`>= 3` deliverables, `> 2,200` chars, or security scope), while preserving `"fast"` for compact non-security `bug_or_visual_fix` and `allow_chained_publish=True, resume_headless=True` runs.
  - Added `retire_after_closeout=True` deferral on headless `release_closeout` + `retire_session=True` handoffs so `RETIRED.json` is written only after `git commit` and `git push` succeed (via `record_session_retirement(..., final_commit_sha=<HEAD_SHA>)`), while preserving immediate retirement for non-headless `retire_session=True`.

## [3.2.4] — 2026-11-19

### Added
- **Drag-Resizable 2-Pane Workspace Tree & Modular JS Extractions (`web/workspace_resizer.js`, `web/heatmap.js`, `web/index.html`, `web/workspace.css`, `web/styles.css`)**:
  - Widened default `--tree-w` tokens (`D1: 320px`, `D2: 300px`, `D3: 280px`, `D4: 256px`), styled a subtle `thin` (`6px`) scrollbar with WCAG-compliant thumb contrast, and added `#workspaceResizer` (`220px–480px` drag + keyboard splitter persisted in `localStorage.nexus_tree_width`, double-click to reset).
  - Extracted `web/heatmap.js` (<= 160L) and `web/workspace_resizer.js` (<= 140L) so `web/app.js` drops below `500` lines; registered both across `PWA_ASSETS` (`src/agy_nexus/web_routes.py`), `SHELL_ASSETS`/`SHELL_NAMES` (`web/sw.js`), and `web/index.html`.
- **Direct `/web#workspace` Version Hydration (`src/agy_nexus/bucket_api.py`, `web/health.js`, `web/explorer.js`, `web/demo_data.js`)**:
  - Included `"version"` and cached `"version_info"` in `/web/api/workspace/tree` (and `DEMO_WORKSPACE_TREE`) and extracted `updateVersionBadge()` in `web/health.js` so direct `/web#workspace` loads immediately show the current version dot and label without clobbering Analytics state.

### Fixed
- **Widescreen Desktop Docking & Analytics Expansion (`web/workspace.css`, `web/styles.css`)**:
  - Removed `.workspace-main`'s `max-width: 1680px; margin: 0 auto;` centering so Workspace docks flush edge-to-edge under `.topbar` and keeps the `38px` slim rail aligned beneath `#sidebarToggleBtn` (`◧`).
  - Expanded Analytics `.container` to `min(1960px, calc(100% - 32px))` so 4-up KPI footers (`Gemini Web / Cloud MCP`), the 53-week heatmap, and stacked bar charts scale cleanly on `1920px–3440px` monitors without side gutters.
- **Stale HTML Service Worker Caching (`web/sw.js`, `src/agy_nexus/web_routes.py`, `web/app.js`)**:
  - Removed `"/web"` from `SHELL_ASSETS` and `/web` + `/web/index.html` from `isCacheableShellAsset()`, set `Cache-Control: no-store, no-cache, must-revalidate` on `/web` HTML and `sw.js`, bumped `CACHE_NAME` to `"agy-nexus-overwatch-v3.2.4-b1"`, and added a guarded one-time `controllerchange` reload listener (`sessionStorage.nexus_sw_reloaded === "3.2.4"`).
- **`Pure White` Surface Contrast & Muted Disabled `.btn-focal` (`web/styles.css`)**:
  - Updated `[data-surface="white"]` (`--bg-canvas: #f8fafc`, `--bg-shell: #ffffff`, `--bg-card: #ffffff`, `--bg-elevated: #f1f5f9`) with subtle `--card-shadow` separation, and muted `.btn-focal:disabled` (`✦ Share Sheets`) to neutral slate when `0` items are selected.
- **Readable 2-Line Tree Titles, Gallery `Per Sheet` Label & Clean Corner Badges (`web/workspace.css`, `web/gallery_view.js`, `web/explorer.js`, `web/index.html`)**:
  - Updated `#workspaceTreeSearch` placeholder to `"Filter sessions..."`, wrapped `.tree-session-title` cleanly up to 2 lines, and removed the redundant inline `Artifacts` / `Uploads` sub-list under active tree items.
  - Made `.visuals-strip-grid` responsive (`248px` at `>=1100px`, `210px` at `680–1099px`, `145px` mobile), switched `.thumb-lbl` to `overflow-wrap: anywhere`, renamed `Grid` $\rightarrow$ `Per Sheet`, replaced unselected `"✓"` badges with an empty ring, and hover-revealed `.gallery-zoom-btn` (`⤢`) on fine-pointer desktops.
- **Missing `Jan` Month Header & `Year` `24h daily` Bar-Chart Alignment (`web/heatmap.js`, `src/agy_nexus/stats.py`, `src/agy_nexus/stats_series.py`, `web/charts.js`)**:
  - Fixed `computeHeatmapMonthCols()` so `dayOfM === 1` (`Jan 1`) overrides a partial prior-month stub sharing column `0` (`Dec 29–31`), restoring all 12 month headers (`Jan`..`Dec`) on `2026 · 53 WEEKS`.
  - Fixed `build_base_slot_grid()` and `stats.py` so `Year` (`ytd` & `last_year`) always emits `24h daily` bins across the full selected Year calendar span (`Jan 1 – Nov 19` / `52w`) instead of truncating to `12H BINS`, and added `ytd` showcase export support.

## [3.2.3] — 2026-11-18

### Added
- **Two-Tier Proportional Execution Lifecycle (`src/agy_nexus/handoff_templates.py`, `src/agy_nexus/handoff.py`, `src/agy_nexus/inventory.py`)**:
  - Smart `execution_mode="auto"` resolution selecting `"fast"` for `release_closeout` and compact non-security `bug_or_visual_fix` handoffs (`< 6,500` chars) while preserving `"plan"` for `feature_update`, `new_project`, large specs, and any security/auth/deadbolt boundary changes (`touches_security_boundary()`).
  - Extracted `handoff_templates.py` (`128L`) emitting a streamlined **Tier 1 Surgical Fast-Path Lifecycle** (direct Main-Chat `Gemini 4 Carbon` inspection/editing + `pytest`/`--self-test` without multi-subagent ceremony on `<= 3` non-security files) vs. the **Tier 2 Full 4-Step Execution Lifecycle + Intra-Google Dual-Review**.
  - Tightened `_resolve_skill_directives` so `dual-review` only auto-injects for `release_closeout`, `publish_to_github`, or genuine security/auth/deadbolt scope.
- **Byte-Bounded Praxis `polyglot_map` (`src/agy_nexus/polyglot_index.py`, `src/agy_nexus/tools_praxis.py`)**:
  - Added `max_bytes: int = 17500` (`< 20 KB` on-wire budget), grouped `"directory_summary"` stats (`dir`, `files`, `lines`, `symbols`), progressive symbol-prioritized trimming, `truncated` flag, and `drilldown_hint`.
- **Real Depersonalized HTML, Workspace & ASCII Showcase (`scripts/export_depersonalized_showcase.py`, `web/demo_snapshot.js`, `docs/assets/*.png`)**:
  - Created repeatable `scripts/export_depersonalized_showcase.py` (`494L`, zero cleartext private strings; deterministic SHA-256[:12] aliasing and sparse `_z()` + shared-date serialization into `web/demo_snapshot.js`).
  - Exported live 4-window telemetry (`current_month`, `last_month`, `last_90d`, `last_year`), 16-project recency tree, and live Code Health; replaced flat placeholder SVGs with crisp preview captures (`web/demo_thumb_{desktop,workspace,foldable,mobile,health}.png`) registered in `PWA_ASSETS` and `web/sw.js` (`v3.2.3-b2`); refreshed `docs/assets/{dashboard,workspace}-{desktop,mobile}.png` and all four `README.md` ASCII showcase blocks (`get_session_tree`, `default`, `quick`, `rich`).
- **Autouse `pytest` Isolation & Regression Suites (`tests/conftest.py`, `tests/test_v323_wire_caps_fastpath_and_isolation.py`, `tests/test_v323_showcase_privacy_and_compaction.py`)**:
  - Isolated `cfg.STATE_FILE`, `AG_BRIDGE_STATE_FILE`, and in-place `SESSION_STATE` across `pytest` runs and expanded test coverage to **95 `pytest` tests** including zero-leak sub-token hash scans, UUID leak checks, PWA parity, and Markdown/wire-cap bounds.

### Fixed
- **Praxis IDE Attribution & Handshake Separation in Wire Telemetry (`src/agy_nexus/telemetry_scanner.py`, `src/agy_nexus/middleware.py`, `ascii_default.py`, `ascii_rich.py`)**:
  - Fixed `detect_product_name()` to evaluate Praxis/local IDE signals (`doorway == "praxis"`, `praxis`/`polyglot` tokens, `polyglot_*`/`praxis_*` tool names) before generic `"http-client"`/`"google"` User-Agent matches, classifying Praxis calls as `"Antigravity IDE (Praxis MCP)"`, and updated `ascii_rich.py` / `ascii_default.py` client labels dynamically.
  - Recorded `"rpc"` and `[rpc:<method>]` labels in `middleware.py`, computing `total_recorded_calls`, `avg_kb`, `max_kb`, `total_mcp_tokens`, and `budget_compliance_pct` over real `tools/call` traffic while exposing `"protocol_handshakes"` (`calls`, `bytes`, `tokens`, `tools_list_kb`).
- **Tight `load_session_into_gemini` Compaction & Hard `< 20 KB` Wire Loop (`src/agy_nexus/hygiene.py`, `src/agy_nexus/tools_session.py`)**:
  - Fixed `_compact_markdown()` to scale proportionally under `1,800` chars instead of enforcing fixed `~1.8 KB` floors, re-compacted from raw documents, and added `_shrink_optional_payload_fields()` enforcing `<= 17.8 KB` inner JSON (`< 20 KB` wire even with 6 signed `/web/media/` URLs, `include_files`, and large untracked file lists).
- **Stale Test Slot Pruning & `< 17.5 KB` `get_session_tree` Wire Guard (`src/agy_nexus/config.py`, `src/agy_nexus/session_tree.py`, `src/agy_nexus/tools_ops.py`)**:
  - Added `prune_stale_context_slots()` removing dead `/tmp/` and unbacked synthetic test slots on state load/save and in `get_routing_telemetry()`, capped `slots` at `8` compact entries, and tightened `get_session_tree` compaction to `<= 17,500` inner JSON bytes.
- **`/web?demo=1` Offline Resilience, URL XSS Hardening & Compact `tools/list` (`web/explorer.js`, `web/app.js`, `web/charts.js`, `web/gallery_view.js`, `web/markdown_renderer.js`)**:
  - Guarded Demo Mode `viewFile()` (Queue `Read Spec` / Batch `INDEX.md`) and `handleFilesUpload()` against `401` lockouts, synced `localStorage.nexus_period` across Demo horizon switches/reloads, added intrinsic `width`/`height` + `decoding="async"` on gallery thumbnails, hardened `isSafeUrl()` against tab/control-character `javascript:`/`vbscript:`/`data:image/svg+xml` bypasses, and compacted `tools/list` from `12.2 KB` down to `~9.1 KB`.

## [3.2.2] — 2026-11-18

### Added
- **GitHub Community Standards & Documentation Sync (`CODE_OF_CONDUCT.md`, `ACCESSIBILITY.md`, `.github/ISSUE_TEMPLATE/`, `.github/PULL_REQUEST_TEMPLATE.md`, `README.md`, `AGENTS.md`, `CONTRIBUTING.md`)**:
  - Added Contributor Covenant `CODE_OF_CONDUCT.md`, comprehensive `ACCESSIBILITY.md`, YAML Issue Forms (`bug_report.yml`, `feature_request.yml`, `config.yml`), and `PULL_REQUEST_TEMPLATE.md` (`100%` GitHub Community Profile compliance), packaged in `pyproject.toml`, and refreshed `README.md`, `AGENTS.md`, `CONTRIBUTING.md`, and high-DPI `?demo=1` Workspace screenshots in `docs/assets/` to `v3.2.2`.

### Fixed
- **Strict Most-Recent-First Project & Session Ordering (`src/agy_nexus/sessions.py`, `src/agy_nexus/session_tree.py`, `src/agy_nexus/bucket_api.py`, `src/agy_nexus/media_discovery.py`, `web/explorer.js`, `web/workspace.css`)**:
  - Normalized >6-digit ISO fractional seconds in `parse_iso_epoch` (`media_discovery.py`) for Python 3.12 compatibility and computed unified `last_updated_ts = max(db_ts, transcript_mtime, task_md_mtime, brain_dir_mtime)` in `sessions.py` alongside a dedicated sentinel query so brand-new `"0001-01-01..."` SQLite rows are never dropped behind `LIMIT`.
  - Sorted sessions strictly descending by `last_updated_ts` (`is_running` tie-breaker only; `is_pinned` kept visual) and sorted projects strictly descending by newest session or active `STAGED`/`IN_WORK` handoff timestamp in `session_tree.py` and `bucket_api.py`.
  - Updated `web/explorer.js` to display compact `.tree-age-pill` recency badges and auto-select `projects[0].sessions[0]` whenever `selected_session` is empty, missing, or older than the newest active session (preserving explicit `?session=` deep-links).
- **7-Day Media Link Docstrings (`src/agy_nexus/media.py`, `src/agy_nexus/tools_media.py`, `src/agy_nexus/tools_session.py`, `docs/WORKFLOWS.md`)**:
  - Updated stale `"30-min"` / `"30-minute"` media-link docstrings on `load_session_into_gemini`, `inspect_visual_artifacts`, and `sign_media_url` to accurately describe **7-day (`604,800s`) HMAC-signed `/web/media/` HTTPS links**, keeping the 30-minute passphrase deadbolt window distinct.
- **Session-Isolated SQLite Workspace Resolution, Markdown Rewriting & Repo-Aware ZIP Downloads (`src/agy_nexus/bucket_api.py`, `src/agy_nexus/tools_media.py`, `web/`)**:
  - Added `_resolve_session_workspace_info(conv_id)` querying SQLite `conversation_summaries` (`title`, `project_id`, `workspace_uris`) and `pick_primary_workspace_uri()` instead of the nonexistent `conversations` table or borrowing another session's `SESSION_STATE["selected_workspace"]`.
  - Updated `get_session_bucket_payload` (cap raised to `30`, returning `"scope"` and numeric `"mtime"`), `get_session_file_payload` (resolving `ws_path` from SQLite so Markdown previews rewrite both `file://` and relative repository image links), and `build_session_zip` / `/download-zip` (safely bundling both `brain:<conv_id>/` and validated `repo:<slug>/` screenshots while blocking traversal with `403` and deduplicating ZIP member names).
  - Split `handle_bucket_api_request` into helper handlers so every function stays well under `100` lines.
  - Scoped multi-select gallery keys (`scope/rel_path`) in `web/gallery_select.js` / `web/explorer.js`, added `scope` deep-link support and auth-overlay workspace guards in `web/app.js` / `web/charts.js`.
- **Expanded Workspace & Brain Screenshot Discovery (`src/agy_nexus/media.py`, `src/agy_nexus/media_discovery.py`, `src/agy_nexus/bucket_api.py`, `src/agy_nexus/bucket_zip.py`)**:
  - Upgraded `discover_visual_artifacts(limit=30, cap=40)` and added `discover_visual_buckets()` with `"category": "session" | "repo_asset"` ownership windowing so `Session Captures` shows only `brain/<conv_id>/` and active/in-window uncommitted repo captures, moving static `docs/assets/*` into a collapsed `Shared Repo Assets (M)` drawer and exposing fast `capture_count` badges in the left tree.
  - Extracted ZIP archival into `src/agy_nexus/bucket_zip.py` and discovery helpers into `src/agy_nexus/media_discovery.py` so every backend module remains comfortably under `500` lines.
- **Press-and-Glide Gallery Selection, 2/4/8 High-Res Sheets & Workspace UI Cleanups (`web/`)**:
  - Removed the broken `⬚ Drag-Select` toggle and replaced `15×15px` checkboxes with `40×40px` (`44×44px` touch) corner tap zones displaying `1, 2, 3...` selection badges, 260ms touch press-and-glide sweep selection + desktop mouse click-drag in-place (`syncGalleryDomState`), zero layout-shift sticky `.gallery-toolbar`, uncropped `16:10` `object-fit: contain` thumbnails with `WxH` dimension badges, and 2-line tail-preserving filenames.
  - Added `web/sheet_builder.js` (`2 / 4 / 8` per sheet persisted in `localStorage`, aspect-aware `MAX_EDGE=3072` canvas layout engine with direct sequential individual PNG export for `⬇ Sheets (K)` and `⬇ PNGs (N)` alongside optional `⬇ ZIP (N)` / modal `⬇ Sheets ZIP`, plus 10-file Gemini Web Share batching and preview modal), Lightbox `‹ Prev` / `Next ›` / swipe / `✓ Select` controls (`web/gallery_view.js`), and collapsible `+ Upload / Paste` header toggle + hidden empty `Uploads (0)` tree blocks (`web/explorer.js`, `web/workspace.css`).

## [3.2.1] — 2026-11-16

### Fixed
- **Fix [COMPLETED] Ticket Labels & Bounded Historical Display in Session Tree (`src/agy_nexus/session_tree.py`, `docs/WORKFLOWS.md`, `web/styles.css`)**:
  - Fixed `render_ascii_session_tree` to render completed handoff tickets as `[✓ COMPLETED]` instead of falsely falling through to `[⊘ SUPERSEDED -> newer]`.
  - Updated `_attach_handoffs_to_groups` to keep 100% of active `STAGED` and `IN_WORK` tickets visible while bounding historical closed (`COMPLETED` + `SUPERSEDED`) tickets at a clean recent window (4 most recent closed tickets per project) and rendering `(+N older completed)` when truncated, protecting the 20 KB MCP wire budget while keeping total project counts accurate.
  - Added visual styling for `.hier-handoff-row.is-completed` and `.hier-handoff-badge.completed, .hier-handoff-pill.completed` in `web/styles.css`.
- **Fix Remote Tag Semantic Version Comparison in Code Health (`src/agy_nexus/code_health.py`)**:
  - Fixed `_fetch_remote_version()` to collect candidate versions from both GitHub `/releases/latest` and `/tags` and select the highest valid semantic version tag, rather than exiting early on an older GitHub Release (`v2.7.0`).
  - Resolves false `Staged Locally` warnings on tag-pushed releases like `v3.2.0`.
- **Workflow Baseline Documentation (`docs/WORKFLOWS.md`)**:
  - Documented the four distinct ticket badges, closed-ticket bounding rules in `get_session_tree`, and highest-semver release/tag comparison across Workflow 1 and Workflow 2.

## [3.2.0] — 2026-11-15

### Added
- **Plain-Language Workflow Baselines & Handoff Quality Evaluator (`src/agy_nexus/workflow_baseline.py`, `src/agy_nexus/virtual_uris.py`, `src/agy_nexus/tools_session.py`, `docs/WORKFLOWS.md`)**:
  - Extracted modular `src/agy_nexus/workflow_baseline.py` (211L <= 500L) providing `discover_project_workflows()`, `format_workflow_baseline_for_wire()`, `evaluate_handoff_quality()`, and `extract_user_intent_from_handoff()`.
  - Added `workflow:baseline` virtual URI in `virtual_uris.py` for direct read-only inspection.
  - Integrated plain-language `project_workflows` baseline into `load_session_into_gemini` and wire compaction (<20 KB budget).
  - Authored authoritative `docs/WORKFLOWS.md` baseline documenting the 5 core user journeys (voice/mobile status queries, plain-language handoffs, multi-posture analytics, 2-pane workspace explorer, in-place retirement).
- **Plain-Language Handoff Modes & Non-Blocking Quality Advisories (`src/agy_nexus/handoff.py`, `src/agy_nexus/config.py`)**:
  - Replaced legacy modes (`intent`, `surgical_audit`, `visual_critique`) with 4 plain-language stage modes: `feature_update` (default), `new_project`, `bug_or_visual_fix`, `release_closeout` with backward-compatible alias mapping.
  - Increased character limit warning threshold from 4,500 to 24,000 characters, ending the anti-pattern where Gemini was discouraged from providing rich user stories and context.
  - Added non-blocking `handoff_advisory` soft-linting handoffs lacking `# User Goal` or `# Workflow` headings.
  - Updated `FastMCP(instructions=...)` with plain-language, stage-specific rules.
- **Session Continuity Intent Extraction & Ticket Auto-Reconciliation (`src/agy_nexus/retirement.py`, `src/agy_nexus/handoff_queue.py`)**:
  - `extract_prior_session_baton` now extracts prior user goal and workflow context from `gemini_research_handoff.md` across session rollovers.
  - `record_session_retirement` and `reconcile_completed_tickets` now auto-transition claimed `IN_WORK` and `STAGED` tickets to `COMPLETED` whenever a session's `RETIRED.json` manifest is written.
  - Sanitized skill path directives in `inventory.py` to prevent instructing agents to `view_file` on `(unresolved: ...)` skill placeholders.

## [3.1.0] — 2026-11-15

### Added
- **Unified 42px Studio Topbar, Shared D1–D4 Scaling & Collapsible Workspace Sidebar (`web/index.html`, `web/styles.css`, `web/app.js`, `web/explorer.js`)**:
  - Invariant 42px single-row studio topbar (`AGY-NEXUS v3.1.0`) with compact sidebar toggle button `◧` visible ONLY when Workspace is active and hidden on Analytics.
  - Non-wrapping center cluster (`Month | Quarter | Year` · `Current | Rolling` · `‹ [Span] ›` · `Steps | Tokens`) on viewports >= 780px; renamed `To Date` / `TD` to `Current` across all surfaces.
  - Shared `[data-density="D1|D2|D3|D4"]` token scaling across Analytics and Workspace; removed `min-height` on stage (`height: auto`).
  - 34px Unified Stage Header Bar (`[← Bucket] project / filename.md (size) [HTML|Raw|Print|Zen|Copy]`) and 34px compact inline upload dropzone strip.
  - Collapsible Workspace Sidebar (240px Left Tree <-> 38px Slim Rail with initial pills & handoff jump <-> 0px Zen Mode); mobile slide-over drawer with `box-shadow: none` when closed.
- **Single-Hue `#2563eb` Blue Heatmap Ramp & Mobile KPI Scaling (`web/styles.css`, `web/app.js`)**:
  - Unified 5-level single-hue `#2563eb` blue ramp across all 4 themes (`Pure White`, `Warm Paper`, `Dark Paper`, `Obsidian`).
  - Locked 7-row Mon–Sun alignment between `.heatmap-days` and `.heatmap-grid`.
  - Added mobile `26w | 53w` toggle button defaulting to `26w` on small viewports (< 560px).
  - 2×2 mobile KPI grid layout on `< 780px`.
- **Multi-Select Gallery, Bulk .zip Endpoint, Web Share API v2 & Contact Sheet (`web/gallery_select.js`, `src/agy_nexus/bucket_api.py`)**:
  - Extracted `web/gallery_select.js` (257L <= 260L) with multi-selection state, Shift+Click range, Select/Deselect All, and drag marquee.
  - Sticky bulk action bar: Web Share API v2 (`shareToGemini`), `<canvas>` Contact Sheet clipboard copy, bulk `.zip` download, and individual PNG downloads.
  - Added `POST /web/api/sessions/{conv_id}/download-zip` in `bucket_api.py` with path traversal validation and in-memory streaming.
- **Canonical PWA Deep Links & Verified Request Origin Resolution (`src/agy_nexus/media.py`, `web/manifest.webmanifest`, `web/app.js`)**:
  - Fixed origin resolution: reject 12-hex container hostnames, prioritize `_VERIFIED_REQUEST_ORIGIN`, tolerate query parameters like `?hl=en-US`.
  - Added `workspace_url` to visual artifacts and updated PWA manifest with `handle_links: "preferred"` and `launch_handler`.
  - Deep link handler in PWA supporting authenticated direct jump and unauthenticated in-app media viewer fallback with unlock button.
- **In-Place Terminal Session Closeout & Deterministic 5-Phase Suggested Actions (`src/agy_nexus/retirement.py`, `src/agy_nexus/handoff.py`, `src/agy_nexus/session_status.py`, `src/agy_nexus/config.py`)**:
  - Extracted `src/agy_nexus/retirement.py` (177L <= 220L) providing terminal session retirement (`RETIRED.json`), prior-session baton extraction, cleanup directives (`git worktree prune`), and closeout step-cap exemption (`session_continuity="closeout"`).
  - Added `retire_session: bool = False` to `send_handoff_and_resume` (85L <= 95L).
  - Job-first 1-tap `Yes` `suggested_actions` transitions (`ready_to_run`, `in_flight`, `ready_to_ship`) integrated into FastMCP instructions and `/web#workspace` `RETIRED` posture badge.

### Fixed
- **PWA Asset Registry, Responsive Topbar, Foldable KPI Grid & Hierarchy Polish (`src/agy_nexus/web_routes.py`, `web/styles.css`, `web/app.js`, `web/explorer.js`, `web/hierarchy.js`)**:
  - Added `"gallery_select.js"` and HTTP `HEAD` support to `PWA_ASSETS` in `web_routes.py` plus an automated `index.html` $\leftrightarrow$ `PWA_ASSETS` / `sw.js` `SHELL_NAMES` parity test (`test_pwa_assets_and_shell_names_integrity`).
  - Prevented vertical button wrapping in `.topbar`, hid navigation controls while `#authOverlay` is locked, enforced a single-row primary mobile topbar (`<= 780px`), and preserved 4-across KPI cards on unfolded foldables (`>= 781px`).
  - Wired `26w | 53w` heatmap buttons to re-render immediately, sliced `26w` at clean Monday boundaries without clipping `Mon–Sun` labels, replaced raw 36-char UUIDs in Hierarchy rows with compact 8-char click-to-copy pills, and synchronized `#navWorkspaceBadge` with active staged/in-work tickets.
- **Markdown & Breadcrumb Bug Fixes (`web/markdown_renderer.js`, `src/agy_nexus/bucket_api.py`)**:
  - Fixed `__MK_TOKEN_N__` token leak in markdown links wrapping inline code via multi-pass token restoration.
  - Stripped HTML metadata comments (`<!--[\s\S]*?-->`) in Editorial HTML view mode.
  - Real project and repository breadcrumb resolution across Explorer and stage header bar.

---

## [3.0.1] — 2026-11-14

### Added
- **Strict 2-Pane Finder Workspace Layout (`web/index.html`, `web/styles.css`, `web/explorer.js`)**:
  - Eliminated redundant 4-layer navigation by removing `#workspaceControls` from topbar and removing duplicate `.artifacts-dual-layout` / `.artifacts-sidebar` middle column.
  - Replaced with a single Left Tree (`288px`) and Full-Width Right Stage (`minmax(0, 1fr)`).
  - Added mobile `☰ Tree` drawer toggle button at `<= 820px` with backdrop dismissing.
  - Left Tree displays `◈ Handoffs Queue` showing active (`STAGED` + `IN_WORK`) count, collapsible `▸ + N older sessions` per project, and child branches (`Uploads` and `Artifacts`) only under the selected session.
  - 4 full-width Right Stage modes: `overview`, `batch`, `doc`, and `queue`.
  - Added compact inline upload strip (`padding: 10px 12px`) with drag/drop, file browse, Ctrl+V paste, and batch labeling.
  - Added native `<dialog id="lightboxModal">` with zoom preview and 1-click absolute 7-day link copying.

### Fixed
- **Markdown Sanitizer Wiping Entire Content (`web/markdown_renderer.js`)**:
  - Added `"article"`, `"section"`, `"header"`, `"svg"`, `"path"`, `"rect"`, `"circle"`, `"line"`, `"polyline"`, `"polygon"`, `"g"`, `"defs"`, `"marker"`, `"text"` to `ALLOWED_TAGS` and DOMPurify config.
  - Added SVG attributes (`viewbox`, `d`, `fill`, `stroke`, etc.) to `ALLOWED_ATTRS`.
- **Media Signer Broken URLs Across Container Restarts (`src/agy_nexus/media.py`, `src/agy_nexus/bucket_api.py`, `src/agy_nexus/uploads.py`)**:
  - Supported relative URL signing (`/web/media/...`) for session bucket and upload responses.
  - Client-side link copier now safely prepends `window.location.origin` for domain-invariant sharing.
- **52-Week Heatmap Overflowing Horizontal Scrollbar (`web/styles.css`, `web/app.js`)**:
  - Replaced fixed column widths with fluid `grid-template-columns: repeat(var(--week-cols, 53), minmax(0, 1fr))` with `aspect-ratio: 1/1` and trailing month label.
- **Foldable Topbar Multi-Row Wrapping (`web/styles.css`, `web/app.js`)**:
  - Hid `.brand-sub` on viewports `<= 1100px`, tightened topbar padding, disabled forward stepper at `offset <= 0`, and hid "Today" button when `offset === 0`.
- **Average Bin Metric Calculation in Hourly Plots (`web/app.js`)**:
  - Corrected `avgBin` formula in Model and Subagent plots to divide tokens by active bins when `metric === "tokens"` and calls/steps when `metric === "calls"`.
- **Handoff Ticket ID Symmetrical Decoration (`src/agy_nexus/handoff_queue.py`)**:
  - Symmetrically populated both `ticket_id` and `handoff_id` with real `<repo-slug>-NN` slugs.

---

## [3.0.0] — 2026-11-14

### Added
- **Overwatch Dashboard & Primary Surface Switcher (`web/index.html`, `web/styles.css`, `web/app.js`)**:
  - Added primary topbar surface switcher toggling between **`Analytics`** (`#analytics`) and **`Workspace`** (`#workspace` with real-time unclaimed staged ticket badge).
  - Implemented dynamic center horizon controls (`Month | Quarter | Year` · `To Date | Rolling` · `‹` `[Active Label]` `›` `Today` · `Steps | Tokens`) with date-offset stepper arithmetic and today snap.
  - Consolidated Color Surface (`Obsidian`, `Dark Paper`, `Warm Paper`, `Pure White`), Compactness (`D1–D4`), PWA App Install, and Lock Bridge into a popover Settings menu (`#settingsPopover`).
- **52-Week Muted Heatmap & Divisor-of-24 Adaptive Slot Binning (`src/agy_nexus/stats.py`, `src/agy_nexus/stats_series.py`, `web/charts.js`)**:
  - Full 52-week heatmap invariant emitting 52–53 weeks (Jan 01–Dec 31 for `to_date`, 52 weeks ending on anchor for `rolling`), highlighting `in_window: true`, muting out-of-window activity (`0.26` opacity), and marking future calendar days as hollow cells with tightened 1.5px grid gaps.
  - Emitted 1h base slots on `/web/api/stats` for Month and Quarter (`24h` for Year). Adaptive binning selects factors of 24h (`3h`/`4h` for Month, `8h`/`12h` for Quarter, `48h`/`72h` for Year) with zero bar gaps below 9px pitch.
- **Compact Tabular Legends & Handoff Lifecycle Transitions (`web/app.js`, `web/hierarchy.js`, `src/agy_nexus/handoff_queue.py`)**:
  - Replaced tall cards under Plots 1 & 2 with compact 24px-row borderless tabular legends (`[Swatch + Name] | Tier | Share vs Target micro-bar | Calls | Tokens | Avg | P95 | Peak`) with `+N inactive` collapse and click-to-solo.
  - Added a 1-line clickable Project Swatch Strip beneath Plot 3 (`[■ google-nexus 27.8%] ...`) to solo project shades.
  - Renamed filter pills to `Active & Attached`, `All in Period`, and `+ Dormant`.
  - Added `reconcile_completed_tickets` to auto-transition claimed `IN_WORK` tickets to `COMPLETED` once their session finishes running or rolls over, collapsing completed tickets under `▸ Completed Handoffs (N)`.
- **Rendered HTML Workspace Explorer & Quiet UI Editorial Reader (`src/agy_nexus/bucket_api.py`, `src/agy_nexus/web_routes.py`, `web/explorer.js`, `web/markdown_renderer.js`)**:
  - Built Hierarchical Workspace Explorer with human-names-only left tree (`Visual Handoffs Queue` node + `Project Name -> Session Title -> Uploads / Artifacts`) and dual-area right pane.
  - Added expandable sub-session child branches in left tree for `Uploads (N)` (listing date-stamped batches `📂 YYYY-MM-DD HH:MM · label (N)`) and `Artifacts & Handoffs (M)`.
  - Implemented cross-project `Visual Handoffs Queue` board with 1-click `Copy Praxis Command` and `View Specification`.
  - Upgraded upload batch cards with clickable 7-day image thumbnails, 1-click `Copy Evaluation Prompt`, and `Open INDEX.md`.
  - Implemented Quiet UI Editorial HTML markdown reader with Tufte Booktabs, task check badges, GFM callouts, syntax-highlighted copy blocks, Mermaid diagrams, parsed handoff metadata banner, DOMParser-based XSS sanitization, and 3 view modes.
  - Extended default media token expiration to 7 days (`604800s`) in `src/agy_nexus/media.py`.
- **Continuity-Aware Rollover Engine (`src/agy_nexus/session_status.py`, `src/agy_nexus/handoff.py`)**:
  - Added multi-metric continuity analyzer evaluating session step count, compactions, open task items, uncommitted git changes, and clean seams across 5 postures: `FRESH` (0–319), `SEAM_AWARE` (320–699), `HOLD_FOR_COMPLETION` (700–949), `CLOSEOUT_ONLY` (950–1149), and `HARD_ROLLOVER` (>=1150 or compactions>=7).
  - Added `session_continuity: "auto" | "continue" | "new"` parameter to `send_handoff_and_resume` and updated legacy `get_session_context_budget()` thresholds to `GREEN (<500 steps)`, `AMBER (500-749 steps)`, and `ROLLOVER_RECOMMENDED (>=750 steps or context exceeded)`.
- **Modular Architecture Refactoring (`src/agy_nexus/bucket_api.py`, `src/agy_nexus/web_routes.py`, `src/agy_nexus/code_health.py`)**:
  - Extracted `bucket_api.py` (449L) and `web_routes.py` (229L) from `middleware.py`, keeping `middleware.py` at 407L.
  - Added repository-wide modular hygiene scanner with `git status --porcelain` integration and a dedicated Watchlist & Exceptions view filter.

---

## [2.9.0] — 2026-11-14

### Changed
- **Sequential Read-Only Governance & Multi-Hop Inspection (`config.py`, `tools_session.py`, `tools_workspace.py`, `tools_ops.py`, `hygiene.py`, `skills/agy-nexus-stats/SKILL.md`)**:
  - Replaced the blanket one-tool-call-per-turn ban with Sequential Read-Only Governance (1 call at a time, up to 4 hops/turn), eliminating unnecessary multi-turn round-trips for read-only inspections while strictly prohibiting parallel simultaneous calls that cause UI confirmation card hangs.
  - Updated FastMCP server instructions to clearly document sequential non-parallel execution rules, bundling best practices, and preserved hard stops on `send_handoff_and_resume` and `LOCKED_RESPONSE`.
  - Removed `"STOP AND REPLY TO USER NOW: Do NOT chain a second MCP tool"` across read-only tool responses (`unlock_sessions`, `list_saved_sessions`, `load_session_into_gemini`, `ask_workspace_readonly`, `inspect_git_diff`, `get_session_tree`, `manage_background_run`, `list_models_and_agents`).
  - Updated pagination hints in `slice_file_content` (`next_range_hint`) and `slice_git_diff` (`pagination_hint`) to permit sequential same-turn paging (`via a sequential follow-up call if needed—never in parallel`).

### Fixed
- **Cross-Repository Slot Isolation & Guardrails (`routing.py`, `tools_workspace.py`, `tools_media.py`)**:
  - Fixed a slot-isolation bug where calling `ask_workspace_readonly` or `inspect_visual_artifacts` with an explicit `workspace` but no `session_identifier` inherited `selected_session` and clobbered that session's `active_contexts` slot and `session_workspace_map` with the foreign workspace.
  - Implemented `_session_matches_workspace()` to verify whether `selected_session`'s canonical workspace/URIs match the target workspace; if they differ, `conv_id` is cleared to `""` for that ad-hoc read so unrelated running sessions are never mutated.

---

## [2.8.0] — 2026-11-13

### Added
- **Internal Workstation MCP Doorway Renamed & Expanded to `agy-praxis-mcp` (`tools_praxis.py`, `tools_polyglot.py`, `middleware.py`, `server.py`, `config.py`)**:
  - Paired **Nexus** (external cloud bridge for Google Gemini) with **Praxis** (`FastMCP("agy-praxis-mcp")`), the zero-trust LAN/localhost execution doorway mounted at `/praxis/{PRAXIS_MCP_TOKEN}/mcp` (plus `agy-praxis-mcp --stdio`) while maintaining zero-downtime backward compatibility on `/polyglot/{POLYGLOT_MCP_TOKEN}/mcp`.
  - Expanded the local doorway to 6 tools: `polyglot_map`, `polyglot_search`, `polyglot_outline`, `praxis_handoff_inbox`, `praxis_claim_handoff`, and `praxis_update_handoff`, plus `praxis:map|search|handoffs` virtual URIs.
- **Repo-Prefixed Incremental Handoff Queue & Lifecycle Tracking (`handoff_queue.py`, `handoff.py`, `routing.py`)**:
  - Replaced single-file global staging overwrite (`latest_gemini_handoff.md`) with `fcntl.flock`-guarded repo-prefixed monotonic tickets (`<repo-slug>-01`, `<repo-slug>-02`, ...) in `sidecar_data/ag-bridge-bg/staged_handoffs/`.
  - Implemented explicit **`STAGED`** *(unclaimed / new chat)*, **`IN_WORK`** *(claimed by IDE `conversation_id` or woken headlessly)*, **`SUPERSEDED`** *(auto-marked when re-staging the same repo + topic while unclaimed)*, and **`COMPLETED`** lifecycle states.
  - Added IDE disambiguation (`AMBIGUOUS_MULTIPLE_STAGED` when 2+ unclaimed tickets match a workspace vs. auto-claim when 1 matches), strict cross-repo `RESUME_STAGED` isolation (`NO_STAGED_HANDOFF_FOR_REPO`), and `_resolve_session_identifier("<repo-slug>-NN")` resolution to claimed IDE sessions.
- **Dashboard Hierarchical Tree Handoff Integration (`session_tree.py`, `stats_series.py`, `web/hierarchy.js`, `web/styles.css`, `web/demo_data.js`)**:
  - Surfaced `STAGED`, `IN_WORK`, and `SUPERSEDED` handoff rows and header count badges (`◈ STAGED`, `▶ IN-WORK`, `⊘ SUPERSEDED`) directly inside the Row 5 **Project $\rightarrow$ Chat $\rightarrow$ Session Hierarchical Tree** (`#hierarchyProjectList`) and 76-col ASCII tree—auto-promoting and expanding brand-new zero-session projects with unclaimed handoffs.
- **Unified 4-Surface Perceptual Color System & Multi-Hue Sequential Heatmap (`web/palettes.js`, `web/styles.css`, `web/charts.js`, `web/index.html`)**:
  - Replaced green/blue-clustered plot colors and the clashing GitHub-green heatmap with `PRAXIS_MASTER_SLOTS`—a uniform 10-hue alternating Cool $\leftrightarrow$ Warm perceptual OKLCH palette shared across Model, Subagent, and Project plots, paired with a polarity-aware 4-stop multi-hue sequential heatmap (`--heat-0..4`) tuned for **Obsidian**, **Dark Paper**, **Warm Paper**, and **Pure White**.

---

## [2.7.0] — 2026-11-11

### Security
- **Zero-Trust LAN-Only `agy-polyglot-mcp` Endpoint & Incremental Index Sandboxing (`middleware.py`, `polyglot_index.py`, `polyglot_outline.py`, `hygiene.py`, `config.py`)**:
  - Enforced constant-time 192-bit token verification (`hmac.compare_digest` via `POLYGLOT_MCP_TOKEN` or domain-separated `HMAC-SHA256(PATH_SECRET, "agy-polyglot-mcp-v1")`) on `/polyglot/{POLYGLOT_MCP_TOKEN}/mcp`, failing closed (`503`) if unconfigured.
  - Enforced strict LAN-only `403 Forbidden` rejection whenever reverse-proxy/tunnel headers (`X-Forwarded-For`, `X-Real-IP`, `Forwarded`, `CF-Connecting-IP`, `X-Forwarded-Proto`, `X-Forwarded-Host`), browser `Origin` headers, non-local `Host` headers (preventing DNS rebinding), or non-RFC1918/loopback client IPs are present.
  - Hardened index cache permissions (`0700` directory, `0600` atomic temp-swap files), centralized `is_sensitive_filename()` exclusion (`secrets.env`, `.env.*`, `mcp_config.json`, private keys/tokens), redacted inline YAML scalar values during outlining, blocked relative `..` escape and umbrella root (`$HOME`, `/`, `~/gitlab`, `~/github`) indexing, and ensured `try/finally` read-only SQLite connection cleanup across all session and telemetry scanners.

### Added
- **Unified Incremental SHA-256 Polyglot Engine & Paired Local `agy-polyglot-mcp` Server (`polyglot_outline.py`, `polyglot_index.py`, `tools_polyglot.py`, `middleware.py`, `server.py`)**:
  - Replaced `ast_outline.py` completely with a unified Polyglot semantic outliner & incremental `(mtime_ns, size)` + `sha256` JSON workspace index supporting Python, JS/TS/JSX/TSX, Vue, Markdown, JSON/JSONC, YAML, Go, Rust, Shell, SQL, HTML, and CSS/SCSS with `L<start>-L<end>` spans, 1-liner docstrings/comments, and `>100`-line function warnings.
  - Exposed a dedicated deadbolt-free local MCP server (`agy-polyglot-mcp`) mounted at `/polyglot/{POLYGLOT_MCP_TOKEN}/mcp` (plus `--stdio` CLI entrypoint) providing `polyglot_map`, `polyglot_search`, and `polyglot_outline` for Antigravity IDE agents alongside `agy-nexus-mcp`.
- **Virtual URI Routing (`virtual_uris.py`, `workspace.py`, `workflows.py`)**:
  - Added `transcript:latest`, `transcript:turn:<K>`, and `transcript:step:<N>` reading untruncated turns from `.system_generated/logs/transcript_full.jsonl` with `<= 136`-char line wrapping for clean `start_line`/`end_line` pagination.
  - Added nested `brain:<subpath>` / `brain:<conv_id>/<subpath>` resolution, `polyglot:map[:prefix]` / `polyglot:search:<query>`, and policy-safe read-only `telemetry:stats[:period[:style]]` / `telemetry:quota` / `telemetry:wire` / `telemetry:export_notebook` URIs.
- **Pragmatic `<= 500` Line Modular Budget & `/web` Polyglot Health Telemetry (`hygiene.py`, `code_health.py`, `web/health.js`, `web/demo_data.js`, `web/charts.js`)**:
  - Updated target file budget from `<= 300`/`400` to **`<= 500` lines** (`501–650` warning, `650` hard ceiling, functions `<= 100` lines), eliminating artificial micro-file sprawl while keeping semantic navigation instant via Polyglot outlines.
  - Added deterministic `?demo=1` / `?theme=` / `?period=` URL query overrides on `/web` and upgraded Row 6 (**Code Health, Polyglot Index & Modular Hygiene**) plus all 3 ASCII telemetry tiers with live Polyglot symbol counts and `<= 500L` / `650L` margin reporting.

### Fixed
- **MCP Streamable HTTP `405 Method Not Allowed` Spec Compliance & Async Event-Loop Offload (`middleware.py`, `server.py`)**:
  - Returned `405 Method Not Allowed` (`Allow: POST, OPTIONS`, `Cache-Control: no-store`, `X-Accel-Buffering: no`) on `GET`, `DELETE`, and `HEAD` to `*/mcp` per the MCP Streamable HTTP specification, multiplexed lifespans with `finally` cleanup across both FastMCP apps, and offloaded synchronous MCP tool functions via `anyio.to_thread.run_sync` (`is_async = True`) with `timeout_keep_alive=65`.
- **Policy-Safe Telemetry & Session Stats (`tools_ops.py`, `skills/agy-nexus-stats/SKILL.md`)**:
  - Added `include_stats: bool = False`, `period`, and `style` directly to `get_session_tree()`, eliminating hosted Gemini `POLICY_DECISION_DENY` blocks on `manage_background_run`.
- **Read-Only Slice Performance & Pinned-Session Search (`hygiene.py`, `workspace.py`, `inventory.py`, `search.py`, `tools_workspace.py`)**:
  - Separated `hit_char_cap` from `truncated` so explicit `start_line`/`end_line` slices skip full-file outlining, guarded `resolve_customization_file` against multi-segment/wildcard globs, bounded multi-repo grep to `3.2s` monotonic wall-clock (`1.5s`/repo) across `~/gitlab`, `~/github`, and worktrees, and added Tier-0 pinned session `transcript_full.jsonl` + `brain/` search.
- **Headless Chained Publish Mode, `RESUME_STAGED` Unwrap & `"Google Nexus"` Routing (`handoff.py`, `sessions.py`, `routing.py`, `tools_session.py`, `stats.py`)**:
  - Defaulted `execution_mode="auto"` (`"fast"` when `allow_chained_publish=True` and `resume_headless=True`, else `"plan"`), propagated host-bridge wakeup failures accurately (`status="FAILED"`), added `_unwrap_staged_handoff_markdown` (`<!-- BEGIN_USER_HANDOFF_BODY -->`) to prevent `RESUME_STAGED` double-wrapping, narrowed `NEXUS_TITLE_KEYWORDS` so `"Google Nexus"` chats never hijack `workspace_path`, mapped `NEXUS_PROJECT_ID` (`a97e4c10-2600-4a91-8b2c-1e75c90a0301`) cleanly to `agy-nexus-mcp`, dynamically expanded `latest_assistant_response` up to `10,500` chars from `transcript_full.jsonl`, and prioritized SQLite `conversation_summaries` over stale cached slots.
- **High-Detail Visual Thumbnails & Public HTTPS Media Origin (`tools_media.py`, `docker-compose.yml`)**:
  - Raised 2-up `inspect_visual_artifacts` `max_edge` to `840px` (`min_quality=58`), added `zoom_warning` guidance for `count > 2` full-frame views, documented hosted Gemini `ImageContent` stripping, and wired `AG_BRIDGE_PUBLIC_URL` + `${HOME}/github:ro` into `docker-compose.yml`.

---

## [2.6.0] — 2026-11-11

### Security
- **Host Companion Bridge Zero-Trust Authentication & Loopback Hardening (`CWE-306`, `CWE-88` — `host_bridge/bridge_security.py`, `host_bridge/agy_host_bridge.py`, `systemd/agy-host-bridge.service`, `src/agy_nexus/config.py`)**:
  - Changed default `HOST_BRIDGE_BIND_HOST` from `0.0.0.0` to `127.0.0.1` across `agy_host_bridge.py`, `systemd/agy-host-bridge.service`, `.env.example`, and setup wizards (`init_secrets.py`, `setup.sh`, `setup.ps1`), eliminating unintended LAN exposure on port `8098`.
  - Enforced mandatory constant-time `X-Bridge-Token` authentication (`hmac.compare_digest` against 256-bit `HOST_BRIDGE_TOKEN` or domain-separated `HMAC-SHA256(PATH_SECRET, "agy-host-bridge-agentapi-v1")`) on every `POST /agentapi` call, failing closed (`503` / startup exit) if unconfigured and returning `401` on missing/invalid credentials.
  - Added defense-in-depth peer CIDR filtering (`HOST_BRIDGE_ALLOWED_CIDRS=127.0.0.0/8,::1/128,172.16.0.0/12`), browser `Origin` rejection (`403`), `OPTIONS` rejection (`405`), strict `Content-Type: application/json` validation (`415`), and a `1 MB` `Content-Length` ceiling (`413`).
  - Removed `Path.home()` (`$HOME`) and `/` from `resolve_allowed_git_roots()` across both `git-inspect` and `new-conversation` (restricting strictly to `AGY_GITLAB_DIR` and `AGY_DATA_DIR/worktrees`), serialized `app_storage.json` updates under an atomic lock, and added `sanitize_git_ref`, `sanitize_conv_id`, and `guard_cli_positional` to prevent `git` and `agentapi` CLI option injection (`CWE-88`). Thanks to Shiqiang Chen (Independent Researcher) for responsible disclosure.

### Added
- **Two-Step Headless Confirmation Gate & `/web` Session Scratch Batch Uploads (`src/agy_nexus/handoff.py`, `src/agy_nexus/uploads.py`, `web/uploads.js`, `src/agy_nexus/middleware.py`)**:
  - Defaulted `send_handoff_and_resume(..., resume_headless=False)` to write-only staging (`status="STAGED_ONLY"`) with zero-reupload `RESUME_STAGED` override support.
  - Added multi-file, drag-and-drop, and clipboard-paste session scratch batch uploads (`POST /web/api/sessions/<conv_id>/upload`) generating timestamped `scratch/uploads_YYYYMMDD_HHMMSS/` directories with `INDEX.md` manifests and HMAC-signed `/web/media/` image links.
- **Universal Polyglot Structural Outliner (`src/agy_nexus/polyglot_outline.py`, `src/agy_nexus/ast_outline.py`, `src/agy_nexus/workspace.py`)**:
  - Implemented standalone companion outliner module (`polyglot_outline.py`, 248 lines, zero external dependencies) providing exact `L<start>-L<end>` line-span outlines across non-Python formats.
  - **Markdown (`.md`, `.mdx`)**: Extracts heading tree (`#` through `######`) with calculated section line spans up to equal/higher level headings or EOF, plus fenced code block summaries (`[code:<lang> L<start>-L<end>]`).
  - **JSON / JSONC (`.json`, `.jsonc`)**: Parses top-level and 2nd-level keys, reporting value types (`str`, `int`, `float`, `bool`, `dict[N keys]`, `list[N items]`) and sampling array-of-object keys (`list[N items] of {k1, k2, ...}`) while stripping JSONC comments gracefully.
  - **YAML (`.yaml`, `.yml`)**: Pure-stdlib indentation/sequence parser safe against Home Assistant custom tags (`!include`, `!secret`, `!env_var`), mapping top-level keys and 2nd-level entries/named items (`- alias: ...`, `- id: ...`, `- name: ...`) with line spans.
  - **JavaScript / TypeScript / CSS / HTML (`.js`, `.mjs`, `.ts`, `.tsx`, `.jsx`, `.css`, `.html`)**: Extracts imports, brace-depth tracked declarations (`function`, `async function`, `class`, methods, `const/let <name> = (...) =>`, `export`), CSS rule blocks (`@media`, `@keyframes`, `:root`), and major semantic HTML tags.
  - Unified `build_file_outline` in `ast_outline.py` to seamlessly dispatch non-Python files to `polyglot_outline.py`, powering both explicit `outline:<path>` queries in `ask_workspace_readonly` and automatic outline attachment on truncated file reads.
- **Automated Session "Baton-Pass" & Context Rollover (`src/agy_nexus/handoff.py`, `src/agy_nexus/session_status.py`, `src/agy_nexus/tools_session.py`)**:
  - Added `context_budget` telemetry to `execution_status` (`"GREEN (<250 steps)"`, `"AMBER (250-350 steps)"`, `"ROLLOVER_RECOMMENDED (>350 steps or context exceeded)"`), backed by `check_context_exceeded` scanning transcript turns for `"Context window exceeded"`.
  - Implemented automatic **Prior Session Baton** extraction (`extract_prior_session_baton`) from the previous session's brain directory (`task.md` completed tasks, `walkthrough.md` highlights, and `git status --short`), prepending a `## Prior Session Baton (<prev_id>)` block to the new session's `gemini_research_handoff.md` and inline wakeup prompt.
  - Implemented automated session promotion from `create_new_session=False` to `create_new_session=True` (`auto_rollover_from: <prev_id>`) when targeting sessions with `>= 380` steps or `"Context window exceeded"`, eliminating dead-end mega-session crashes.

---

## [2.5.0] — 2026-11-09

### Fixed
- **Gemini Mobile MCP Tool Collisions & Same-Turn Fallback (`tools_session.py`, `tools_ops.py`, `tools_workspace.py`, `config.py`)**:
  - Designated `load_session_into_gemini` and `ask_workspace_readonly` as the primary tools for routine session "Check-in" and status checks, resolving client-side `permission_denied` policy blocks triggered on Gemini mobile by the `manage_*` verb.
  - Designated `manage_background_run` specifically for `action='stats'`, `'telemetry'`, `'sessions'`, or `'export_notebook'`.
  - Refined the strict 1-MCP-tool-per-turn rule across all tool docstrings and `assistant_guidance`: while chaining a second MCP call after a successful response remains prohibited (to prevent UI connection hangs), Gemini is now explicitly permitted to invoke `ask_workspace_readonly` or `load_session_into_gemini` once as an automatic same-turn fallback whenever a call encounters `permission_denied` or an immediate error, eliminating conversational stalls.
- **`sendMessage` Path Shadowing & Absolute Path Resolution (`src/agy_nexus/handoff.py`)**:
  - Updated `sendMessage` payload construction in `send_handoff_and_resume` to use the exact absolute `handoff_file` path (`str(handoff_file)`) rather than relative `scratch/gemini_research_handoff.md`, preventing path resolution failures when sessions switch working directories.
  - Embedded `send_prompt_body` directly in the `sendMessage` payload (up to `2,500` characters), ensuring follow-up task instructions are immediately visible in the active session context.
- **Session Brain Scratch Isolation & Root Shadow File Elimination (`src/agy_nexus/hygiene.py`)**:
  - Removed untracked repo-root `scratch/` and `task.md` shadow files from the repository root.
  - Updated `MODULAR_HYGIENE_STANDARDS` and `MODULAR_HYGIENE_MARKDOWN_BLOCK` to mandate storing temporary scratch scripts and notes strictly inside the session brain directory (`~/.gemini/antigravity/brain/<conv_id>/scratch/`), explicitly forbidding repository-root `scratch/` directories that could shadow handoff files.
- **Local Service Reload Clarification During Stage & Preview (`src/agy_nexus/handoff.py`)**:
  - Clarified `stage_gate_block` and `sendMessage` gate directives: while `allow_chained_publish=False` prohibits `git push`, `publish_to_github.py`, and remote production stack redeployments, it explicitly mandates restarting the local `ag-bridge-mcp` service/container on the local host whenever Python or web files change so updates take effect in memory immediately.

---

## [2.4.1] — 2026-11-09

### Added
- **3-Mode Middleman Protocol & Gemini High Task (Spark) PM Workflow (`src/agy_nexus/handoff.py`, `ag_bridge.py`, `README.md`)**:
  - Added `handoff_mode: str = "intent"` (`"intent"` | `"visual_critique"` | `"surgical_audit"`), `allow_chained_publish: bool = False`, and `force_interrupt: bool = False` to `send_handoff_and_resume()`.
  - Enforced the **3-Mode Middleman Protocol**: `intent` for clean requirements/user-flow briefs without guessing unverified implementation mechanics; `visual_critique` for grounded UX/visual delta critiques anchored to `visual-architecture-system`; and `surgical_audit` for verified file fixes only after inspecting code with read-only tools.
  - Documented Gemini High Task Mode (formerly Spark) Project Manager orchestration: systematic multi-step sequencing (scouting context $\rightarrow$ staging & previewing handoffs $\rightarrow$ inspecting visual/diff gates $\rightarrow$ approving release).
  - Enforced the **Two-Phase Safety Gate (`allow_chained_publish=False` default)**: blocks premature `git push`, `publish_to_github.py`, and container redeployments in mutation turns, requiring artifact/diff verification first.
- **Content-Aware Skill Auto-Router & 4-Step Subagent Protocol (`src/agy_nexus/inventory.py`, `src/agy_nexus/handoff.py`)**:
  - Implemented `_resolve_skill_directives(workspace_str, activate_skills, research_markdown)` automatically scanning handoff markdown for domain triggers:
    - **UI / Frontend** (`\.(html|css|js|tsx|vue)\b` or keywords `ui|css|layout|table|chart|hierarchy|drawer|modal|screenshot|theme|redesign`): auto-attaches `visual-architecture-system` and `modern-web-guidance`.
    - **Container / Stack** (`docker-compose|portainer|StackGitRedeploy|container`): auto-attaches `portainer-gitops`.
    - **Release / Auth / Security** (`publish_to_github|release|security|deadbolt|auth`): auto-attaches `dual-review`.
  - Enforced the **Mandatory 4-Step Subagent Lifecycle** (`flash-scout` $\rightarrow$ `flash-surgeon` / `argon-surgeon` $\rightarrow$ `flash-auditor` $\rightarrow$ `Visual & Preview Gate`) in both the `agentapi` wakeup prompt and `gemini_research_handoff.md` footer, eliminating headless subagent starvation and enforcing Rule 8.1 (no solo code signoff).
- **In-Flight Handoff Mutex & Session Compaction Telemetry (`src/agy_nexus/session_status.py`, `src/agy_nexus/tools_session.py`, `src/agy_nexus/sessions.py`)**:
  - Created `src/agy_nexus/session_status.py` with `check_inflight_handoff_mutex()` returning `status="ALREADY_RUNNING"` with `active_job_id` and `elapsed_seconds` when a background job started `< 300` seconds ago, eliminating duplicate wakeup collisions across multi-turn handoffs.
  - Added binary transcript compaction scanning (`count_session_compactions`) detecting `# Resuming from a compaction` and active execution step pacing (`calculate_step_pacing`) excluding idle inter-turn gaps.
  - Integrated `session_health_warning` into `load_session_into_gemini` and `list_saved_sessions`, alerting when `step_count > 1500` or `compaction_count >= 10` and advising clean conversation rotation via `create_new_session=True` before Cortex tool amnesia occurs.
- **Native AST Symbol Outliner, Caller Reference Counter & Undefined-Name Verifier (`src/agy_nexus/ast_outline.py`, `src/agy_nexus/workspace.py`, `src/agy_nexus/tools_workspace.py`, `src/agy_nexus/search.py`)**:
  - Created `src/agy_nexus/ast_outline.py` (`<= 240` lines, zero external dependencies, MIT-compatible) keeping `agy-nexus-mcp` at **10 tools total** while embedding 1-call symbol discovery directly inside `ask_workspace_readonly`:
    - **Python (`ast`)**: Extracts module imports, classes, methods, and `def`/`async def` signatures with exact line spans (`L024-L068 def _resolve_skill_directives(...) -> list[str]`), plus an automatic two-pass lexical scope **undefined-name / broken-import check** (`check_python_undefined_names` / `scan_package_undefined_names`).
    - **JS / TS / HTML / CSS / YAML**: Extracts exported functions, classes, DOM `#id` containers, CSS selectors, and top-level YAML keys with exact line numbers.
    - **Caller Reference Counter (`find_symbol_callers`)**: Attaches `git grep -n -w` caller counts and top `file:line` references when outlining files or searching symbol identifiers.
    - **1-Call `outline:` Prefix & Auto-Truncation Outlines**: Supports `file_subpath="outline:src/agy_nexus/handoff.py"` for full symbol/caller maps and automatically attaches a compact `< 1.5 KB` `ast_outline` whenever a source file read is truncated (`total_lines > shown_end_line`).
- **Hybrid `oraios/serena` (Local LSP Subagents) + `ast_outline` (Remote Gemini MCP) Architecture (`agents/*.md`, `src/agy_nexus/handoff.py`, `README.md`)**:
  - Integrated `oraios/serena` (`serena-agent`, `--context=antigravity`) for local Antigravity subagents (`flash-scout`, `flash-surgeon`, `flash-auditor`), pairing Serena's local LSP symbolic navigation/editing (`get_symbols_overview`, `find_symbol`, `find_referencing_symbols`, `replace_symbol_body`) with `ast_outline.py` for remote Gemini Web/Mobile MCP sessions.
- **Installed vs. Published GitHub Release Telemetry & Code Health Engine (`src/agy_nexus/code_health.py`, `src/agy_nexus/stats.py`, `src/agy_nexus/ascii_default.py`, `src/agy_nexus/ascii_rich.py`, `src/agy_nexus/session_tree.py`, `web/`)**:
  - Created `src/agy_nexus/code_health.py` (241 lines <= 250) providing non-blocking GitHub latest release/tag comparisons against [`github.com/FrankXLT/agy-nexus-mcp`](https://github.com/FrankXLT/agy-nexus-mcp) with a 3600s disk cache (`github_release_cache.json`), 2.0s socket timeout, and offline fallback.
  - Distinctly categorizes and renders 3 version states: `Up to Date`, `Update Available`, and `Staged Locally` (`v2.4.1 > v2.4.0`).
  - Surfaced installed version (`v2.4.1`) in ASCII telemetry across 40-col `quick`, 72-col `default`, 76-col `rich` views, and the 76-col session tree header.
  - Implemented **Row 7: Code Health, AST Integrity & Modular Hygiene** in the `/web` Quiet UI dashboard, featuring a 6px status dot in the topbar brand title, 4 summary KPI cards, and a clean tabular module breakdown tracking file line budgets (`<=300L`, `301-400L`, `>400L`), live AST undefined-name counts, and local Serena LSP readiness.
- **Modular Architecture & File Hygiene**:
  - Modularized session status logic into `src/agy_nexus/session_status.py` (205 lines), AST symbol outlining into `src/agy_nexus/ast_outline.py` (214 lines), and code health telemetry into `src/agy_nexus/code_health.py` (241 lines), keeping all 25 package modules strictly `<= 357` lines (hard ceiling `<= 400` lines).

### Fixed
- **Missing `discover_visual_artifacts` Import in `load_session_into_gemini` (`src/agy_nexus/tools_session.py`, `src/agy_nexus/server.py`)**:
  - Restored `from .media import discover_visual_artifacts` in `tools_session.py`, eliminating the runtime `NameError` when calling `load_session_into_gemini`, and added both an end-to-end `load_session_into_gemini` assertion and a package-wide AST undefined-name scan (`scan_package_undefined_names`) to `ag_bridge.py --self-test`.
- **Explicit `workspace_path` Pinning on `create_new_session=True` & Stateless Worker Context Restoration (`src/agy_nexus/handoff.py`, `src/agy_nexus/config.py`, `src/agy_nexus/tools_session.py`)**:
  - Fixed `send_handoff_and_resume(create_new_session=True)` so an explicitly passed or extracted `eff_workspace_path` takes priority over the project's default first repo in `bridge_response.get("workspace_path")`.
  - Updated `load_session_into_gemini` and `pin_session_context` to restore pinned `workspace`, `project_id`, and `title` from `SESSION_STATE["active_contexts"][conv_id]` across stateless HTTP workers.

---

## [2.4.0] — 2026-11-07

### Added
- **Parallel Session Isolation & Atomic Keyed Context Slots (`src/agy_nexus/config.py`, `src/agy_nexus/tools_session.py`, `src/agy_nexus/tools_workspace.py`)**:
  - Upgraded `session_state.json` persistence with `fcntl.flock` file locking and atomic temp-file `os.replace()`, storing per-conversation context slots (`active_contexts[conv_id]`) and routing telemetry counters (`pinned_calls`, `auto_resolved_calls`).
  - Added stateless per-call context pinning (`session_identifier`, `workspace`) to `ask_workspace_readonly` and `inspect_git_diff` so two or more Gemini Web / Gemini Mobile tabs can operate concurrently on different sessions and repositories without overwriting each other's active workspace.
- **3-Tier Smart Path Resolver (`src/agy_nexus/workspace.py`)**:
  - Upgraded `_resolve_and_read_files()` with 3-tier path resolution: Tier 1 (Explicit Pin + multi-root `extra_workspace_uris`), Tier 2 (Repo-Prefix Match under `AGY_GITLAB_DIR` when `file_subpath` begins with `<repo_name>/...`), and Tier 3 (Unique Subpath Auto-Discovery across top-level repositories in `AGY_GITLAB_DIR`, returning `auto_resolved_workspace`).
- **Same-Repo Concurrent Writer Guard (`src/agy_nexus/sessions.py`, `src/agy_nexus/handoff.py`)**:
  - Extended `_get_selected_session_quick_status()` and `send_handoff_and_resume()` to detect when another session is `RUNNING` against the same `workspace_path`, computing session `mode` (`MAIN WRITER`, `WORKTREE`, `SHARED (READ-ONLY)`, `MAIN TREE`) and surfacing a `concurrent_writer_warning` recommending `use_worktree=True`.
- **76-Column ASCII Project, Chat & Session Hierarchy (`src/agy_nexus/session_tree.py`, `src/agy_nexus/tools_ops.py`)**:
  - Added first-class `@mcp.tool def get_session_tree(...)` and `manage_background_run(action="sessions" | "session_status")`, rendering a copy-ready 76-column ASCII hierarchy (`Project -> Chat -> Session ID -> Workspace -> Status`) alongside 3-2-1 backup sync status (`read_backup_321_manifest()`).
- **Unified `/web` Project, Chat & Session Hierarchy Panel (`web/hierarchy.js`, `web/index.html`, `web/app.js`, `web/styles.css`)**:
  - Added the full-width `col-12` **Project, Chat & Session Hierarchy** card to `/web` with live `3-2-1 SYNC: <short_sha> ✓` badge, `SLOTS / PINNED / AUTO-RESOLVED` telemetry badge, `[Pinned / Active | All Sessions]` toggle, `Copy ASCII Tree` button, collapsible project cards with `SHARED REPO` badge, 1-click `📋` copy buttons on `project_id`, `session_id`, chat title, and `workspace`, and live running/pinned badges in `#workspaceTableBody`.
- **Automated 3-2-1 Git Synchronization & Depersonalized Documentation (`scripts/backup_321_sync.py`, `README.md`, `docs/assets/`)**:
  - Added `scripts/backup_321_sync.py` to synchronize GitHub (`origin/main`), local GitLab (`gitlab/main`), and a verified offline `git bundle` (`agy-nexus-mcp-latest.bundle` + SHA-256 `backup_manifest.json`).
  - Added 100% depersonalized 76-column `get_session_tree` and 3-tier ASCII telemetry examples to `README.md` alongside refreshed headless Chrome CDP `/web` screenshots (`docs/assets/dashboard-desktop.png`, `docs/assets/dashboard-mobile.png`).

---

## [2.3.4] — 2026-11-05

### Fixed
- **Unified Time-Series Alignment & Local Timezone Bucketing (`src/agy_nexus/telemetry_scanner.py`, `src/agy_nexus/stats.py`, `web/charts.js`, `web/app.js`)**:
  - **Local Timezone Conversion (`TZ` / `America/New_York`)**: Converted `transcript.jsonl` UTC timestamps (`...Z`) to local timezone before bucketing into 4h slots (`to_4h_slot`), eliminating the `+5h` UTC offset that shifted evening coding sessions after `7:00 PM EST` into tomorrow's date and excluded future 4h slots later today from dragging the right edge of today's chart line to zero.
  - **Locked X-Axes Across All 3 Time-Series Charts**: Removed independent per-chart leading-zero slicing (`firstNonZero` in `web/charts.js` and `firstIdx` in `web/app.js`) and the 14-day October backfill on `current_month`, ensuring `Activity Over Time`, `Subagent Activity Over Time`, and `Project Activity Over Time` share the exact same X-axis start/end timestamps and vertical spike positions in every period tab.
  - **Exact Period-Scoped Project & Subagent Totals**: Unified `ws_map` and `ws_slots` (including `"unassigned"`, subagent steps, and an `"other-projects"` / `"other-subagents"` 6th layer for items `#6..#N`), filtered `subagent_role_breakdown` and `model_usage_vs_target` strictly to the active date window (`s_iso <= d_str <= e_iso`), removed `_smooth_series` peak distortion, and added title-aware workspace resolution (`_pick_primary_workspace`) for multi-URI conversations.
- **Single-Call-Per-Turn Gemini Web Guardrail & Auto-Bundled Context (`src/agy_nexus/config.py`, `tools_session.py`, `tools_workspace.py`, `tools_ops.py`, `hygiene.py`)**:
  - Enforced the strict `1 MCP Tool Call Per Turn` rule across `mcp.instructions` and all `assistant_guidance` strings to prevent Google Gemini Web's Connected Apps UI from freezing on `"Trying to connect..."`, while upgrading `ask_workspace_readonly` to auto-read the top 4 matched files from `code_search_matches` and `list_saved_sessions` to bundle `top_session_detail` in a single call.

---

## [2.3.3] — 2026-11-04

### Fixed
- **Strict `< 20 KB` Wire-Budget Enforcement Across Chained Tool Calls (`src/agy_nexus/hygiene.py`, `tools_session.py`, `tools_workspace.py`, `tools_ops.py`)**:
  - Removed the `if not has_inc` bypass in `load_session_into_gemini` so calls passing `include_files` are still bounded by the `< 19,000`-byte progressive compaction guard instead of emitting `40+ KB` payloads that stall Gemini Web's Cloud MCP proxy when chaining multiple tool calls in a single turn.
  - Added `< 19,200`-byte (`<= 20,480` bytes on the wire) progressive compaction guards to `ask_workspace_readonly` and `list_models_and_agents`, and tuned `MAX_FILE_CHARS` (`14,000`) and `MAX_TOTAL_FILE_CHARS` (`16,500`).
- **Web Overwatch PWA Deadbolt Unlock Fix (`web/charts.js`, `web/app.js`, `web/index.html`, `web/sw.js`)**:
  - Fixed a commented closing brace (`// 0 = Mon .. 6 = Sun }`) in `web/charts.js` that prevented `charts.js` from loading `renderDashboard`, updated `fetchStats()` error handling so network/parse errors are surfaced instead of silently entering `demoMode`, and added `node --check` + brace validation to `ag_bridge.py --self-test`.
- **3-Tier ASCII Telemetry Renderer Polish (`src/agy_nexus/ascii_default.py`, `src/agy_nexus/ascii_rich.py`)**:
  - Added explicit numeric column headers (`M T W T F S S (0-5+ runs)`) and legends to the 35-day activity heatmaps, switched `compact` (`38-col`) to a stacked 2-line per-model layout so `0%` bars never clip on mobile viewports, and exposed both `total_calls` and `avg_wire_bytes` on the `MCP BRIDGE` line.

---

## [2.3.0] — 2026-11-03

### Added
- **Clean Modular Package Architecture (`src/agy_nexus/`)**:
  - Decomposed the 2,730-line monolithic `ag_bridge.py` and 7 loose root helper files into 19 cohesive domain modules inside `src/agy_nexus/` (`config`, `hygiene`, `inventory`, `telemetry_scanner`, `ascii_default`, `ascii_rich`, `stats`, `workflows`, `sessions`, `routing`, `search`, `workspace`, `tools_session`, `tools_workspace`, `tools_ops`, `handoff`, `middleware`, `server`, `__init__`), keeping every module within the `100–340 line` modular budget (`< 400 lines` hard ceiling).
  - Retained a 51-line backward-compatible `ag_bridge.py` root shim so existing Docker Compose, `systemd`, and CLI invocations continue working with zero breaking changes.
- **Modular Web Overwatch PWA (`web/`)**:
  - Split the 1,913-line `web/index.html` into `web/index.html` (`341 lines`), `web/styles.css` (`113 lines`), `web/charts.js` (`302 lines`), and `web/app.js` (`358 lines`), registered in `BridgeCompatMiddleware` and `web/sw.js`.
- **Autonomous Multi-File Research & Generous Context Window Pool (`src/agy_nexus/hygiene.py`, `src/agy_nexus/search.py`)**:
  - Raised `MAX_FILE_CHARS` to `48,000` (`~1,200 lines`), `MAX_TOTAL_FILE_CHARS` to `120,000` (`~3,000+ lines`), `MAX_FILES_PER_CALL` to `12`, and `MAX_TASK_DOC_CHARS` to `24,000`.
  - Replaced rigid equal division (`MAX_FILE_CHARS // len(paths)`) with a dynamic shared `120,000`-character pool across up to 12 files per `ask_workspace_readonly` call so Gemini can read entire multi-file subsystems in a single turn without mid-task permission prompts.
- **Bundled 8-Agent Orthogonal Roster (`agents/`) & Governance Docs**:
  - Added portable, depersonalized agent definitions in `agents/*.md` (`flash-scout`, `argon-architect`, `flash-surgeon`, `argon-surgeon`, `flash-auditor`, `argon-sentinel`, `claude-specialist`, `claude-sentinel`, `pool-failover`, `image-generator`).
  - Added `AGENTS.md`, `CHANGELOG.md`, `SECURITY.md`, and `CONTRIBUTING.md`.
- **GNU AGPLv3 + Section 7 Attribution & Security-Integrity Terms (`LICENSE`, `NOTICE`)**:
  - Licensed under GNU AGPLv3 (`SPDX-License-Identifier: AGPL-3.0-or-later`) with Section 7 attribution, origin notice preservation, and security-gate integrity protection.

---

## [2.2.0] — 2026-11-02

### Added
- **3-Format Live ASCII Telemetry (`get_quota_and_system_stats`)**:
  - Added `format_type="default"` (`44-col` mobile-first Unicode blocks `░▒▓█`), `format_type="compact"` (`38-col` dense HUD card), and `format_type="desktop"` (`78-col` side-by-side matrix with 7-day rolling window).
  - Added per-surface client detection (`Gemini Mobile`, `Gemini Web`, `Antigravity IDE`, `Headless CLI`) via User-Agent and heuristic tool-call fingerprinting.
- **Manifest V3 Chrome Extension (`chrome-extension/`)**:
  - Added Side Panel + Popup companion extension (`manifest.json`, `background.js`, `panel.html`, `panel.js`, `panel.css`) with native Web Speech API voice passphrase unlock, 1-click session resume, and copyable ASCII telemetry cards.
- **5 Cross-App Workflow Accelerators (`src/agy_nexus/workflows.py`)**:
  - `audit_multi_repo_drift`: Cross-repo dependency, schema, and dirty-tree drift scanner.
  - `export_notebook_bundle`: Deduplicated SHA-256 Markdown knowledge bundles for NotebookLM and Gemini Gems.
  - `capture_thought_to_workspace`: Append timestamped mobile voice notes and tasks into any repository (`docs/MOBILE_INBOX.md` or `task.md`).
  - `triage_recent_failures`: Instant log/trace and git regression correlate-and-triage bundle.
  - `generate_standup_digest`: Multi-repo git commit + Antigravity session standup generator.

---

## [2.0.0] — 2026-11-01

### Added
- **AGY-Nexus Overwatch PWA (`web/`)**:
  - Added responsive Desktop + Mobile glassmorphic telemetry dashboard at `/web` with SVG dual-pool quota gauges, 14-day stacked token charts, 35-day activity heatmap, and one-tap Deadbolt Lock/Unlock controls.
- **Dual-Pool Quota Pacing & Antigravity Inventory (`src/agy_nexus/inventory.py`, `src/agy_nexus/routing.py`)**:
  - Added real-time monitoring of Google 20x Ultra (`Gemini 4 Argon`, `Gemini 3.8 Flash`) and Weekly Partner Pool (`Claude Sonnet 5.5`, `Claude Opus 5.5`, `GPT-OSS 120B`) with automated failover routing.

---

## [1.0.0] — 2026-10-31

### Added
- Initial release of **AGY-Nexus MCP** (`ag-bridge-mcp`) with 3-Layer Security (`SUBDOMAIN_HASH`, 192-bit `PATH_SECRET`, and Voice-Normalized SHA-256 Spoken Passphrase Deadbolt with sliding TTL), SQLite session discovery (`list_saved_sessions`, `load_session_into_gemini`), read-only workspace research (`ask_workspace_readonly`, `inspect_git_diff`), and headless Language Server handoff (`send_handoff_and_resume`, `manage_background_run`).
