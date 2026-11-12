# AGENTS.md — AI Coding Assistant & Multi-Agent Architecture Guide

This document defines the modular architecture, coding standards, security invariants, and multi-agent orchestration rules for **AGY-Nexus MCP** (`agy-nexus-mcp`).

Any AI coding assistant (Google Antigravity, Gemini CLI, Claude Code, Cursor, or subagents) working in this repository **must** follow these guidelines.

---

## 1. Modular Package Architecture (`src/agy_nexus/`)

All server implementation code lives in `src/agy_nexus/`. The root `ag_bridge.py` file is a **51-line backward-compatible entrypoint shim** that prepends `src/` to `sys.path` and re-exports public symbols so existing Docker Compose, `systemd`, and CLI invocations continue to work without breaking changes.

### Module Responsibilities

| Module | Lines | Responsibility |
| :--- | :---: | :--- |
| `src/agy_nexus/config.py` | ~322 | Environment/secrets loading (`secrets.env`), `POLYGLOT_MCP_TOKEN` derivation, SHA-256 voice passphrase normalization, sliding-TTL Deadbolt gate, `fcntl.flock` atomic keyed `active_contexts` slots, and `FastMCP` initialization |
| `src/agy_nexus/hygiene.py` | ~269 | `< 20 KB` progressive wire compaction, centralized `is_sensitive_filename()` filter, line-range file slicing (`slice_file_content`), diff pagination (`paginate_diff`), and `<= 500L` (`650L` ceiling) modular auditing |
| `src/agy_nexus/polyglot_outline.py` | ~639 | Unified multi-language Polyglot semantic outliner (`.py`, `.js/.ts/.tsx`, `.vue`, `.md`, `.json/.jsonc`, `.yaml`, `.go`, `.rs`, `.sh`, `.sql`, `.html/.css`) with `Lstart-Lend` spans, 1-liner summaries, YAML scalar redaction, and `>100L` function warnings |
| `src/agy_nexus/polyglot_index.py` | ~412 | Incremental `(mtime_ns, size)` + `sha256` per-workspace JSON semantic index (`0700`/`0600` permissions) powering `polyglot_map`, `polyglot_search`, and `polyglot_outline` |
| `src/agy_nexus/tools_polyglot.py` | ~93 | Deadbolt-free local `FastMCP("agy-polyglot-mcp")` server (`polyglot_map`, `polyglot_search`, `polyglot_outline`), `--stdio` entrypoint, and `--self-test` |
| `src/agy_nexus/virtual_uris.py` | ~308 | Virtual URI dispatcher for `brain:<subpath>`, `transcript:latest|turn|step`, `polyglot:map|search`, and policy-safe `telemetry:stats|quota|wire|export_notebook` |
| `src/agy_nexus/inventory.py` | ~349 | Antigravity IDE config scanner (`agents/`, `skills/`, `plugins/`, `profiles/`), guarded customization file resolver, MCP server discovery, and workspace enumeration |
| `src/agy_nexus/telemetry_scanner.py` | ~305 | Local-timezone transcript JSONL scanner (`transcript.jsonl`), activity heatmap aggregator, client surface classifier, and per-model token attribution |
| `src/agy_nexus/ascii_default.py` | ~296 | `72-col` standard (`style="default"`) and `40-col` mobile (`style="quick"`) Unicode block (`░▒▓█`) ASCII telemetry renderers |
| `src/agy_nexus/ascii_rich.py` | ~181 | `76-col` widescreen box-drawn ASCII telemetry rig (`style="rich"`) |
| `src/agy_nexus/session_tree.py` | ~299 | 76-column copy-ready ASCII `Project -> Chat -> Session ID` hierarchy builder, parallel slot telemetry, and 3-2-1 backup manifest reader |
| `src/agy_nexus/session_status.py` | ~345 | Session health warnings, compaction tracking, context rollover budget, and in-flight handoff mutex |
| `src/agy_nexus/code_health.py` | ~265 | Cached GitHub release comparator (`installed` vs `remote`), `<= 500L` (`650L` ceiling) modular hygiene scanner, and Polyglot symbol health aggregator |
| `src/agy_nexus/stats_series.py` | ~231 | Sub-daily (`1h`/`2h`/`6h`/`24h`) stacked model, subagent, and project velocity series builder |
| `src/agy_nexus/stats.py` | ~325 | Unified telemetry builder (`build_nexus_stats_bundle`) combining Dual-Pool quota pacing, locked sub-daily series, session hierarchy, and 3-tier ASCII views |
| `src/agy_nexus/workflows.py` | ~291 | Cross-app workflow implementations (`inspect_multi_repo_drift`, `export_notebook_bundle` with `dry_run` preview, quarantine handoff staging) |
| `src/agy_nexus/media.py` | ~253 | Ephemeral 30-minute HMAC-SHA256 `/web/media/` signer, verified public HTTPS origin resolver, and visual artifact discovery |
| `src/agy_nexus/uploads.py` | ~255 | Session scratch batch upload receiver (`POST /web/api/sessions/<conv_id>/upload`), `INDEX.md` generator, and file-size/type validator |
| `src/agy_nexus/webhook_proxy.py` | ~83 | GitHub $\rightarrow$ GitLab webhook proxy handler |
| `src/agy_nexus/sessions.py` | ~316 | Read-only SQLite `conversation_summaries.db` indexer, `NEXUS_PROJECT_ID` workspace mapper, status classifier, and concurrent writer detector |
| `src/agy_nexus/routing.py` | ~190 | Authenticated Host Companion (`:8098`) RPC caller, Dual-Pool quota router (`quota-router.sh`), and skill keyword router |
| `src/agy_nexus/search.py` | ~304 | Monotonic wall-clock bounded multi-repo `git grep` scanner, Tier-0 pinned session `transcript_full.jsonl` + `brain/` search, and SQLite FTS5 search |
| `src/agy_nexus/workspace.py` | ~357 | 3-Tier Smart Path Resolver (`_resolve_and_read_files`), virtual URI router, git diff/status helper, and background job monitor |
| `src/agy_nexus/tools_session.py` | ~371 | MCP tools: `unlock_sessions`, `lock_bridge`, `list_saved_sessions`, `load_session_into_gemini` |
| `src/agy_nexus/tools_workspace.py` | ~313 | MCP tools: `ask_workspace_readonly`, `inspect_git_diff`, `get_visual_artifact` |
| `src/agy_nexus/tools_media.py` | ~398 | MCP tool: `inspect_visual_artifacts` (`840px` 2-up WebP encoding within `< 20 KB` wire budget) |
| `src/agy_nexus/tools_ops.py` | ~358 | MCP tools: `get_session_tree` (with policy-safe `include_stats=True`), `list_models_and_agents`, `manage_background_run` |
| `src/agy_nexus/handoff.py` | ~455 | MCP tool: `send_handoff_and_resume` (`execution_mode="auto"`, `RESUME_STAGED` unwrap, same-repo writer guard, and headless wakeup) |
| `src/agy_nexus/middleware.py` | ~530 | `BridgeCompatMiddleware` (Streamable HTTP `405` spec handling, zero-trust LAN-only `/polyglot/` guard, multiplexed lifespan, `/web` PWA, `/web/media/`, `/health`) |
| `src/agy_nexus/server.py` | ~468 | Dual-MCP Starlette/Uvicorn builder, `anyio.to_thread.run_sync` sync-tool offload, `--self-test` runner, and `main()` CLI entrypoint |

---

## 2. Polyglot-First Navigation & Pragmatic File Size Standard

1. **Polyglot-First Navigation (`agy-polyglot-mcp`)**:
   - Query `polyglot_map`, `polyglot_search`, and `polyglot_outline` first to obtain incremental SHA-256 cached `Lstart-Lend` spans and 1-liner docstrings before reading full files.
2. **Pragmatic File Size Budget (`<= 500 Lines`, Hard Split Ceiling `650 Lines`, Functions `<= 100 Lines`)**:
   - Keep cohesive Python modules in `src/agy_nexus/` and frontend files in `web/` **`<= 500 lines`** (warning band `501–650 lines`, hard split ceiling **`650 lines`**) and individual functions/methods **`<= 100 lines`**, avoiding artificial micro-file sprawl.
3. **Root-Directory Hygiene**:
   - Never add new `ag_bridge_*.py` modules or temporary files to the repository root.
   - Add new backend functionality inside `src/agy_nexus/`, new skills inside `skills/`, agent templates inside `agents/`, and documentation inside `docs/`.

---

## 3. Security & Depersonalization Invariants

1. **Zero Hardcoded Secrets**:
   - Never hardcode `PATH_SECRET`, `POLYGLOT_MCP_TOKEN`, `PASS_HASH`, `HOST_BRIDGE_TOKEN`, `SUBDOMAIN_HASH`, or API tokens in source code, tests, comments, or docs. Runtime secrets load exclusively from `AG_BRIDGE_ENV_FILE` (`~/.config/ag-bridge-mcp/secrets.env`, `chmod 600`).
2. **Deadbolt Enforcement (`is_unlocked()` / `try_inline_unlock()`) & LAN Isolation**:
   - Every `agy-nexus-mcp` tool that reads or mutates session/workspace state **must** check `if not is_unlocked() and not try_inline_unlock(spoken_passphrase): return LOCKED_RESPONSE`.
   - The local `agy-polyglot-mcp` endpoint (`/polyglot/{POLYGLOT_MCP_TOKEN}/mcp`) **must** enforce constant-time token verification (`hmac.compare_digest`) and immediately reject (`403`) any request carrying reverse-proxy headers, browser `Origin` headers, public `Host` domains, or non-private client IPs.
3. **Path Traversal & Sensitive File Protection**:
   - All file and repository paths resolved by `workspace.py`, `search.py`, and `polyglot_index.py` **must** be canonicalized via `Path.resolve()`, checked with `.is_relative_to(ws_path)`, and filtered through `is_sensitive_filename()`.
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

Before committing any change, run the automated self-test suite:

```bash
python3 ag_bridge.py --self-test
```

Or via `uv`:

```bash
uv run --no-project --with fastmcp --with uvicorn --with starlette --with pydantic --with psutil python3 ag_bridge.py --self-test
```
