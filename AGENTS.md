# AGENTS.md — AI Coding Assistant & Multi-Agent Architecture Guide

This document defines the modular architecture, coding standards, security invariants, and multi-agent orchestration rules for **AGY-Nexus MCP** (`agy-nexus-mcp`).

Any AI coding assistant (Google Antigravity, Gemini CLI, Claude Code, Cursor, or subagents) working in this repository **must** follow these guidelines.

---

## 1. Modular Package Architecture (`src/agy_nexus/`)

All server implementation code lives in `src/agy_nexus/`. The root `ag_bridge.py` file is a **51-line backward-compatible entrypoint shim** that prepends `src/` to `sys.path` and re-exports public symbols so existing Docker Compose, `systemd`, and CLI invocations continue to work without breaking changes.

### Module Responsibilities

| Module | Lines | Responsibility |
| :--- | :---: | :--- |
| `src/agy_nexus/config.py` | ~224 | Environment/secrets loading (`secrets.env`), SHA-256 voice passphrase normalization, sliding-TTL Deadbolt gate (`is_unlocked`, `try_inline_unlock`), and `FastMCP` instance initialization |
| `src/agy_nexus/hygiene.py` | ~234 | Context window pool limits (`MAX_FILE_CHARS=48000`, `MAX_TOTAL_FILE_CHARS=120000`, `MAX_FILES_PER_CALL=12`), line-range file slicing (`slice_file_content`), diff pagination (`paginate_diff`), and modular file-size auditing |
| `src/agy_nexus/inventory.py` | ~287 | Antigravity IDE config scanner (`agents/`, `skills/`, `plugins/`, `profiles/`), MCP server discovery (`mcp_config.json`), and workspace repo enumeration |
| `src/agy_nexus/telemetry_scanner.py` | ~272 | Transcript JSONL scanner (`transcript.jsonl`), 35-day activity heatmap aggregator, client surface classifier (`gemini_mobile`, `gemini_web`, `antigravity_ide`, `cli_headless`), and per-model token attribution |
| `src/agy_nexus/ascii_default.py` | ~288 | `44-col` mobile-first Unicode block (`░▒▓█`) ASCII telemetry renderer (`format_type="default"`) |
| `src/agy_nexus/ascii_rich.py` | ~160 | `38-col` compact HUD card (`format_type="compact"`) and `78-col` side-by-side desktop matrix (`format_type="desktop"`) |
| `src/agy_nexus/stats.py` | ~294 | Unified telemetry builder (`build_quota_and_system_stats`) combining host metrics (`psutil`), Dual-Pool quota pacing, Antigravity inventory, and ASCII views |
| `src/agy_nexus/workflows.py` | ~279 | 5 cross-app workflow implementations (`audit_multi_repo_drift`, `export_notebook_bundle`, `capture_thought_to_workspace`, `triage_recent_failures`, `generate_standup_digest`) |
| `src/agy_nexus/sessions.py` | ~276 | Read-only SQLite `conversation_summaries.db` indexer, status classifier (`RUNNING`, `STALLED_WAITING_APPROVAL`, `COMPLETED`, `IDLE`), and transcript turn parser |
| `src/agy_nexus/routing.py` | ~173 | Language Server (`agentapi`) HTTP bridge caller, Dual-Pool quota router (`quota-router.sh`), and model failover selector |
| `src/agy_nexus/search.py` | ~180 | Multi-file workspace reader (`_resolve_and_read_files`), `git grep` code scanner, and SQLite FTS5 conversation search |
| `src/agy_nexus/workspace.py` | ~289 | Workspace resolver (`_resolve_workspace_path`), git diff/status helper, and background job monitor (`_manage_background_run_internal`) |
| `src/agy_nexus/tools_session.py` | ~293 | MCP tools: `unlock_sessions`, `lock_bridge`, `list_saved_sessions`, `load_session_into_gemini` |
| `src/agy_nexus/tools_workspace.py` | ~232 | MCP tools: `ask_workspace_readonly`, `inspect_git_diff`, `manage_background_run` |
| `src/agy_nexus/tools_ops.py` | ~320 | MCP tools: `list_models_and_agents`, `get_quota_and_system_stats`, and the 5 cross-app workflow tools |
| `src/agy_nexus/handoff.py` | ~334 | MCP tool: `send_handoff_and_resume` (writes `scratch/gemini_research_handoff.md`, manages git worktrees, and dispatches headless runs) |
| `src/agy_nexus/middleware.py` | ~280 | `BridgeCompatMiddleware` (CORS, `/healthz`, `/web` Overwatch PWA static serving, `/web/api/*` endpoints, and client surface headers) |
| `src/agy_nexus/server.py` | ~139 | Starlette/Uvicorn app builder (`build_http_app`), `--self-test` suite (`run_self_test`), and `main()` CLI entrypoint |

---

## 2. File Size & Modular Hygiene Standard

1. **File Size Budget (`100–300 Lines`, Hard Split Ceiling `400 Lines`)**:
   - Every Python module in `src/agy_nexus/` and frontend file in `web/` (`index.html`, `styles.css`, `charts.js`, `app.js`) must stay under **400 lines** (ideally **100–300 lines**).
   - This guarantees every file fits 100% inside a single `ask_workspace_readonly` read without truncation and prevents surgical edit drift.
2. **Root-Directory Hygiene**:
   - Never add new `ag_bridge_*.py` modules or temporary files to the repository root.
   - Add new backend functionality inside `src/agy_nexus/`, new skills inside `skills/`, agent templates inside `agents/`, and documentation inside `docs/`.

---

## 3. Security & Depersonalization Invariants

1. **Zero Hardcoded Secrets**:
   - Never hardcode `PATH_SECRET`, `PASS_HASH`, `SUBDOMAIN_HASH`, or API tokens in source code, tests, comments, or docs. Runtime secrets load exclusively from `AG_BRIDGE_ENV_FILE` (`~/.config/ag-bridge-mcp/secrets.env`, `chmod 600`).
2. **Deadbolt Enforcement (`is_unlocked()` / `try_inline_unlock()`)**:
   - Every MCP tool that reads or mutates session/workspace state **must** check `if not is_unlocked() and not try_inline_unlock(spoken_passphrase): return LOCKED_RESPONSE` before accessing any data.
3. **Path Traversal Protection**:
   - All file and repository paths passed to `ask_workspace_readonly`, `inspect_git_diff`, or workflow tools **must** be resolved via `Path.resolve()` and verified with `.is_relative_to(ws_path)` before reading or writing.
4. **Strict Depersonalization**:
   - Never commit personal hostnames, private LAN IPs, real domains, or local username paths into the repository. Use generic placeholders (`your-domain.example.com`, `/home/user/...`).

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

Before committing any change, run the automated self-test suite:

```bash
python3 ag_bridge.py --self-test
```

Or via `uv`:

```bash
uv run --no-project --with fastmcp --with uvicorn --with starlette --with pydantic --with psutil python3 ag_bridge.py --self-test
```
