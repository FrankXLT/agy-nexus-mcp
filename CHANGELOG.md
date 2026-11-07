# Changelog

All notable changes to **AGY-Nexus MCP** (`agy-nexus-mcp`) are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
