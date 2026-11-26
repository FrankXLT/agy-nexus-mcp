# How It Is Built — Deep Technical Architecture (`AGY-Nexus MCP v4.2.0`)

`agy-nexus-mcp` is built as a modular dual-doorway Model Context Protocol (MCP) runtime, a host-level Language Server companion, and a zero-CDN Quiet UI Studio frontend. Every subsystem is constrained by deterministic file-size ceilings, strict `< 20 KB` wire budgets, constant-time cryptographic boundary checks, and fail-closed privacy verification.

---

## 1. System Architecture Blueprint

The runtime separates untrusted external MCP transport, deadbolt session isolation, local IDE indexing, and host process orchestration across strict privilege boundaries styled with Quiet UI CSS tokens (`--bg-canvas`, `--bg-card`, `--bg-elevated`, `--border-hairline`, `--accent-focal`):

<svg viewBox="0 0 920 384" width="100%" role="img" aria-label="AGY-Nexus MCP v4.2.0 Dual-Doorway Architecture Diagram" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <marker id="agyArrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 1 1 L 9 5 L 1 9 z" fill="var(--accent-focal, #2563eb)" />
    </marker>
    <marker id="agyMutedArrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 1 1 L 9 5 L 1 9 z" fill="var(--border-strong, #94a3b8)" />
    </marker>
  </defs>

  <rect x="2" y="2" width="916" height="380" rx="10" fill="var(--bg-canvas, #f8fafc)" stroke="var(--border-hairline, #e2e8f0)" stroke-width="1.5" />
  <rect x="2" y="2" width="916" height="4" rx="2" fill="var(--accent-focal, #2563eb)" />
  <text x="24" y="34" font-family="-apple-system, BlinkMacSystemFont, Inter, Segoe UI, sans-serif" font-size="13" font-weight="700" letter-spacing="0.04em" fill="var(--text-primary, #0f172a)">AGY-NEXUS MCP v4.2.0 — DUAL-DOORWAY, WIRE-BUDGET &amp; ROUTING ARCHITECTURE</text>
  <text x="896" y="34" text-anchor="end" font-family="JetBrains Mono, ui-monospace, monospace" font-size="11" fill="var(--text-secondary, #475569)">&lt;= 500L Modules · &lt; 20 KB Wire Cap</text>

  <!-- Column 1: Clients -->
  <rect x="22" y="56" width="184" height="86" rx="8" fill="var(--bg-card, #ffffff)" stroke="var(--border-strong, #cbd5e1)" />
  <rect x="22" y="56" width="4" height="86" rx="2" fill="var(--accent-focal, #2563eb)" />
  <text x="38" y="80" font-family="-apple-system, BlinkMacSystemFont, Inter, sans-serif" font-size="12" font-weight="700" fill="var(--text-primary, #0f172a)">Cloud &amp; Mobile MCP</text>
  <text x="38" y="99" font-family="JetBrains Mono, ui-monospace, monospace" font-size="10.5" fill="var(--text-secondary, #475569)">/{PATH_SECRET}/mcp</text>
  <text x="38" y="117" font-family="-apple-system, BlinkMacSystemFont, Inter, sans-serif" font-size="10.5" fill="var(--text-secondary, #475569)">Stateless Streamable HTTP</text>
  <text x="38" y="133" font-family="-apple-system, BlinkMacSystemFont, Inter, sans-serif" font-size="10.5" fill="var(--text-secondary, #475569)">Voice-Normalized Unlock</text>

  <rect x="22" y="158" width="184" height="86" rx="8" fill="var(--bg-card, #ffffff)" stroke="var(--border-strong, #cbd5e1)" />
  <text x="36" y="182" font-family="-apple-system, BlinkMacSystemFont, Inter, sans-serif" font-size="12" font-weight="700" fill="var(--text-primary, #0f172a)">OCI --stdio Clients</text>
  <text x="36" y="201" font-family="JetBrains Mono, ui-monospace, monospace" font-size="10.5" fill="var(--text-secondary, #475569)">--stdio (0 stdout noise)</text>
  <text x="36" y="219" font-family="-apple-system, BlinkMacSystemFont, Inter, sans-serif" font-size="10.5" fill="var(--text-secondary, #475569)">VS Code / CLI / Claude</text>
  <text x="36" y="235" font-family="-apple-system, BlinkMacSystemFont, Inter, sans-serif" font-size="10.5" fill="var(--text-secondary, #475569)">Fail-Closed PASS_HASH</text>

  <rect x="22" y="260" width="184" height="98" rx="8" fill="var(--bg-card, #ffffff)" stroke="var(--border-strong, #cbd5e1)" />
  <text x="36" y="284" font-family="-apple-system, BlinkMacSystemFont, Inter, sans-serif" font-size="12" font-weight="700" fill="var(--text-primary, #0f172a)">Quiet UI Studio PWA</text>
  <text x="36" y="303" font-family="JetBrains Mono, ui-monospace, monospace" font-size="10.5" fill="var(--text-secondary, #475569)">/web &amp; /web/v9</text>
  <text x="36" y="321" font-family="-apple-system, BlinkMacSystemFont, Inter, sans-serif" font-size="10.5" fill="var(--text-secondary, #475569)">3-Route Static Showcase</text>
  <text x="36" y="338" font-family="JetBrains Mono, ui-monospace, monospace" font-size="10.5" fill="var(--text-secondary, #475569)">./ · ./demo/ · ./docs/</text>

  <!-- Column 2: Core Middleware & Engine -->
  <rect x="248" y="56" width="230" height="302" rx="10" fill="var(--bg-elevated, #f1f5f9)" stroke="var(--accent-focal, #2563eb)" stroke-width="1.5" />
  <text x="264" y="79" font-family="-apple-system, BlinkMacSystemFont, Inter, sans-serif" font-size="12" font-weight="700" fill="var(--text-primary, #0f172a)">BridgeCompatMiddleware &amp; Core</text>

  <rect x="262" y="92" width="202" height="74" rx="6" fill="var(--bg-card, #ffffff)" stroke="var(--border-hairline, #e2e8f0)" />
  <text x="274" y="112" font-family="-apple-system, BlinkMacSystemFont, Inter, sans-serif" font-size="11.5" font-weight="700" fill="var(--text-primary, #0f172a)">Deadbolt &amp; Sliding-TTL Gate</text>
  <text x="274" y="130" font-family="JetBrains Mono, ui-monospace, monospace" font-size="10" fill="var(--text-secondary, #475569)">SHA-256 + hmac.compare_digest</text>
  <text x="274" y="147" font-family="JetBrains Mono, ui-monospace, monospace" font-size="10" fill="var(--text-secondary, #475569)">TTL_SECONDS (1800 / 7200s) + flock</text>

  <rect x="262" y="178" width="202" height="78" rx="6" fill="var(--bg-card, #ffffff)" stroke="var(--border-hairline, #e2e8f0)" />
  <text x="274" y="198" font-family="-apple-system, BlinkMacSystemFont, Inter, sans-serif" font-size="11.5" font-weight="700" fill="var(--text-primary, #0f172a)">Wire-Budget Compaction</text>
  <text x="274" y="216" font-family="JetBrains Mono, ui-monospace, monospace" font-size="10" fill="var(--text-secondary, #475569)">&lt;= 18.5 KB raw / &lt;= 19.8 KB esc</text>
  <text x="274" y="233" font-family="JetBrains Mono, ui-monospace, monospace" font-size="10" fill="var(--text-secondary, #475569)">anyio.to_thread + 840px WebP</text>

  <rect x="262" y="268" width="202" height="78" rx="6" fill="var(--bg-card, #ffffff)" stroke="var(--border-hairline, #e2e8f0)" />
  <text x="274" y="288" font-family="-apple-system, BlinkMacSystemFont, Inter, sans-serif" font-size="11.5" font-weight="700" fill="var(--text-primary, #0f172a)">SQLite RO &amp; 7-Day Media HMAC</text>
  <text x="274" y="306" font-family="JetBrains Mono, ui-monospace, monospace" font-size="10" fill="var(--text-secondary, #475569)">conversation_summaries.db?mode=ro</text>
  <text x="274" y="323" font-family="JetBrains Mono, ui-monospace, monospace" font-size="10" fill="var(--text-secondary, #475569)">/web/media/&lt;exp&gt;/&lt;sig&gt; (604800s)</text>

  <!-- Column 3: Local Doorway & Host Companion -->
  <rect x="518" y="56" width="204" height="106" rx="8" fill="var(--bg-card, #ffffff)" stroke="var(--border-strong, #cbd5e1)" />
  <rect x="518" y="56" width="4" height="106" rx="2" fill="var(--accent-emerald, #0b7d71)" />
  <text x="534" y="79" font-family="-apple-system, BlinkMacSystemFont, Inter, sans-serif" font-size="12" font-weight="700" fill="var(--text-primary, #0f172a)">agy-praxis-mcp (LAN)</text>
  <text x="534" y="98" font-family="JetBrains Mono, ui-monospace, monospace" font-size="10" fill="var(--text-secondary, #475569)">/praxis/{TOKEN}/mcp</text>
  <text x="534" y="115" font-family="-apple-system, BlinkMacSystemFont, Inter, sans-serif" font-size="10.5" fill="var(--text-secondary, #475569)">403 Proxy &amp; Origin Guard</text>
  <text x="534" y="132" font-family="-apple-system, BlinkMacSystemFont, Inter, sans-serif" font-size="10.5" fill="var(--text-secondary, #475569)">SHA-256 Polyglot Lstart-Lend</text>
  <text x="534" y="149" font-family="JetBrains Mono, ui-monospace, monospace" font-size="10" fill="var(--text-secondary, #475569)">&lt;repo-slug&gt;-NN Handoff Inbox</text>

  <rect x="518" y="178" width="204" height="94" rx="8" fill="var(--bg-card, #ffffff)" stroke="var(--border-strong, #cbd5e1)" />
  <text x="532" y="201" font-family="-apple-system, BlinkMacSystemFont, Inter, sans-serif" font-size="12" font-weight="700" fill="var(--text-primary, #0f172a)">Host Companion :8098</text>
  <text x="532" y="220" font-family="JetBrains Mono, ui-monospace, monospace" font-size="10" fill="var(--text-secondary, #475569)">X-Bridge-Token + CIDR Auth</text>
  <text x="532" y="237" font-family="JetBrains Mono, ui-monospace, monospace" font-size="10" fill="var(--text-secondary, #475569)">CreateProject Connect-RPC</text>
  <text x="532" y="254" font-family="JetBrains Mono, ui-monospace, monospace" font-size="10" fill="var(--text-secondary, #475569)">agentapi conversationId</text>

  <rect x="518" y="288" width="204" height="70" rx="8" fill="var(--bg-card, #ffffff)" stroke="var(--border-strong, #cbd5e1)" />
  <text x="532" y="311" font-family="-apple-system, BlinkMacSystemFont, Inter, sans-serif" font-size="12" font-weight="700" fill="var(--text-primary, #0f172a)">Loopback Quota Probe</text>
  <text x="532" y="330" font-family="JetBrains Mono, ui-monospace, monospace" font-size="10" fill="var(--text-secondary, #475569)">127.0.0.1 RetrieveUserQuota</text>
  <text x="532" y="346" font-family="JetBrains Mono, ui-monospace, monospace" font-size="10" fill="var(--text-secondary, #475569)">0600 live_quota_snapshot.json</text>

  <!-- Column 4: Pools & Routing -->
  <rect x="760" y="56" width="138" height="106" rx="8" fill="var(--bg-card, #ffffff)" stroke="var(--border-strong, #cbd5e1)" />
  <text x="774" y="79" font-family="-apple-system, BlinkMacSystemFont, Inter, sans-serif" font-size="11.5" font-weight="700" fill="var(--text-primary, #0f172a)">Google 20x Pool</text>
  <text x="774" y="99" font-family="JetBrains Mono, ui-monospace, monospace" font-size="10" fill="var(--text-secondary, #475569)">Gemini 4 Carbon</text>
  <text x="774" y="116" font-family="JetBrains Mono, ui-monospace, monospace" font-size="10" fill="var(--text-secondary, #475569)">Neon · Argon</text>
  <text x="774" y="133" font-family="JetBrains Mono, ui-monospace, monospace" font-size="10" fill="var(--text-secondary, #475569)">Hydrogen</text>
  <text x="774" y="150" font-family="JetBrains Mono, ui-monospace, monospace" font-size="10" fill="var(--text-secondary, #475569)">Flash 3.8</text>

  <rect x="760" y="178" width="138" height="94" rx="8" fill="var(--bg-card, #ffffff)" stroke="var(--border-strong, #cbd5e1)" />
  <text x="774" y="201" font-family="-apple-system, BlinkMacSystemFont, Inter, sans-serif" font-size="11.5" font-weight="700" fill="var(--text-primary, #0f172a)">Partner Pool</text>
  <text x="774" y="221" font-family="JetBrains Mono, ui-monospace, monospace" font-size="10" fill="var(--text-secondary, #475569)">Claude Opus 5.5</text>
  <text x="774" y="238" font-family="JetBrains Mono, ui-monospace, monospace" font-size="10" fill="var(--text-secondary, #475569)">Claude Sonnet 5.5</text>
  <text x="774" y="255" font-family="JetBrains Mono, ui-monospace, monospace" font-size="10" fill="var(--text-secondary, #475569)">GPT-OSS 120B</text>

  <rect x="760" y="288" width="138" height="70" rx="8" fill="var(--bg-card, #ffffff)" stroke="var(--border-strong, #cbd5e1)" />
  <text x="774" y="311" font-family="-apple-system, BlinkMacSystemFont, Inter, sans-serif" font-size="11.5" font-weight="700" fill="var(--text-primary, #0f172a)">13-Agent Roster</text>
  <text x="774" y="330" font-family="JetBrains Mono, ui-monospace, monospace" font-size="10" fill="var(--text-secondary, #475569)">12 Subagents &lt;=120</text>
  <text x="774" y="346" font-family="JetBrains Mono, ui-monospace, monospace" font-size="10" fill="var(--text-secondary, #475569)">Orchestrator &lt;250</text>

  <!-- Connectors -->
  <line x1="206" y1="99" x2="246" y2="120" stroke="var(--accent-focal, #2563eb)" stroke-width="1.6" marker-end="url(#agyArrow)" />
  <line x1="206" y1="201" x2="246" y2="201" stroke="var(--accent-focal, #2563eb)" stroke-width="1.6" marker-end="url(#agyArrow)" />
  <line x1="206" y1="308" x2="246" y2="308" stroke="var(--border-strong, #94a3b8)" stroke-width="1.5" marker-end="url(#agyMutedArrow)" />
  <line x1="478" y1="110" x2="516" y2="110" stroke="var(--accent-focal, #2563eb)" stroke-width="1.6" marker-end="url(#agyArrow)" />
  <line x1="478" y1="225" x2="516" y2="225" stroke="var(--accent-focal, #2563eb)" stroke-width="1.6" marker-end="url(#agyArrow)" />
  <line x1="478" y1="323" x2="516" y2="323" stroke="var(--border-strong, #94a3b8)" stroke-width="1.5" marker-end="url(#agyMutedArrow)" />
  <line x1="722" y1="109" x2="758" y2="109" stroke="var(--border-strong, #94a3b8)" stroke-width="1.5" marker-end="url(#agyMutedArrow)" />
  <line x1="722" y1="225" x2="758" y2="225" stroke="var(--border-strong, #94a3b8)" stroke-width="1.5" marker-end="url(#agyMutedArrow)" />
  <line x1="722" y1="323" x2="758" y2="323" stroke="var(--border-strong, #94a3b8)" stroke-width="1.5" marker-end="url(#agyMutedArrow)" />
</svg>

---

## 2. Modular `src/agy_nexus/` Package Design & `75`-Line Root Shim

All production backend code lives inside cohesive domain modules under `src/agy_nexus/` rather than a monolithic script or fragmented micro-files:

- **Hard Size & Complexity Ceilings**: `src/agy_nexus/hygiene.py` codifies `TARGET_FILE_LINES = 500` and `HARD_MAX_FILE_LINES = 650` alongside a `<= 100`-line function ceiling enforced across `src/agy_nexus/*.py`, `host_bridge/*.py`, `web/`, and `web/v9/`. Every backend module currently stays at `<= 499` lines, with automated checks in `tests/test_v408_ghcr_stdio_and_registry.py` and `tests/test_v409_wave3_catalog_security_and_docs.py`.
- **`75`-Line Backward-Compatible Root Shim (`ag_bridge.py`)**: Preserves compatibility with Docker Compose, `systemd` units, CLI scripts, and test imports by prepending `src/` to `sys.path`, re-exporting core symbols (`mcp`, `praxis_mcp`, `BridgeCompatMiddleware`, `SESSION_STATE`, `is_unlocked`, `main`), and delegating `__main__` directly to `agy_nexus.server.main()`.
- **Non-Blocking Async Thread Offload (`src/agy_nexus/server.py`)**: `_offload_sync_mcp_tools()` inspects FastMCP `_tool_manager._tools` and `_local_provider._components` at startup and wraps synchronous tool callables in `anyio.to_thread.run_sync(functools.partial(...))`, ensuring SQLite reads, git diffs, and Pillow WebP encoding never stall Uvicorn's ASGI event loop. `build_nexus_http_app()` mounts both `mcp` and `praxis_mcp` under `BridgeCompatMiddleware`, whose `_multiplex_lifespan()` coordinates both ASGI lifespans in lockstep.

| Layer | Location | Line Budget | Key Responsibilities |
| :--- | :--- | :---: | :--- |
| Root Shim | `ag_bridge.py` | `75` lines | `sys.path` injection + public symbol re-exports |
| Backend Core | `src/agy_nexus/*.py` | `<= 500` lines/file | Auth, wire compaction, Polyglot index, sessions, media, telemetry, MCP tools |
| Host Companion | `host_bridge/*.py` | `<= 356` lines/file | `:8098` Language Server discovery, `CreateProject` RPC, `/agentapi`, CIDR auth |
| Quiet UI Studio | `web/` & `web/v9/` | `<= 500` lines/file | Layered CSS tokens (`@layer`), ECharts analytics, 2-pane workspace, contact sheets |

---

## 3. Two-Doorway Setup Architecture & Zero-Stdout `--stdio`

The `ag-bridge-mcp` service (`agy-nexus-mcp`) exposes two isolated protocol doorways from a single runtime process, plus a container-native `--stdio` mode:

### External Streamable HTTP Doorway (`ag-bridge-mcp` / `agy-nexus-mcp`)
1. **Capability URL Path & Stateless HTTP**: Mounted at `/{PATH_SECRET}/mcp` (`PATH_SECRET >= 32` hex characters) with `stateless_http=True`, `json_response=True`, and `host_origin_protection=False` behind reverse proxies. `BridgeCompatMiddleware._handle_non_post_http()` returns `204 No Content` (`Allow: POST, OPTIONS`) on `OPTIONS` preflights and strict Streamable HTTP `405 Method Not Allowed` JSON-RPC errors on `GET`/`HEAD`/`DELETE` calls to `/mcp`.
2. **Header Normalization & `tools/list` Compaction**: `_prepare_post_scope_and_summary()` injects `Accept: application/json, text/event-stream` if missing, while `_compact_tools_list_body()` strips empty `_meta.fastmcp.tags` and redundant auto-generated `title` properties from `tools/list` responses to conserve client context.
3. **SHA-256 Voice-Normalized Passphrase Gate**: `normalize_phrase()` strips every non-alphanumeric character (`re.sub(r"[^a-z0-9]", "", phrase.lower())`) before computing SHA-256. `verify_passphrase()` validates against 64-hex `PASS_HASH` (loaded from `/home/dev/.config/ag-bridge-mcp/secrets.env` or `AG_BRIDGE_ENV_FILE`) using `hmac.compare_digest()`, stripping conversational prefixes (`"my spoken passphrase is ..."`) and scanning `2..10`-token sliding windows to tolerate voice-to-text transcription drift.
4. **Configurable Sliding-TTL Lock & Parallel Context Isolation**: `TTL_SECONDS` defaults to `7200` seconds (clamped above `MIN_TTL_SECONDS = 300`) and can be tuned in `secrets.env` or container environment—for example, `TTL_SECONDS=1800` enables a **Thirty-Minute Passphrase Lock**. Every valid `is_unlocked()` call refreshes `SESSION_STATE["unlocked_at"]` and persists atomically to `STATE_FILE` via `fcntl.flock(..., LOCK_EX)` + temporary file `os.replace()`. When expired, `_clear_selected_session_state()` clears active pointers and `active_contexts`, while `prune_stale_context_slots()` sweeps missing `/tmp/` paths and orphaned synthetic test slots.

### Internal Workstation Doorway (`agy-praxis-mcp`)
- **Deadbolt-Free Local Endpoint with Zero-Trust LAN Guard**: `tools_praxis.py` exposes `FastMCP("agy-praxis-mcp")` (`polyglot_map`, `polyglot_search`, `polyglot_outline`, `praxis_handoff_inbox`, `praxis_claim_handoff`, `praxis_update_handoff`) at `/praxis/{PRAXIS_MCP_TOKEN}/mcp` (plus `/polyglot/{POLYGLOT_MCP_TOKEN}/mcp` compatibility routing). When explicit tokens are unset, `get_praxis_mcp_token()` derives a 48-hex token via `hmac.new(PATH_SECRET, b"agy-praxis-mcp-v1", sha256)`.
- **Strict `403` Boundary Enforcement**: `BridgeCompatMiddleware._route_praxis_doorway()` rejects (`403`) any request carrying reverse-proxy headers (`X-Forwarded-For`, `X-Real-IP`, `Forwarded`, `CF-Connecting-IP`, `X-Forwarded-Host`, `Via`, etc.), duplicate `Host`/`Origin` headers, non-LAN `Host` or `Origin` values, or non-private client IPs before performing constant-time `hmac.compare_digest()` token verification.

### Zero-Stdout `--stdio` Container Mode
- Passing `--stdio` (or `--stdio=true|1|yes`) invokes `_run_stdio_transport()` (`mcp.run(transport="stdio", show_banner=False)`), routing all startup diagnostics to `sys.stderr` so `stdout` carries strictly valid JSON-RPC messages for OCI containers (`agy-nexus-mcp --stdio`), VS Code, and CLI clients.
- When `PASS_HASH` is absent or invalid in `--stdio` mode, deadbolt-safe tools (`list_models_and_agents`, `get_session_tree` when telemetry is allowed) remain reachable while private session and workspace tools fail closed with `LOCKED_RESPONSE`.

---

## 4. Wire-Budget Engineering & SHA-256 Polyglot Semantic Index

Cloud MCP adapters impose strict `20 KB` payload ceilings on JSON-RPC responses—counting **escaped** bytes inside the outer JSON-RPC wrapper as well as raw UTF-8 characters.

### Dual Raw + Escaped `< 20 KB` Budget & Progressive Compaction
- **Dual Byte Guards (`src/agy_nexus/hygiene.py`)**: `within_wire_budget()` verifies both `len(raw_text.encode("utf-8")) <= WIRE_INNER_CAP_BYTES` (`18500` B) and `len(json.dumps(raw_text, ensure_ascii=False).encode("utf-8")) <= WIRE_ESCAPED_CAP_BYTES` (`19800` B).
- **Progressive Compaction Pipeline (`compact_payload_to_wire_budget`)**: When an outgoing response exceeds either cap, the compactor trims sequentially without corrupting JSON syntax:
  1. Slices secondary search arrays (`historical_session_matches`, `symbol_callers`, `polyglot_symbol_matches`, `code_search_matches`, `pinned_session_matches`, `untracked_files`) and drops `available_repositories` / `configured_mcp_servers`.
  2. Compacts multi-repo drift arrays via `_trim_drift_repos()` across `(20,4) -> (10,2) -> (6,0) -> (3,0)` repo/file caps.
  3. Progressively shortens git `diff` blocks with explicit pagination hints (`file_path` or `offset_chars`).
  4. Shrinks batched `file_details` content (`_shrink_file_details_step`, preserving `start_line`/`end_line` slice pointers) and drops non-essential telemetry blocks (`_shrink_aux_fields_step`).

### `840px` WebP Thumbnails & `<2ms` Header-Only Fast Path (`src/agy_nexus/tools_media.py`)
- When `inspect_visual_artifacts()` is called by Cloud MCP adapters with `include_thumbnails=False`, `_build_visual_item()` skips image transcoding entirely and calls `read_image_dimensions_fast()` (`<2ms` header-only PNG/JPEG/WebP/GIF parser) while returning 7-day signed `/web/media/` links.
- When thumbnails are enabled (`limit=2` default), `max_edge` adapts by batch size (`960px` for 1 image, `840px` for 2-up default, `560px` for 3, `460px` for 4+), applies optional region crops (`top`, `middle`, `bottom`, or `x,y,w,h`), and runs `encode_image_to_webp_budget()` across a Lanczos resize + WebP quality ladder (`78 -> 22`) inside `MAX_TOTAL_RAW_WEBP_BYTES = 11400` (`<= 15.2 KB` base64 + JSON metadata `< 20 KB`).

### SHA-256 Cached Polyglot Semantic Index (`src/agy_nexus/polyglot_index.py` & `polyglot_outline.py`)
- Maintains per-workspace JSON indexes inside `AGY_DATA_DIR/sidecar_data/polyglot_index/` (`0700` directory, `0600` index files), guarded by `_is_safe_workspace()`, `is_sensitive_filename()`, `MAX_INDEX_FILE_BYTES = 524288`, `MAX_INDEXED_FILES = 2500`, and `MEM_DEBOUNCE_SECONDS = 4.0`.
- Fast-stat checks `(mtime_ns, size)` skip unchanged files in memory, falling back to `sha256` content digests so only modified, added, or deleted files are re-parsed.
- Unified outliners extract `Lstart-Lend` symbol spans, 1-line summaries, and `>100L` complexity flags across Python, JS/TS/TSX, Vue, Go, Rust, Bash, SQL, Markdown, JSON/JSONC, YAML (with scalar redaction), HTML, and CSS/SCSS. `polyglot_map` stays strictly bounded (`max_bytes = 17500`) with directory summaries.

---

## 5. Host Companion (`:8098`), HMAC Media, SQLite Scanner & Static Showcase

### Host Companion (`:8098`) RPC & `CreateProject` Registration
- `host_bridge/agy_host_bridge.py` binds a `ThreadingHTTPServer` on `127.0.0.1:8098` protected by `host_bridge/bridge_security.py` (constant-time `X-Bridge-Token` derived via `hmac.new(PATH_SECRET, b"agy-host-bridge-agentapi-v1", sha256)` or explicit `HOST_BRIDGE_TOKEN`, peer CIDR allowlist, and anti-CSRF validation).
- `host_bridge/project_manager.py` discovers the active Antigravity Language Server from `/proc` or `ps` (`--csrf_token` + `JetskiWeb` Content-Security-Policy port probe in `discover_antigravity_env()`).
- For greenfield workspaces (`create_if_missing=True`), `resolve_or_create_project()` validates containment under canonical workspace pillar roots (such as `/home/dev/agentic_workspace/projects/<slug>`), initializes `git init -b <branch>`, assigns a new UUID, invokes Connect-RPC `POST /exa.language_server_pb.LanguageServerService/CreateProject`, and syncs `app_storage.json` under a mutex. `extract_agentapi_conversation_id()` parses JSON `conversationId` responses safely without colliding with prompt-embedded UUIDs.

### HMAC-SHA256 7-Day `/web/media/` Signing (`src/agy_nexus/media.py`)
- `sign_media_url()` creates capability URLs shaped `/web/media/<exp_ts>/<hmac_sig>/<scope>/<rel_path>` with `MEDIA_TTL_SECONDS = 604800` (7 days) and a 32-char hex signature `hmac.new(PASS_HASH, f"{exp_ts}:{scope}:{clean_rel}", sha256)`.
- `verify_and_resolve_media()` enforces timestamp expiry, constant-time `hmac.compare_digest()`, `..` rejection, and canonical `.resolve().is_relative_to(...)` path confinement inside `brain:<conv_id>` or `repo:<slug>`.

### SQLite Read-Only Session Scanner (`src/agy_nexus/sessions.py`)
- Opens Antigravity's `conversation_summaries.db` strictly read-only (`sqlite3.connect(f"file:{cfg.AGY_DB_FILE}?mode=ro", uri=True)`), combining recent `last_modified_time DESC` rows with `"0001-"` sentinel or NULL rows (`rowid DESC`).
- `_compute_session_activity_ts()` rescues sentinel timestamps by taking `max(db_ts, sess_dir_mtime, task.md_mtime, transcript_full.jsonl_mtime, transcript.jsonl_mtime)`, while `_safe_conv_subdir()` validates `conv_id` and blocks symlink traversal outside `AGY_BRAIN_DIR`.

### Privacy-Stripped Static Three-Route Showcase Builder (`scripts/build_github_showcase.py`)
- Compiles a zero-backend static bundle into `build/gh-pages/` (`.nojekyll`, `window.AGY_STATIC_SHOWCASE = true`, `./` relative paths, `demo_snapshot.js`, and offline vendored Apache ECharts + Quiet UI assets under `v9/vendor/`).
- Powers the **Three-Route Public Project Site**:
  - **Overview (`./`)**: Architecture summary and static entry links.
  - **Interactive Demo (`./demo/`)**: Live client-side **Analytics** (KPIs, `Quota & Resets % left`, stacked series, sortable tables, 52w/26w calendar matrix), **Project Scope** (`?project=<id>` via `v9_project_view.js`), and **Workspace Explorer** (2-pane session tree, Markdown reader, capture gallery).
  - **Technical Docs (`./docs/`)**: Static documentation views.
- Every PNG passes through `strip_png_metadata()`—parsing raw PNG chunks and dropping `tEXt`, `zTXt`, `iTXt`, `eXIf`, and `tIME`—followed by fail-closed `scan_showcase_privacy()`, which aborts the build on any `.lan` domain, RFC1918 private IP, live brain UUID, local username literal, PNG metadata chunk, trailing post-`IEND` bytes, or SHA-256 `_BANNED_HASHES` match.

---

## 6. Quiet UI Styling Layers & Model/Subagent Routing Architecture

### Quiet UI CSS Layers & Design Tokens (`web/v9/`)
- `web/v9/v9_layers.css` establishes deterministic cascade precedence (`@layer reset, tokens, shell, archetypes, evidence, views, utilities;`) with zero `!important` overrides.
- `web/v9/vendor/quiet-ui-tokens.css` defines fluid root scaling (`16px` up to `22px` at 4K), 4 polarity themes (`white`, `paper`, `dark-paper`, `dark`), concentric corner radii (`--radius-inner: max(0px, calc(var(--radius-card) - var(--inset-pad)))`), and `D1–D4` density tokens.

### Dual-Pool Model & 13-Agent Routing (`agents/`, `ls_quota_probe.py`, `routing.py`)
- **Dual-Pool Quota Split**: Separates the **Google 20x Pool** (`Gemini 4 Carbon`, `Neon`, `Argon`, `Hydrogen`, `Gemini 3.8 Flash`) from the **Partner Pool** (`Claude Opus 5.5`, `Claude Sonnet 5.5`, `GPT-OSS 120B`). `ls_quota_probe.py` polls the loopback Language Server (`127.0.0.1` `RetrieveUserQuotaSummary`) to persist sanitized `0600` `live_quota_snapshot.json` telemetry (`Quota & Resets % left` and reset countdowns) with zero tokens or emails stored.
- **13-Agent Orthogonal Roster**: `agents/*.md` defines 12 specialized subagents capped at `<= 120` steps (`flash-scout`, `argon-architect`, `flash-surgeon`, `hydrogen-surgeon`, `neon-surgeon`, `argon-surgeon`, `flash-auditor`, `argon-sentinel`, `carbon-sentinel`, `claude-specialist`, `claude-sentinel`, `pool-failover`) plus `swarm-orchestrator` (`< 250` steps). Dual-Tab orchestration routes routine verification through `0%`-Partner Mode A (`carbon-sentinel`) and reserves Partner quota for Strike-2 escalation (`claude-specialist` / `claude-sentinel`) or automatic `pool-failover`.
- **Cross-Repo Slot Isolation & `<repo-slug>-NN` Queue**: `routing.py` resolves target sessions deterministically (`_resolve_target_session_for_handoff`) and refuses to borrow another repository's active slot, staging incremental `<repo-slug>-NN` tickets (`STAGED -> IN_WORK -> COMPLETED | SUPERSEDED`) inside `handoff_queue.py` for IDE pickup via `agy-praxis-mcp`.
