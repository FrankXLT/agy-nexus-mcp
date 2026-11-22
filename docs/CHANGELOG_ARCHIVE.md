# Changelog Archive (`v1.0.0` – `v2.9.0`)

Historical release notes prior to the `v3.0.0` Overwatch & Workspace release. See [`CHANGELOG.md`](../CHANGELOG.md) for `v3.0.0` through `v4.0.0+`.

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
  - Implemented explicit **`STAGED`**, **`IN_WORK`**, **`SUPERSEDED`**, and **`COMPLETED`** lifecycle states, IDE disambiguation, strict cross-repo `RESUME_STAGED` isolation, and `_resolve_session_identifier("<repo-slug>-NN")` resolution.
- **Dashboard Hierarchical Tree Handoff Integration (`session_tree.py`, `stats_series.py`, `web/`)**:
  - Surfaced `STAGED`, `IN_WORK`, and `SUPERSEDED` handoff rows and header count badges directly inside the session hierarchy and 76-col ASCII tree.
- **Unified 4-Surface Perceptual Color System & Multi-Hue Sequential Heatmap**:
  - Replaced clashing plot colors with `PRAXIS_MASTER_SLOTS` and a polarity-aware 4-stop multi-hue sequential heatmap tuned for Obsidian, Dark Paper, Warm Paper, and Pure White.

---

## [2.7.0] — 2026-11-11

### Security
- **Zero-Trust LAN-Only `agy-polyglot-mcp` Endpoint & Incremental Index Sandboxing**:
  - Enforced constant-time 192-bit token verification on `/polyglot/{POLYGLOT_MCP_TOKEN}/mcp`, strict LAN-only `403 Forbidden` rejection on reverse-proxy/Origin headers or non-RFC1918 IPs, `0700`/`0600` index cache permissions, `is_sensitive_filename()` exclusion, YAML scalar redaction, and read-only SQLite connection cleanup.

### Added
- **Unified Incremental SHA-256 Polyglot Engine (`polyglot_outline.py`, `polyglot_index.py`, `tools_polyglot.py`)**, **Virtual URI Routing (`virtual_uris.py`)**, **Pragmatic `<= 500` Line Modular Budget (`code_health.py`)**.

### Fixed
- **MCP Streamable HTTP `405` Compliance, Async Offload, Read-Only Slice Performance, `RESUME_STAGED` Unwrap & High-Detail `840px` WebP Delivery**.

---

## [2.6.0] — 2026-11-11

### Security
- **Host Companion Bridge Zero-Trust Authentication & Loopback Hardening (`CWE-306`, `CWE-88`)**: Loopback default `127.0.0.1`, constant-time `X-Bridge-Token`, CIDR filtering, Browser `Origin` rejection, and `git`/`agentapi` CLI injection guards.

### Added
- **Two-Step Headless Confirmation Gate, `/web` Session Scratch Batch Uploads, Universal Polyglot Outliner & Automated Session Baton-Pass**.

---

## [2.5.0] — 2026-11-09

### Fixed
- **Gemini Mobile MCP Tool Collisions, Same-Turn Fallback, `sendMessage` Path Shadowing, Brain Scratch Isolation & Service Reload Clarification**.

---

## [2.4.1] — 2026-11-09

### Added
- **3-Mode Middleman Protocol, Content-Aware Skill Auto-Router, 4-Step Subagent Lifecycle, In-Flight Handoff Mutex, Native AST Outliner & Code Health Engine**.

---

## [2.4.0] — 2026-11-07

### Added
- **Parallel Session Isolation (`active_contexts`), 3-Tier Smart Path Resolver, Concurrent Writer Guard, 76-Col ASCII Hierarchy & 3-2-1 Git Synchronization**.

---

## [2.3.4] — 2026-11-05

### Fixed
- **Unified Time-Series Alignment, Local Timezone Bucketing, Single-Call Guardrail & Period-Scoped Project Totals**.

---

## [2.3.3] — 2026-11-04

### Fixed
- **Strict `< 20 KB` Wire-Budget Enforcement, Web Overwatch Deadbolt Unlock Fix & 3-Tier ASCII Renderer Polish**.

---

## [2.3.0] — 2026-11-03

### Added
- **Modular `src/agy_nexus/` Package Architecture, Modular Web Overwatch PWA, 120k-Char Multi-File Research Pool, Bundled Orthogonal Agent Roster & GNU AGPLv3 License**.

---

## [2.2.0] — 2026-11-02

### Added
- **3-Format Live ASCII Telemetry, Manifest V3 Chrome Extension & 5 Cross-App Workflow Accelerators**.

---

## [2.0.0] — 2026-11-01

### Added
- **AGY-Nexus Overwatch PWA (`/web`) & Dual-Pool Quota Pacing**.

---

## [1.0.0] — 2026-10-31

### Added
- Initial release of **AGY-Nexus MCP** (`ag-bridge-mcp`) with 3-Layer Security (`SUBDOMAIN_HASH`, 192-bit `PATH_SECRET`, Voice-Normalized SHA-256 Spoken Passphrase Deadbolt), SQLite session discovery, read-only workspace research, and headless Language Server handoff.
