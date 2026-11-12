# Changelog

All notable changes to **AGY-Nexus MCP** (`agy-nexus-mcp`) are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
