# AGENTS.md — AI Coding Assistant & Multi-Agent Architecture Guide

This document defines the modular architecture, coding standards, security invariants, and multi-agent orchestration rules for **AGY-Nexus MCP** (`agy-nexus-mcp`).

Any AI coding assistant (Google Antigravity, Gemini CLI, Claude Code, Cursor, or subagents) working in this repository **must** follow these guidelines.

---

## 1. Modular Package Architecture (`src/agy_nexus/`, `host_bridge/`, `web/`)

All server implementation code lives in `src/agy_nexus/`. The root `ag_bridge.py` file is a **75-line backward-compatible entrypoint shim** that prepends `src/` to `sys.path` and re-exports public symbols so existing Docker Compose, `systemd`, and CLI invocations continue to work without breaking changes.

### Backend & Host Bridge Module Responsibilities

| Module | Lines | Responsibility |
| :--- | :---: | :--- |
| `src/agy_nexus/__init__.py` | ~5 | Package metadata and canonical `__version__` (`3.2.5`) |
| `src/agy_nexus/config.py` | ~472 | Environment/secrets loading (`secrets.env`), `PRAXIS_MCP_TOKEN` + legacy `POLYGLOT_MCP_TOKEN` derivation, SHA-256 voice passphrase normalization, sliding-TTL Deadbolt gate, `fcntl.flock` atomic `active_contexts` slots + `prune_stale_context_slots()`, Sequential Read-Only Governance instructions, and `FastMCP` initialization |
| `src/agy_nexus/hygiene.py` | ~426 | `<= 18.5 KB` inner / `<= 19.8 KB` escaped outer `< 20 KB` progressive wire compaction (`within_wire_budget`, `compact_payload_to_wire_budget`), centralized `is_sensitive_filename()` filter, line-range file slicing (`slice_file_content`), diff pagination (`slice_git_diff`), and `<= 500L` (`650L` ceiling) modular auditing |
| `src/agy_nexus/polyglot_lang_outliners.py` | ~376 | Markup, config, and comment-summary outliners for Markdown, JSON/JSONC, YAML (with scalar redaction), HTML, and CSS/SCSS alongside shared leading-comment extractors |
| `src/agy_nexus/polyglot_outline.py` | ~290 | Unified multi-language Polyglot semantic outliner (`.py`, `.js/.ts/.tsx`, `.vue`, `.go`, `.rs`, `.sh`, `.sql`, plus re-exported markup/config outliners) with `Lstart-Lend` spans, 1-liner summaries, and `>100L` function warnings |
| `src/agy_nexus/polyglot_index.py` | ~474 | Incremental `(mtime_ns, size)` + `sha256` per-workspace JSON semantic index (`0700`/`0600` permissions) powering byte-bounded `polyglot_map` (`<= 17.5 KB` + `directory_summary`), `polyglot_search`, and `polyglot_outline` |
| `src/agy_nexus/handoff_queue_store.py` | ~199 | `fcntl.flock` atomic index storage, slugifiers (`slugify_token`, `normalize_repo_slug`, `canonicalize_handoff_id`), ticket decoration, and auto-supersede helpers |
| `src/agy_nexus/handoff_queue.py` | ~376 | Repo-prefixed incremental handoff queue (`<repo-slug>-01`, `<repo-slug>-02`...) with `STAGED`, `IN_WORK`, `SUPERSEDED`, and `COMPLETED` lifecycle states, automatic completion reconciliation, and IDE disambiguation |
| `src/agy_nexus/handoff_templates.py` | ~177 | Security-boundary classifiers (`touches_security_boundary`, `should_inject_dual_review`), multi-deliverable/complexity `plan` coercion (`resolve_execution_mode_with_reason`), and Two-Tier Surgical Fast-Path vs. Full 4-Step Dual-Review prompt builders |
| `src/agy_nexus/workflow_baseline.py` | ~213 | Automatic `docs/WORKFLOWS.md` / `README.md` plain-language workflow discovery (`workflow:baseline`), wire formatter, handoff quality evaluator, and prior-intent extraction |
| `src/agy_nexus/tools_praxis.py` | ~165 | Deadbolt-free local `FastMCP("agy-praxis-mcp")` internal workstation doorway (`polyglot_map`, `polyglot_search`, `polyglot_outline`, `praxis_handoff_inbox`, `praxis_claim_handoff`, `praxis_update_handoff`), `--stdio` entrypoint, and `--self-test` |
| `src/agy_nexus/tools_polyglot.py` | ~18 | Backward-compatible re-export shim aliasing `praxis_mcp` as `polyglot_mcp` for existing CLI and import consumers |
| `src/agy_nexus/virtual_uris.py` | ~329 | Virtual URI dispatcher for `brain:<subpath>`, `transcript:latest|turn|step`, `workflow:baseline`, `praxis:map|search|handoffs` (`polyglot:map|search`), and policy-safe `telemetry:stats|quota|wire|export_notebook` |
| `src/agy_nexus/inventory.py` | ~369 | Antigravity IDE config scanner (`agents/`, `skills/`, `plugins/`, `profiles/`), guarded customization file resolver, MCP server discovery, and tightened `dual-review` directive router |
| `src/agy_nexus/telemetry_scanner.py` | ~346 | Local-timezone transcript JSONL scanner, Praxis-first product detection (`Antigravity IDE (Praxis MCP)`), RPC handshake separation (`protocol_handshakes`), and per-model token attribution |
| `src/agy_nexus/ascii_default.py` | ~301 | `72-col` standard (`style="default"`) and `40-col` mobile (`style="quick"`) Unicode block (`░▒▓█`) ASCII telemetry renderers |
| `src/agy_nexus/ascii_rich.py` | ~190 | `76-col` widescreen box-drawn ASCII telemetry rig (`style="rich"`) |
| `src/agy_nexus/session_tree.py` | ~384 | 76-column copy-ready ASCII `Project -> Chat -> Session ID` + `[HANDOFF <slug>-NN]` hierarchy builder, strict recency sorting (`-last_updated_ts`), pruned & capped `8`-slot routing telemetry, and 3-2-1 backup manifest reader |
| `src/agy_nexus/session_status.py` | ~464 | Session health warnings, traversal-safe compaction tracking, 5-posture continuity-aware rollover evaluator (`FRESH`, `SEAM_AWARE`, `HOLD_FOR_COMPLETION`, `CLOSEOUT_ONLY`, `HARD_ROLLOVER`), and in-flight handoff mutex |
| `src/agy_nexus/retirement.py` | ~203 | Terminal session closeout & in-place retirement manifest (`RETIRED.json`), deferred `retire_after_closeout` closeout directives, prior-session baton extractor, and job-first 1-tap `Yes` `suggested_actions` engine |
| `src/agy_nexus/code_health.py` | ~324 | Cached GitHub `/releases/latest` + `/tags` highest-semver comparator (`installed` vs `remote`), `<= 500L` (`650L` ceiling) modular hygiene scanner, and Polyglot symbol health aggregator |
| `src/agy_nexus/stats_series.py` | ~278 | `1h` adaptive base slot grids (`24h` daily for Year), stacked model/subagent/project velocity series, and canonical Top-10 project-to-session hierarchy bands |
| `src/agy_nexus/stats.py` | ~418 | Unified telemetry builder (`build_nexus_stats_bundle`) combining Dual-Pool quota pacing, 52-week muted calendar matrix, full-span Year `24h` daily / sub-daily series, and 3-tier ASCII views |
| `src/agy_nexus/workflows.py` | ~303 | Cross-app workflow implementations (`inspect_multi_repo_drift`, `export_notebook_bundle` with `dry_run` preview & SHA-256 deduplication, quarantine handoff staging) |
| `src/agy_nexus/media_discovery.py` | ~401 | `<2ms` header-only image dimension parser (`read_image_dimensions_fast`), session ownership windowing (`0001-` sentinel rescue, nanosecond-safe `parse_iso_epoch`), symlink-safe depth-bounded walkers, and `git status` media classification |
| `src/agy_nexus/media.py` | ~407 | 7-day (`604800s`) HMAC-SHA256 `/web/media/` signer, canonical PWA deep-link builder (`workspace_url`), verified public HTTPS origin resolver, and bucket visual discovery |
| `src/agy_nexus/bucket_zip.py` | ~251 | Traversal-guarded `brain:<cid>/` & `repo:<slug>/` `.zip` path resolution, deduplicated streaming archive builder (`build_session_zip`), and `/download-zip` ASGI handler |
| `src/agy_nexus/bucket_scanner.py` | ~194 | Session upload batch scanner (`scan_session_uploads`), artifact markdown scanner (`scan_session_artifacts`), and Markdown media URL rewriter (`rewrite_markdown_media_links`) |
| `src/agy_nexus/bucket_api.py` | ~372 | Hierarchical 2-Pane Workspace tree (`build_workspace_tree_payload` + `version_info`), SQLite session workspace resolution (`conversation_summaries`), session bucket inventory, and backward-compat scanner/rewriter wrappers |
| `src/agy_nexus/web_routes.py` | ~242 | Static PWA asset server (`PWA_ASSETS`, `GET`/`HEAD` support, `no-store` on `/web` HTML & `sw.js`), `/web/media/` verification handler, and `/web/api/*` routes |
| `src/agy_nexus/uploads.py` | ~261 | Session scratch batch upload receiver (`POST /web/api/sessions/<conv_id>/upload`), `validate_conv_id`, `INDEX.md` generator, and file-size/type validator |
| `src/agy_nexus/webhook_proxy.py` | ~83 | Signed GitHub $\rightarrow$ GitLab webhook reverse-proxy handler (`/github-webhook-sync`) |
| `src/agy_nexus/sessions.py` | ~405 | Read-only SQLite `conversation_summaries.db` indexer with `validate_conv_id` / symlink guards, `"0001-"` sentinel rescue + filesystem mtime recency (`last_updated_ts`), and canonical project mapper |
| `src/agy_nexus/routing.py` | ~304 | Authenticated Host Companion (`:8098`) RPC caller, `<repo-slug>-NN` session resolver, cross-repo slot isolation (`_session_matches_workspace`), and Dual-Pool quota router |
| `src/agy_nexus/search.py` | ~311 | Monotonic wall-clock bounded multi-repo `git grep` scanner, Tier-0 pinned session `transcript_full.jsonl` + `brain/` search, and SQLite FTS5 search |
| `src/agy_nexus/workspace.py` | ~488 | 3-Tier Smart Path Resolver (`_resolve_and_read_files`), 3-pillar path normalizer, virtual URI router, and git diff/status helper |
| `src/agy_nexus/tools_session.py` | ~417 | MCP tools: `unlock_sessions`, `lock_bridge`, `list_saved_sessions`, `load_session_into_gemini` (<= 17.8 KB wire cap) |
| `src/agy_nexus/tools_workspace.py` | ~288 | MCP tools: `ask_workspace_readonly`, `inspect_git_diff` (dual raw/escaped <20 KB wire cap) |
| `src/agy_nexus/tools_media.py` | ~494 | MCP tool: `inspect_visual_artifacts` (Cloud MCP `<2ms` header-only fast path when `include_thumbnails=False`, plus local/crop `840px` 2-up WebP encoding within `< 20 KB` wire budget + 7-day signed links) |
| `src/agy_nexus/tools_ops.py` | ~387 | MCP tools: `get_session_tree` (`<= 17.5 KB` strict inner JSON guard + policy-safe `include_stats=True`), `list_models_and_agents`, `manage_background_run` |
| `src/agy_nexus/target_resolver.py` | ~354 | Fail-closed workspace/project resolver, 3-pillar path alias normalizer (`projects/<slug>`, `~/projects/<slug>`), and `create_new_project=True` greenfield guardrail |
| `src/agy_nexus/handoff.py` | ~494 | MCP tool: `send_handoff_and_resume` (proportional `fast`/`plan` lifecycle with multi-feature `plan` coercion, stage modes, repo-prefixed `<slug>-NN` staging, `RESUME_STAGED` repo isolation, `session_continuity` & deferred `retire_after_closeout`) |
| `src/agy_nexus/middleware.py` | ~486 | `BridgeCompatMiddleware` (Streamable HTTP `405` spec handling, `tools/list` schema compaction, zero-trust LAN-only `/praxis/` + `/polyglot/` guard, `[rpc:<method>]` wire tagging, multiplexed lifespan, `/web` PWA routing, `/health`) |
| `src/agy_nexus/server.py` | ~499 | Dual-MCP (`Nexus` + `Praxis`) Starlette/Uvicorn builder, `anyio.to_thread.run_sync` sync-tool offload, `--self-test` runner, and `main()` CLI entrypoint |
| `host_bridge/project_manager.py` | ~356 | Unified `:8098` Language Server discovery, `CreateProject` registration (`ANTIGRAVITY_PROJECT_ID`), and JSON-first `conversationId` extractor |
| `host_bridge/agy_host_bridge.py` | ~298 | Unified authenticated `/agentapi` handler shared by `agy_host_bridge` and `agy-host-bridge.service` |
| `host_bridge/bridge_security.py` | ~198 | Constant-time `X-Bridge-Token` auth, peer CIDR allowlist, anti-CSRF envelope checks, and `git-inspect` workspace sandboxing |

### Frontend Overwatch & Workspace Shell (`web/`)

| File | Lines | Responsibility |
| :--- | :---: | :--- |
| `web/index.html` | ~485 | Unified 42px Studio Topbar (`Analytics` \| `Workspace`), KPI & chart containers, 2-Pane Workspace shell with `#workspaceResizer`, Settings popover, Upload, Export & Lightbox dialogs |
| `web/styles.css` | ~399 | 4 surface themes (`Obsidian`, `Dark Paper`, `Warm Paper`, `Pure White` with `#f8fafc`/`#ffffff` contrast + card shadows), `D1–D4` density tokens, `1960px` container, muted `.btn-focal:disabled`, and responsive Analytics rules |
| `web/workspace.css` | ~261 | Edge-to-edge 2-Pane Workspace Explorer (`max-width: none`), thin tree scrollbar, `.workspace-resizer` splitter, 2-line session titles, responsive `248px`/`210px`/`145px` gallery cards, clean corner badges, and Lightbox |
| `web/app.js` | ~496 | Dashboard controller, surface switcher, compact borderless tabular legends, guarded SW `controllerchange` reload, PWA deep-link handler, and Settings menu |
| `web/heatmap.js` | ~154 | `53w`/`26w` Mon–Sun activity heatmap renderer and collision-safe month header mapper (`Jan`..`Dec` without stub clipping) |
| `web/workspace_resizer.js` | ~138 | Drag-to-resize Workspace sidebar splitter (`220–480px`, `localStorage.nexus_tree_width`, double-click reset, arrow-key accessible) |
| `web/explorer.js` | ~478 | 2-Pane Workspace Explorer (collapsible/resizable `300px <-> 38px <-> 0px` Zen sidebar, strict recency tree, `.tree-age-pill`, direct `#workspace` version hydration, and main-stage readers) |
| `web/gallery_select.js` | ~246 | Multi-Select Gallery state (`scope/rel_path`), touch 260ms press-and-glide sweep & desktop marquee drag, `Shift+Click`, sequential `⬇ PNGs (N)` downloader, and bulk `⬇ ZIP (N)` exporter |
| `web/sheet_builder.js` | ~464 | Aspect-aware `2 / 4 / 8`-per-sheet `3072×3072` `<canvas>` Contact Sheet builder, direct sequential `⬇ Sheets (K)` `.png` downloads, preview modal, and 10-file Web Share API v2 batching |
| `web/gallery_view.js` | ~237 | Shared Gallery toolbar (`Per Sheet 2 | 4 | 8`, `✦ Share Sheets`, `⬇ Sheets`, `⬇ PNGs`, `⬇ ZIP`), full-frame `WxH` card renderer with clean empty-ring unselected badges, and Lightbox modal |
| `web/markdown_renderer.js` | ~487 | Quiet UI Editorial HTML Markdown renderer (Tufte Booktabs, GFM callouts, SVG/Mermaid diagrams, handoff metadata banner, and DOMParser XSS sanitizer) |
| `web/hierarchy.js` | ~430 | Plot 3 stacked project/session bands, 1-line Project Swatch Strip, and Hierarchy tree with 8-char Session ID pills & `<slug>-NN` handoff rows |
| `web/charts.js` | ~443 | Divisor-of-24h adaptive DPI slot binning (`3h`/`4h`/`8h`/`12h`/`48h`), stacked SVG bar renderer, `ytd`/`last_year` demo routing, and URL query state sync |
| `web/demo_snapshot.js` | ~21 | Auto-generated sparse `_z()` + shared-date depersonalized 5-window (`current_month`, `last_month`, `last_90d`, `ytd`, `last_year`) showcase snapshot |
| `web/demo_data.js` | ~467 | Hydrates `/web?demo=1` Analytics & Workspace from `DEMO_SNAPSHOT` with real PNG thumbnails & procedural fallback |
| `web/uploads.js` | ~249 | Modal drag-and-drop batch file uploader & evaluator prompt copier |
| `web/health.js` | ~195 | Row 6 Code Health, `#versionLabel` / `#versionDot` badge updater (`updateVersionBadge`), Praxis Semantic Index & Modular Hygiene watchlist renderer |
| `web/palettes.js` | ~174 | Perceptual 10-hue OKLCH project palette & session shade generator |
| `web/sw.js` | ~74 | Root-scoped network-first static asset Service Worker (`SHELL_ASSETS` & `SHELL_NAMES`, excluding `/web` HTML) |

---

## 2. Praxis-First Navigation & Pragmatic File Size Standard

1. **Praxis-First Navigation (`agy-praxis-mcp`, backward-compatible `/polyglot/` alias)**:
   - Query `polyglot_map`, `polyglot_search`, and `polyglot_outline` first to obtain incremental SHA-256 cached `Lstart-Lend` spans and 1-liner docstrings before reading full files, and use `praxis_handoff_inbox` / `praxis_claim_handoff` / `praxis_update_handoff` to inspect and claim `<repo-slug>-NN` Gemini handoffs inside the IDE.
2. **Pragmatic File Size Budget (`<= 500 Lines`, Hard Split Ceiling `650 Lines`, Functions `<= 100 Lines`)**:
   - Keep cohesive Python modules in `src/agy_nexus/` and frontend files in `web/` **`<= 500 lines`** (warning band `501–650 lines`, hard split ceiling **`650 lines`**) and individual functions/methods **`<= 100 lines`**, avoiding artificial micro-file sprawl.
3. **Root-Directory Hygiene**:
   - Never add new `ag_bridge_*.py` modules or temporary files to the repository root.
   - Add new backend functionality inside `src/agy_nexus/`, new skills inside `skills/`, agent templates inside `agents/`, and documentation inside `docs/`.

---

## 3. Security & Depersonalization Invariants

1. **Zero Hardcoded Secrets**:
   - Never hardcode `PATH_SECRET`, `PRAXIS_MCP_TOKEN`, `POLYGLOT_MCP_TOKEN`, `PASS_HASH`, `HOST_BRIDGE_TOKEN`, `SUBDOMAIN_HASH`, or API tokens in source code, tests, comments, or docs. Runtime secrets load exclusively from `AG_BRIDGE_ENV_FILE` (`~/.config/ag-bridge-mcp/secrets.env`, `chmod 600`).
2. **Deadbolt Enforcement (`is_unlocked()` / `try_inline_unlock()`) & LAN Isolation**:
   - Every `agy-nexus-mcp` tool that reads or mutates session/workspace state **must** check `if not is_unlocked() and not try_inline_unlock(spoken_passphrase): return LOCKED_RESPONSE`.
   - The local `agy-praxis-mcp` doorway (`/praxis/{PRAXIS_MCP_TOKEN}/mcp` and legacy `/polyglot/{POLYGLOT_MCP_TOKEN}/mcp`) **must** enforce constant-time token verification (`hmac.compare_digest`) and immediately reject (`403`) any request carrying reverse-proxy headers, browser `Origin` headers, public `Host` domains, or non-private client IPs.
3. **Path Traversal & Sensitive File Protection**:
   - All file, archive, and repository paths resolved by `workspace.py`, `search.py`, `bucket_api.py`, `uploads.py`, and `polyglot_index.py` **must** be canonicalized via `Path.resolve()`, checked with `.is_relative_to(...)`, and filtered through `is_sensitive_filename()`.
4. **Strict Depersonalization**:
   - Never commit personal hostnames, private LAN IPs, real domains, or local username paths into the repository. Use generic placeholders (`your-domain.example.com`, `/home/dev/...`).

---

## 4. Bundled 8-Agent Orthogonal Roster (`agents/`)

The `agents/` directory contains ready-to-use subagent definitions (`~/.gemini/config/agents/*.md`) organized by **(Quota Pool × Thinking Effort × Tool Permissions)**:

| # | Agent File | Model Tier | Thinking | Tools | Role |
| :---: | :--- | :--- | :---: | :---: | :--- |
| 1 | [`agents/flash-scout.md`](agents/flash-scout.md) | `flash` | Low | Read-Only | High-speed directory mapper, symbol indexer, and grep scanner |
| 2 | [`agents/argon-architect.md`](agents/argon-architect.md) | `pro` | High | Read-Only | System blueprinting, schema design, and task decomposition |
| 3 | [`agents/flash-surgeon.md`](agents/flash-surgeon.md) | `flash` | Medium | Read-Write | High-volume CRUD, mechanical refactors, and UI/CSS edits |
| 4 | [`agents/argon-surgeon.md`](agents/argon-surgeon.md) | `pro` | Medium | Read-Write | Complex state machines, concurrency, and multi-module refactors |
| 5 | [`agents/flash-auditor.md`](agents/flash-auditor.md) | `flash` | Low | Read+Exec | Rapid test suite and compiler/linter verifier |
| 6 | [`agents/argon-sentinel.md`](agents/argon-sentinel.md) | `pro` | High | Read-Only | Security, invariant, race-condition, and resource-leak auditor |
| 7 | [`agents/claude-specialist.md`](agents/claude-specialist.md) | `inherit` | High | Read-Write | Partner-pool Strike-2 escalation specialist |
| 8 | [`agents/claude-sentinel.md`](agents/claude-sentinel.md) | `inherit` | High | Read-Only | Partner-pool adversarial security & architecture reviewer |

---

## 5. Verification & Self-Test Commands

Before committing any change, run both the `pytest` regression suites (`50+` unit & integration checks) and the built-in self-test runners:

```bash
uv run --with pytest --with pytest-asyncio pytest
python3 ag_bridge.py --self-test
python3 -m agy_nexus.tools_praxis --self-test
```

Or standalone via `uv`:

```bash
uv run --no-project --with fastmcp --with uvicorn --with starlette --with pydantic --with psutil python3 ag_bridge.py --self-test
```

