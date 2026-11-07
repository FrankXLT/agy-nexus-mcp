# AGENTS.md — AI Coding Assistant & Multi-Agent Architecture Guide

This document defines the modular architecture, coding standards, security invariants, and multi-agent orchestration rules for **AGY-Nexus MCP** (`agy-nexus-mcp`).

Any AI coding assistant (Google Antigravity, Gemini CLI, Claude Code, Cursor, or subagents) working in this repository **must** follow these guidelines.

---

## 1. Modular Package Architecture (`src/agy_nexus/`)

All server implementation code lives in `src/agy_nexus/`. The root `ag_bridge.py` file is a **51-line backward-compatible entrypoint shim** that prepends `src/` to `sys.path` and re-exports public symbols so existing Docker Compose, `systemd`, and CLI invocations continue to work without breaking changes.

### Module Responsibilities

| Module | Lines | Responsibility |
| :--- | :---: | :--- |
| `src/agy_nexus/config.py` | ~284 | Environment/secrets loading (`secrets.env`), SHA-256 voice passphrase normalization, sliding-TTL Deadbolt gate, `fcntl.flock` atomic keyed `active_contexts` slots, and `FastMCP` initialization |
| `src/agy_nexus/hygiene.py` | ~233 | `< 20 KB` progressive wire compaction, line-range file slicing (`slice_file_content`), diff pagination (`paginate_diff`), and modular file-size auditing |
| `src/agy_nexus/inventory.py` | ~287 | Antigravity IDE config scanner (`agents/`, `skills/`, `plugins/`, `profiles/`), MCP server discovery (`mcp_config.json`), and workspace repo enumeration |
| `src/agy_nexus/telemetry_scanner.py` | ~309 | Local-timezone transcript JSONL scanner (`transcript.jsonl`), activity heatmap aggregator, client surface classifier, and per-model token attribution |
| `src/agy_nexus/ascii_default.py` | ~290 | `72-col` standard (`style="default"`) and `40-col` mobile (`style="quick"`) Unicode block (`░▒▓█`) ASCII telemetry renderers |
| `src/agy_nexus/ascii_rich.py` | ~167 | `76-col` widescreen box-drawn ASCII telemetry rig (`style="rich"`) |
| `src/agy_nexus/session_tree.py` | ~289 | 76-column copy-ready ASCII `Project -> Chat -> Session ID` hierarchy builder, parallel slot telemetry, and 3-2-1 backup manifest reader |
| `src/agy_nexus/stats.py` | ~307 | Unified telemetry builder (`build_nexus_stats_bundle`) combining Dual-Pool quota pacing, locked sub-daily series, session hierarchy, and 3-tier ASCII views |
| `src/agy_nexus/workflows.py` | ~279 | Cross-app workflow implementations (`inspect_multi_repo_drift`, `export_notebook_bundle`, quarantine handoff staging) |
| `src/agy_nexus/media.py` | ~177 | Ephemeral 30-minute HMAC-SHA256 `/web/media/` signer, path-traversal sandbox verifier, and visual artifact discovery |
| `src/agy_nexus/webhook_proxy.py` | ~83 | GitHub $\rightarrow$ GitLab webhook proxy handler |
| `src/agy_nexus/sessions.py` | ~301 | Read-only SQLite `conversation_summaries.db` indexer, status classifier, same-repo concurrent writer detector, and transcript turn parser |
| `src/agy_nexus/routing.py` | ~173 | Language Server (`agentapi`) HTTP bridge caller, Dual-Pool quota router (`quota-router.sh`), and model failover selector |
| `src/agy_nexus/search.py` | ~180 | Multi-file workspace reader, `git grep` code scanner, and SQLite FTS5 conversation search |
| `src/agy_nexus/workspace.py` | ~290 | 3-Tier Smart Path Resolver (`_resolve_and_read_files`), git diff/status helper, and background job monitor |
| `src/agy_nexus/tools_session.py` | ~309 | MCP tools: `unlock_sessions`, `lock_bridge`, `list_saved_sessions`, `load_session_into_gemini` |
| `src/agy_nexus/tools_workspace.py` | ~298 | MCP tools: `ask_workspace_readonly`, `inspect_git_diff`, `get_visual_artifact` |
| `src/agy_nexus/tools_ops.py` | ~307 | MCP tools: `get_session_tree`, `list_models_and_agents`, `manage_background_run` |
| `src/agy_nexus/handoff.py` | ~279 | MCP tool: `send_handoff_and_resume` (writes `scratch/gemini_research_handoff.md`, checks same-repo concurrent writers, and dispatches headless runs) |
| `src/agy_nexus/middleware.py` | ~294 | `BridgeCompatMiddleware` (CORS, `/web` Overwatch PWA static serving, `/web/media/`, `/web/api/stats`, and wire telemetry) |
| `src/agy_nexus/server.py` | ~184 | Starlette/Uvicorn app builder, 8-suite `--self-test` runner (`run_self_test`), and `main()` CLI entrypoint |

---

## 2. File Size & Modular Hygiene Standard

1. **File Size Budget (`100–300 Lines`, Hard Split Ceiling `400 Lines`)**:
   - Every Python module in `src/agy_nexus/` and frontend file in `web/` (`index.html`, `styles.css`, `charts.js`, `hierarchy.js`, `app.js`) must stay under **400 lines** (ideally **100–300 lines**).
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
