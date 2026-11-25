# Changelog

All notable changes to **AGY-Nexus MCP** (`agy-nexus-mcp`) are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [4.0.9] — 2026-11-24

### Added & Improved
- **Wave 4 `develop` Pricing Soak, `16 MiB` Feed Cap, Token Floor & Node 24 Workflow Actions (`catalog_sync.py`, `scripts/catalog_sync.py`, `tools_ops.py`, `web/v9/v9_catalog_banner.js`, `.github/workflows/{ci,catalog-sync,publish-mcp}.yml`)**:
  - Raised the upstream `models.dev` feed parse cap in `scripts/catalog_sync.py` to `16 MiB` (`16 * 1024 * 1024` bytes) while keeping stored `model_catalog.json`, `cost_ledger.json`, and `catalog_override.json` `<= 256 KB`, and guarded `apply_numeric_feed_updates` so lower feed limits never downgrade higher curated `public_api` context/output token ceilings (`262,144` on Carbon/Neon/Hydrogen) while still recording verified USD/1M rate deltas as dated `rate_epochs`.
  - Added strict `{"main", "develop"}` upstream branch resolution (`AGY_CATALOG_BRANCH` -> local `develop` checkout -> fail-closed `"main"`) in `catalog_sync.py`, exposed `upstream_branch` in `/web/api/catalog/status` and `tools_ops._collect_runtime_model_audit`, invalidated stale branch caches automatically, updated `v9_catalog_banner.js` branch labeling, and made `.github/workflows/catalog-sync.yml` branch-aware (`bot/catalog-sync-develop` -> `develop` vs `bot/catalog-sync` -> `main`, scoped `develop` push trigger, and branch-isolated concurrency).
  - Upgraded all deprecated Node 20 GitHub Actions across `ci.yml`, `catalog-sync.yml`, and `publish-mcp.yml` to verified Node 24 tags (`actions/checkout@v6`, `actions/setup-python@v6`, `actions/setup-node@v6` `node-version: "24"`, `docker/setup-qemu-action@v4`, `docker/setup-buildx-action@v4`, `docker/login-action@v4`, `docker/build-push-action@v7`), enabled GitHub Actions PR approval permissions (`can_approve_pull_request_reviews: true`), and synced `.github/README.md`, `src/agy_nexus/data/README.md`, `CONTRIBUTING.md`, and `docs/WORKFLOWS.md`.
- **Wave 3 Anti-Injection Schema Validator, Path-Locked Catalog Bot & Process READMEs (`.github/README.md`, `src/agy_nexus/data/README.md`, `src/agy_nexus/data/schemas/*.schema.json`, `src/agy_nexus/catalog_validator.py`, `catalog_sync.py`, `.github/workflows/{ci,catalog-sync}.yml`)**:
  - Added Draft 2020-12 JSON Schemas (`model_catalog.schema.json`, `cost_ledger.schema.json`) with `"additionalProperties": false` and integer/regex bounds alongside zero-dependency pure-Python `catalog_validator.py` (`<= 256 KB` payload cap, `NaN`/`Infinity`/duplicate-key rejection, `https://`-only vendor host allowlist + anti-SSRF guard, anti-XSS/bidi/control/Markdown-injection checks) wired into `catalog_sync.py` (`load_active_override_pair`, `get_catalog_sync_status`, `accept_catalog_override`), `load_model_catalog` fallback-on-corrupt-override, `scripts/catalog_sync.py --validate-strict`, `ci.yml` (`verify`), and `catalog-sync.yml` (`git diff --name-only` path allowlist gate restricting bot PRs strictly to `model_catalog.json`, `cost_ledger.json`, and `docs/PRICING_HISTORY.md`), plus co-located contributor guides in `.github/README.md`, `.github/PULL_REQUEST_TEMPLATE.md`, and `src/agy_nexus/data/README.md`.
- **Two-File Price Book Ground Truth, 1-Click `/web` Update Banner & `catalog_override.json` (`src/agy_nexus/data/model_catalog.json`, `src/agy_nexus/data/cost_ledger.json`, `src/agy_nexus/catalog_sync.py`, `src/agy_nexus/catalog_report.py`, `src/agy_nexus/model_pricing.py`, `src/agy_nexus/web_routes.py`, `web/v9/v9_catalog_banner.*`, `docs/PRICING_HISTORY.md`)**:
  - Added monotonic `catalog_revision` + `updated_at` to `model_catalog.json` and partitioned each model cleanly into `public_api` vs. locked `antigravity_ide` (`placeholders`, `tier_placeholders`, IDE `context_window` / `max_output_tokens`, `pool_key`, `target_pct`), while extracting effective-dated `rate_epochs` with `source_url` and `verified_at` into repo-tracked `src/agy_nexus/data/cost_ledger.json` and deterministic `docs/PRICING_HISTORY.md` rendering (`scripts/catalog_sync.py --render-docs`).
  - Added 24h fail-open upstream check against protected `main`, git-checkout SHA-256 edit detection, calm `/web` disclosure banner (`Price Book rev <N> available`, native `<dialog id="v9CatalogDiffDialog">` diff preview, `[Accept Update]` writing atomically `0600` to `${AGY_DATA_DIR}/catalog_override.json` strictly behind passphrase auth `/web/api/catalog/{status,accept,reset}`, `[Reset Override]`, auto-retirement when repo catches up, and static showcase suppression).
- **Intended-vs.-Actual Subagent Adjudication & Unmapped `M*` Barcode Alert (`telemetry_scanner.py`, `stats_series.py`, `stats_aggregator.py`, `stats_metrics.py`, `stats.py`, `tools_ops.py`, `web/v9/v9_analytics.js`)**:
  - Fixed `resolve_subagent_model()` so `model: inherit` subagents (`claude-sentinel`, `claude-specialist`) inherit parent main-chat model execution instead of role-name guessing, bumped `CACHE_VERSION = 9` to retain explicit transcript model receipts alongside unrecognized raw model codes (`unmapped_models`), and surfaced Intended-vs.-Actual pills (`Intended: Sonnet 5.5 · Ran: 84% Carbon 4 (inherited)`) across `list_models_and_agents`, `stats`, and `390px`/`900px`/`1440px` `/web` Subagent Workload rows—plus 1-click GitHub Issue reporting for unmapped `M*` barcodes.
- **Wave 1 Heatmap Precision, Grayscale Contrast Boost & Automated Bot/CI PR Workflows (`web/v9/v9_heatmap.js`, `web/v9/v9_shell.css`, `web/v9/v9_analytics.css`, `.github/workflows/ci.yml`, `.github/workflows/catalog-sync.yml`, `CONTRIBUTING.md`)**:
  - Shipped matched-lightness `--v9-heat-out-1..4` out-of-window grayscale tokens boosted `8–10%` further from `--v9-heat-out-0` across all 4 themes (`Pure White`, `Warm Paper`, `Dark Paper`, `Obsidian`), `1px` stepped calendar month dividers, thin soft-red `.is-selected` ring with metric-pinned keyboard navigation, protected-`main` `ci.yml` (`verify` check), and weekly fail-closed `bot/catalog-sync` PR automation (`scripts/catalog_sync.py`).

## [4.0.8] — 2026-11-24

### Added & Improved
- **Public GHCR OCI Container & `--stdio` Transport Mode (`Dockerfile`, `.dockerignore`, `src/agy_nexus/server.py`, `src/agy_nexus/config.py`, `src/agy_nexus/hygiene.py`, `ascii_models.py`, `stats_aggregator.py`, `middleware.py`, `code_health.py`)**:
  - Added slim `python:3.12-slim` `Dockerfile` (`git`, `grep`, `pip install --no-cache-dir .`, `EXPOSE 8765`, `ENTRYPOINT ["agy-nexus-mcp"]`, `io.modelcontextprotocol.server.name="io.github.FrankXLT/agy-nexus-mcp"`, `org.opencontainers.image.source`) and `.dockerignore` excluding `.git`, `.venv`, caches, `.env*`, and `*secrets*`.
  - Implemented `--stdio` transport in `server.py` (`_offload_sync_mcp_tools(mcp)` + `mcp.run(transport="stdio", show_banner=False)`), bypassing HTTP-only `PATH_SECRET` checks and unset `PASS_HASH` exits with zero `stdout` banner noise and diagnostics strictly on `sys.stderr`, while hardening `verify_passphrase` / `is_unlocked` to reject empty or non-64-hex `PASS_HASH` values fail-closed.
  - Added `resolve_package_resource_dir` / `resolve_package_root` in `hygiene.py` so non-editable wheel and container installs resolve `agents/` and `web/` seamlessly, plus CI clean-`HOME` resilience across `tools_workspace.py`, `workspace.py`, and `selftest_runner.py`.
- **Official MCP Registry (`2025-12-11`) & Zero-Secret GitHub OIDC Workflow (`server.json`, `.github/workflows/publish-mcp.yml`, `pyproject.toml`, `README.md`)**:
  - Added schema-validated `server.json` (`io.github.FrankXLT/agy-nexus-mcp`, `< 100`-char description, `ghcr.io/frankxlt/agy-nexus-mcp:4.0.8` OCI `stdio` package with `--stdio` and optional secret `PASS_HASH`).
  - Added `.github/workflows/publish-mcp.yml` triggered on `push` (`v*` tags) and `workflow_dispatch` (`release_tag`), running `pytest`, `--self-test` runners, `--stdio` container smoke test, multi-arch GHCR push (`:version` + `:latest`), Sigstore `cosign` (`v4.1.2`) verification of `mcp-publisher` (`v1.8.1`), `jq` sync, `validate`, `login github-oidc`, and `publish`.
  - Added `<!-- mcp-name: io.github.FrankXLT/agy-nexus-mcp -->` + GHCR `--stdio` usage and updated stale `v4.0.6` headings to `v4.0.8` in `README.md`, added `[project.urls]` in `pyproject.toml`, and synced all 12 `agents/*.md` files (`12/12 SYNCED`).
- **Workflow Baseline, Tests & PWA Sync (`docs/WORKFLOWS.md`, `docs/DEPLOYMENT.md`, `web/`, `tests/test_v408_ghcr_stdio_and_registry.py`)**:
  - Added `Workflow 7: WF-07 — Public GHCR Container, Stdio Mode & MCP Registry OIDC Publishing` and Common Terms (`GHCR OCI Package`, `MCP Registry Manifest`, `Stdio Container Mode`) to `docs/WORKFLOWS.md`, bumped `4.0.8` (`agy-nexus-v4.0.8`), and verified full `pytest` + `--self-test` + Docker `--stdio` smoke suite.

## [4.0.7] — 2026-11-23

### Added & Improved
- **4-Gate `WF-XX` & Common Terms Workflow Engine (`docs/WORKFLOWS.md`, `workflow_baseline.py`, `workflow_gate.py`, `handoff.py`, `tools_praxis.py`, `tools_session.py`, `virtual_uris.py`, `config.py`)**:
  - Added a `Common Terms Glossary` and explicit `WF-01..WF-06` flow headings in `docs/WORKFLOWS.md` without banned terminology, and upgraded `discover_project_workflows` + `format_workflow_baseline_for_wire` so `load_session_into_gemini` and `workflow:baseline` always return `workflow_status` (`READY` vs `MISSING_BASELINE`), the complete `WF-01..WF-NN` index, and `Common Terms` within `< 20 KB` wire caps.
  - Added `workflow_ids`, `workflow_delta`, and `user_terms` parameters to `send_handoff_and_resume`, enforced all 4 plain-language workflow pre-flight gates (`NEEDS_WORKFLOW_SPEC`, `WORKFLOW_BOOTSTRAP_REQUIRED`, `HANDOFF_REJECTED_PLAIN_LANGUAGE` + `WF-XX` binding checks) while preventing `allow_chained_publish=True` from bypassing non-closeout checks, and auto-injected matched `WF-XX` sections + `Common Terms` into `scratch/gemini_research_handoff.md`.
  - Persisted `workflow_ids`, `workflow_delta`, and `docs/WORKFLOWS.md` baseline fingerprints onto staged tickets (`handoff_queue.py`) and gated `praxis_update_handoff(status="COMPLETED")` with `WORKFLOW_DOC_NOT_UPDATED` whenever `docs/WORKFLOWS.md` is left untouched on `bootstrap` / `add_new` / `update_existing` tickets.
- **Thicker Mobile/Tablet Topbar, Hourly Error-Bar Legend & Dedicated Table Legends (`web/v9/`)**:
  - Upgraded `< 680px` folded topbar ergonomics in `v9_shell.css` (`40px` Row 1 targets with `>= 40px` menu button / `18px` icon / `13px` tabs; `36px` Row 2 buttons with `>= 36px` `<`/`>` steppers; `6px` row gap; `8px 12px` padding; `0` horizontal overflow at `390px`) and expanded `680px–1099px` tablet topbar to `56px` with `36px` controls.
  - Fixed `buildCadenceWhiskerOption` (`v9_billing.js`) ECharts legend icons and `itemStyle.color` to match Teal `Min–Max Range` I-beams, Blue `Active Avg` horizontal tick/dash, and Purple `Last 24h` circles across all 4 themes.
  - Added reactive `V9.SparkBars.renderTableLegend(kind, metric)` `.v9-table-legend` swatch bars directly above Model Workload, Subagent Workload, Top Projects, and Project Sessions tables (`v9_spark_bars.js`, `v9_tables_and_rail.css`, `v9_analytics.js`, `v9_project_view.js`, `index.html`), clarified Subagent per-run text as `<avg> avg · <max> max`, and cleaned chart header subtitles.
- **Opt-In Gemini Linux VM Screenshot Audit (`config.py`, `media.py`, `retirement.py`, `tools_session.py`, `tools_media.py`, `docs/DEPLOYMENT.md`)**:
  - Added Rule 6 (`OPT-IN GEMINI VM VISUAL AUDIT`) in `mcp.instructions` and `VISUAL_INSPECTION_HINT` across `load_session_into_gemini` and `inspect_visual_artifacts` so Gemini always presents clickable 7-day `signed_url` links at zero extra token cost first and prompts via `<ElicitationsGroup>` (`Have Gemini audit screenshots in VM (uses extra tokens)`) before pulling images with the `Google-Agent` User-Agent.
  - Updated `docs/DEPLOYMENT.md` (Section 4 Step 2.3) and `docs/WORKFLOWS.md` (`WF-04`) to permit trailing query strings (`(\?.*)?`) on `/web/media/` for Gemini mobile `?hl=en-US` links over split-DNS.
- **Docs, Tests & PWA Sync**: Bumped `4.0.7` (`agy-nexus-v4.0.7`), added `tests/test_v407_workflow_gates_and_mobile_legends.py`, updated `test_v404` & version parity tests, and refreshed showcase snapshots, `docs/assets/*.png`, and verified responsive visuals (`390x844`, `820x1080`, `900x1000`, `1440x900`).

## [4.0.6] — 2026-11-23

### Added & Improved
- **Enforce `@Agy Nexus Mcp` 1-Tap `<FollowUp>` / `<ElicitationsGroup>` Reply Chips Across All Tools & Lifecycles**:
  - Added `REPLY_PROMPT_GUIDANCE` in `src/agy_nexus/config.py`, upgraded `FastMCP` Rule 5 with explicit `<FollowUp label="..." query="@Agy Nexus Mcp ..." />` and `<ElicitationsGroup>` XML syntax + required `@Agy Nexus Mcp ` prefix and exact `conversation_id` / `handoff_id` / `project_name` embedding, and updated `LOCKED_RESPONSE` with next-turn `@Agy Nexus Mcp` guidance.
  - Upgraded `build_suggested_actions()` (`src/agy_nexus/retirement.py`) to accept `handoff_id`, support the `retired` state (prioritized before `step_count >= 900`), prefix all `options` and `query` attributes with `@Agy Nexus Mcp `, embed `conv_id`/`handoff_id`/`target`, and emit `html.escape(..., quote=True)` `followup_xml` strings.
  - Wired `handoff_id=hid` and `REPLY_PROMPT_GUIDANCE` into `src/agy_nexus/handoff.py`, attached lifecycle `suggested_actions` inside `load_session_into_gemini` (`tools_session.py`), and appended `REPLY_PROMPT_GUIDANCE` across `unlock_sessions`, `list_saved_sessions`, `ask_workspace_readonly`, `inspect_git_diff`, `inspect_visual_artifacts`, `get_session_tree`, `list_models_and_agents`, and `manage_background_run`.
- **Docs, Tests & PWA Sync**: Preserved Workflows 1–6 and documented 1-tap reply-chip guidance in `docs/WORKFLOWS.md` (`v4.0.6`), bumped PWA/SW (`agy-nexus-v4.0.6`), added `tests/test_v406_reply_prompt_guidance.py`, and refreshed `demo_snapshot.js` + `README.md`.

## [4.0.5] — 2026-11-23

### Fixed
- **Workspace Gallery `All` (`Select All`) Scoped Strictly to Session Captures (`web/v9/v9_gallery.js`)**:
  - Tracked `currentSessionItems` separately from `currentVisualItems` so clicking **`All`** (`#v9GalAllBtn`) selects only active session captures (`sessionCaps`) and never silently selects collapsed **`Shared Repo Assets`** (`#v9RepoAssetsDrawer`) or inflates `"N selected"` / `PNGs` / `Contact Sheet` / `Download ZIP` exports.
  - Updated `#v9GalAllBtn` label & disabled logic so selecting all session captures immediately flips the button to **`Clear`**, and a `0`-capture session disables **`All`** unless clearing manually selected repo assets.
  - Isolated `Shift+Click` (`handleShiftSelect`) and drag/touch gestures (`bindGalleryGestures`) strictly per grid (`#v9GalGrid` vs `#v9RepoAssetsGrid`) so selection ranges never cross between session captures and shared repo assets.
- **Docs, Tests & PWA Sync**: Updated Workflow 4 & Workflow 6 (`CACHE_NAME = "agy-nexus-v4.0.5"`, `?v=4.0.5`) in `docs/WORKFLOWS.md`, added Node VM & API regression tests (`tests/test_v405_gallery_select_all_scope.py`), and refreshed `demo_snapshot.js`, `README.md`, and `build/gh-pages/` (`0` leaks).

## [4.0.4] — 2026-11-23

### Option A Hybrid Range Whiskers & Target/Seam Caret Bars + Subagent Step-Cap Alerts
- **Per-Run Outlier, Active-Day Range & Trailing 24h Backend Telemetry (`src/agy_nexus/stats_metrics.py`, `cost_ledger.py`, `stats_aggregator.py`, `stats_series.py`, `project_stats.py`, `stats.py`)**:
  - Computed exact active-day `min_daily_*`, `avg_daily_*`, `max_daily_*` (`Steps`, `Tokens`, `$ Cost`) and trailing 24-hour (`last_24h_*` + `has_last_24h`) activity across live and archived ledgers (`l24_slots`), plus session `is_retired` status from `RETIRED.json`.
  - Added per-run subagent distributions (`min_steps_per_run`, `avg_steps_per_run`, `max_steps_per_run`, `min/avg/max_tokens_per_run`, `min/avg/max_cost_per_run`, `last_run_*`, `over_120_runs`) and 24h model `last_24h_steps`/`tokens`/`cost_usd` metrics.
- **Hybrid Range Whiskers & Target/Seam Caret Bars (`web/v9/v9_spark_bars.js`, `v9_tables_and_rail.css`, `v9_analytics.js`, `v9_project_view.js`, `v9_demo_adapter.js`)**:
  - **`Top Projects (Daily)`**: Active-Day Range Whisker (`Min..Peak Day` stem, `│` crossbar at `Active-Day Avg`, `●` dot at `Last 24h` — hollow muted dot when idle in an active window, omitted in closed windows) scaled to highest table peak, reactive to `[Steps | Tokens | $ Cost]`, and sortable via `V9.TableSort`.
  - **`Subagent Workload`**: Per-Run Outlier Whisker (`Min/run..Max/run`, `│` at `Avg/run`, `●` at `Latest Run` / `Last 24h`) with amber `2.5x` burn outlier badges and fault `>120` step-cap warnings when runs exceed `120` steps (`max_steps_per_run > 120` / `over_120_runs > 0`).
  - **`Model Workload`**: Target Guide `│` + `Last 24h ▾` Caret Bar with reactive `Actual %` & `Guide / Delta` across `Steps`, `Tokens`, and `$ Cost`.
  - **`Project Sessions (Daily)`**: `320│ / 700▾` Context-Seam Caret Bar in `Steps` mode (highlighting `500+` warning / `700+` rollover alert on unretired sessions vs. muted `RET` on `RETIRED` sessions) and `Project Avg │ + Last 24h ▾` burn bar in `Tokens` / `$ Cost` modes.
- **Packaging, PWA & Docs**: Registered `v9_spark_bars.js` in `PWA_ASSETS` (`src/agy_nexus/web_routes.py`), `web/sw.js` (`CACHE_NAME = "agy-nexus-v4.0.4"`, `?v=4.0.4`), updated Workflow 6 in `docs/WORKFLOWS.md`, refreshed `demo_snapshot.js`, `README.md`, `docs/assets/`, and `build/gh-pages/` (`0` leaks).

## [4.0.3] — 2026-11-23

### Added
- **Multi-Column Sortable Analytics Tables & `Age` Column (`web/v9/v9_table_sort.js`, `web/v9/v9_tables_and_rail.css`, `web/v9/v9_project_view.js`, `web/v9/v9_analytics.js`, `src/agy_nexus/stats_series.py`, `src/agy_nexus/project_stats.py`)**:
  - Added `V9.TableSort` powering 1-click ascending/descending sorting (`<th scope="col">` buttons with `aria-sort="ascending|descending"` on the active column only and CSS-driven SVG direction arrows) across `Top Projects`, `Project Sessions`, `Model Workload`, and `Subagent Workload`.
  - Added a dedicated `Age` column on both `Top Projects` and `Project Sessions` (backed by project/session `last_updated_ts` + `relative_age` metadata and a relative-age parser fallback for demo/static snapshots), sorted across all active projects prior to slicing the top 14 while preserving ECharts series color indices.
- **Desktop Sidebar Pinning (`>= 1100px`) & Dynamic Menu Affordance (`web/v9/v9_hierarchy.js`, `web/v9/v9_state.js`, `web/v9/v9_app.js`)**:
  - Added `localStorage.nexus_v9_rail_pinned` persistence with `#v9RailPinBtn` in `.v9-rail-hdr` (`>= 1100px`) to dock `#v9NavRail` inline in `#v9AppShell.is-rail-pinned` across `Analytics` and `Workspace`, keeping the rail open across project/session switches and realigning ECharts automatically.
  - Updated `#v9MenuBtn` to render a `☰` hamburger icon when unpinned (or `< 1100px` mobile/tablet overlay mode) and a `◧` docked-panel icon when pinned on desktop, with debounced `1100px` resize synchronization.

### Fixed
- **Opus 5.5 / Sonnet 5.5 Drift Match (`scripts/check_model_drift.py`)**:
  - Pinned `_check_public_rate_feeds` filter tokens to `opus-5-5` / `opus-5.5` and `sonnet-5-5` / `sonnet-5.5`, eliminating false-positive `models.dev` `claude-opus-5` (`$5.00/$25.00`) `RATE_DRIFT` warnings against active `Claude Opus 5.5` (`$4.00/$20.00`) rates.
- **Docs & PWA Cache Sync (`docs/WORKFLOWS.md`, `web/sw.js`, `src/agy_nexus/web_routes.py`, `web/demo_snapshot.js`)**:
  - Registered `v9_table_sort.js` and `v9_tables_and_rail.css` in `PWA_ASSETS` and `web/sw.js` (`CACHE_NAME = "agy-nexus-v4.0.3"`, `?v=4.0.3`), updated Workflow 6 in `docs/WORKFLOWS.md`, and refreshed `demo_snapshot.js` + `build/gh-pages/` (`0` leaks).

## [4.0.2] — 2026-11-22

### Fixed
- **Activity Heatmap Quartiles Across Metrics (`web/v9/v9_heatmap.js`, `src/agy_nexus/stats.py`)**:
  - Replaced linear max-day threshold ratios (`0.16 / 0.38 / 0.65`) on `Tokens` and `$ Cost` with uniform empirical non-zero quartiles (`computeQuartiles`, `P25 / P50 / P75`) over active in-window days (falling back to non-future 52-week strip days when `< 4` positive days exist in window), eliminating October/early-November washout on spike days so `Steps`, `Tokens`, and `$ Cost` match `Model Workload (Daily)`.
- **Out-of-Window Desaturation & Contrast (`web/v9/v9_analytics.css`, `web/v9/v9_heatmap.js`)**:
  - Updated `.v9-heat-cell.is-out` (`filter: grayscale(0.92); opacity: 0.28;`, `0.42` for `data-level="0"`, restoring `grayscale(0.25); opacity: 0.85;` on hover) across all 4 themes (`Pure White`, `Warm Paper`, `Dark Paper`, `Obsidian`) so out-of-window cells clearly recede behind vibrant in-window days.
- **Full-Width Trailing 52w Strip & 1st-of-Month Headers (`src/agy_nexus/stats.py`, `web/v9/v9_heatmap.js`, `web/v9/v9_analytics.css`)**:
  - Anchored trailing `364`-day (`52w–53w` Mon–Sun) heatmap strip at `end_d` for both `to_date` (`MTD` / `QTD` / `YTD` / `Last Month`) and `rolling` presets without popping into `47w` or leaving a right-hand gap (`repeat(keepCols, minmax(10px, 1fr))` shared across `.v9-heat-months` and `.v9-heat-grid`, `2px` mobile gap for `<= 560px` `26w` zero-scroll fit), and anchored `buildMonthLabels(cols)` directly onto the week containing the `1st` (`"-01"`) of each month.
- **Docs, Cache & Showcase Refresh (`docs/WORKFLOWS.md`, `web/sw.js`, `web/demo_snapshot.js`)**:
  - Documented Activity Heatmap invariants in `docs/WORKFLOWS.md` Workflow 6, bumped PWA cache (`agy-nexus-v4.0.2`, `?v=4.0.2`), refreshed `demo_snapshot.js`, `build/gh-pages/` (`0` leaks), and dashboard screenshots.

## [4.0.1] — 2026-11-22

### Fixed
- **Official 4-Tier Google AI Subscription Pricing (`src/agy_nexus/data/model_catalog.json`, `src/agy_nexus/model_pricing.py`, `src/agy_nexus/ascii_models.py`, `docs/WORKFLOWS.md`)**:
  - Corrected `google_ai_ultra_20x` monthly rate from `$99.99/mo` (`99,990,000` micro-USD) to its official US price of **`$199.99/mo`** (`199,990,000` micro-USD, `30 TB` storage, `20x` Pro limits, `$100/mo` developer credits), fixing prorated window cost and break-even multiplier math in `/web`, the static GitHub Pages showcase, and ASCII billing summaries.
  - Added **`Google AI Plus`** (`google_ai_plus`, `$4.99/mo`, `4,990,000` micro-USD, `400 GB` storage, `2x Free` Gemini limits, `Hydrogen 4`) alongside `Google AI Pro` (`$19.99/mo`, `5 TB`, `$10/mo` credits) and `Google AI Ultra (5x)` (`$99.99/mo`, `20 TB`, `$40/mo` credits) in `subscription_tiers`, and exposed `pool_multiplier` and `storage` in `build_billing_comparison()`.
  - Updated `render_ascii_models_status()` (`src/agy_nexus/ascii_models.py`) to format the `SUBSCRIPTION TIERS` box row dynamically from `model_catalog.json` (`Plus $4.99 | Pro $19.99 | 5x $99.99 | 20x $199.99`) within the strict `<= 72`-char inner / `76`-col outer box budget.
- **PWA Cache & Public Showcase Refresh (`web/`, `web/demo_snapshot.js`, `web/demo_thumb_health.png`)**:
  - Bumped PWA cache & query tags (`CACHE_NAME = "agy-nexus-v4.0.1"`, `?v=4.0.1`), refreshed real-data `demo_snapshot.js` + `build/gh-pages/` (`0` leaks) + `web/demo_thumb_health.png` with accurate 4-tier break-even metrics.

## [4.0.0] — 2026-11-22

### Added
- **Quiet UI `v9.3.0` Studio Cutover as Primary `/web` App (`web/index.html`, `web/v9/*`, `src/agy_nexus/web_routes.py`, `web/sw.js`, `web/manifest.webmanifest`)**:
  - Promoted the clean-slate **Quiet UI `v9.3.0` + Apache ECharts `v5.6.0` SVG Studio** to primary live `/web` (`GET /web`, `/web/`, `/web/index.html`) while preserving `/web/v9` route and `/web/v9/*` asset compatibility with `Cache-Control: no-store`.
  - Updated `web/sw.js` (`CACHE_NAME = "agy-nexus-v4.0.0"`, `sessionStorage.nexus_sw_reloaded = "4.0.0"`) and `web/manifest.webmanifest` to precache active Studio modules (`v9/*`, `demo_snapshot.js`, `gallery_select.js`, `sheet_builder.js`) while keeping HTML uncached.
  - Added single-row sticky topbar (`<= 52px`) with invariant left navigation (`Analytics | Workspace <N>`), compound period stepper + 6-preset popover (`MTD`, `QTD`, `YTD`, `30d`, `90d`, `52w`), `[Steps | Tokens | $ Cost]` metric toggle, closed-by-default `Projects & Sessions` overlay drawer (`100vw` / `50vw` / `460px`), Dedicated Project Analytics (`src/agy_nexus/project_stats.py`), and responsive 2-bar Workspace (`100%` Docs + `[Captures (N)]` modal `< 760px`, `64%/36%` `1`-col `760–1279px`, `60%/40%` `2`-col `>= 1280px`) with `Fit | 1:1` + side-by-side **Compare** Lightbox.
- **8-Model Registry, Effective-Dated Micro-USD Cost Ledger & Subscription Break-Even (`src/agy_nexus/data/model_catalog.json`, `src/agy_nexus/model_pricing.py`, `src/agy_nexus/cost_ledger.py`, `src/agy_nexus/telemetry_scanner.py`, `web/v9/v9_billing.js`)**:
  - Cataloged all 8 live Antigravity models (`Gemini 4 Carbon`, `Neon`, `Argon`, `Hydrogen`, `Gemini 3.8 Flash`, `Claude Opus 5.5`, `Claude Sonnet 5.5`, `GPT-OSS 120B`) with effective-dated integer micro-USD rate epochs (`2026-12-01` / `2027-01-01` forecasts) and persistent `cost_ledger.json` (`CACHE_VERSION = 8`, `0600` mode) preserving historical spend even when old `brain/` chats are pruned.
  - Added active-day `Min / Avg / Max` + `Last 24h` **Activity by Hour of Day** whiskers, `Est. $` + `Avg Tok/Run` columns across tables, and the **Subscription Break-Even & Client Billing** card (`Google AI Pro`, `Ultra 5x`, `Ultra 20x`).
- **Deadbolt-Safe `76`-Col Model Matrix, 12-Subagent Sync & `01:45 AM` Drift Timer (`src/agy_nexus/ascii_models.py`, `scripts/sync_agents.py`, `scripts/check_model_drift.py`, `systemd/agy-model-drift-check.{service,timer}`)**:
  - Added `list_models_and_agents(style="ascii", include_skills=False, include_rules=False)` and `manage_background_run(action="models", style="ascii")` returning a deadbolt-safe `76`-col status matrix alongside catalog-driven `ascii_default.py` & `ascii_rich.py` renderers.
  - Expanded synced `agents/*.md` roster to 12 roles (adding `hydrogen-surgeon.md`, `neon-surgeon.md`, and `<= 120` step ceilings) with `sync_agents.py` SHA-256 verification and `01:45 AM` read-only drift monitoring (`model_drift_status.json`).
- **Zero-Leak Real-Data Static Interactive GitHub Pages Showcase (`scripts/export_depersonalized_showcase.py`, `scripts/build_github_showcase.py`, `scripts/publish_to_github.py`)**:
  - Added `scripts/build_github_showcase.py` bundling a self-contained static showcase (`build/gh-pages/` with `.nojekyll`, relative `./` asset paths, all 6 real-data window presets + `Last Month`, and 3–4 interactive Workspace sessions with rendered/raw Markdown and depersonalized PNG captures) gated by an automated `0`-leak privacy & PNG metadata scanner.
  - Wired orphan `gh-pages` branch sync and GitHub Pages REST API configuration into `scripts/publish_to_github.py` (with `--dry-run`).

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

> Older releases (`v1.0.0` – `v2.9.0`) are archived in [`docs/CHANGELOG_ARCHIVE.md`](docs/CHANGELOG_ARCHIVE.md).
