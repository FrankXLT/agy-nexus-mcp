# Security Policy & 5-Layer Zero-Trust Architecture

**AGY-Nexus MCP** (`agy-nexus-mcp`) bridges public cloud AI surfaces (Gemini Mobile, Gemini Web, Gemini Tasks) to your private local Antigravity IDE workspaces. Security is treated as a first-class architectural invariant.

---

## 1. Five-Layer Zero-Trust Defense Model

Every incoming request to AGY-Nexus MCP is protected by five independent security barriers:

### Layer 1 — Unlisted Subdomain (`SUBDOMAIN_HASH`)
- Generated via `scripts/init_secrets.py` using CSPRNG (`secrets.token_hex(6)`).
- Prevents automated subdomain enumeration and opportunistic scanners from discovering the bridge endpoint.

### Layer 2 — 192-Bit Unguessable Route Secret (`PATH_SECRET`)
- Generated via `secrets.token_hex(24)` (`48 hex chars` / `192 bits` of entropy).
- Requests that do not match `/{PATH_SECRET}/mcp` (or `/web` when authenticated) are immediately rejected before touching the MCP router.

### Layer 3 — Voice-Normalized SHA-256 Spoken Passphrase Deadbolt (`PASS_HASH`)
- Even if a client knows the full URL, **the bridge starts in a `LOCKED` state**.
- All session, workspace, bucket, and telemetry endpoints refuse to return private data until unlocked via `unlock_sessions(spoken_passphrase=...)`, an inline `spoken_passphrase` parameter, or `X-Nexus-Passphrase` in `/web`.
- **Voice-Normalized Hashing (`normalize_phrase`)**:
  - Converts input to lowercase and strips all whitespace and punctuation (`re.sub(r"[^a-z0-9]", "", phrase.lower())`) before computing SHA-256 (`hashlib.sha256(...).hexdigest()`).
  - Compares against `PASS_HASH` in constant time (`hmac.compare_digest`) so speech-to-text punctuation differences on mobile never cause false rejections, and the plaintext passphrase is never stored on disk.
- **Sliding Inactivity TTL (`TTL_SECONDS`)**:
  - Automatically re-locks the bridge after `TTL_SECONDS` (default `7200s`, minimum `300s`), or immediately when `lock_bridge()` is invoked.

### Layer 4 — Zero-Trust Host Companion Bridge (`host_bridge/agy_host_bridge.py`)
- **Loopback-Only Default Binding (`127.0.0.1:8098`)**:
  - `HOST_BRIDGE_BIND_HOST` defaults strictly to `127.0.0.1` (both in code and `systemd/agy-host-bridge.service`), preventing LAN exposure on native installs.
- **Peer CIDR Allowlist (`HOST_BRIDGE_ALLOWED_CIDRS`)**:
  - Restricts `/agentapi` socket peers to `127.0.0.0/8,::1/128,172.16.0.0/12` (loopback and local Docker bridge gateways), dropping LAN peers with `403 Forbidden` even when Docker bridge routing is enabled.
- **Mandatory Constant-Time Shared Secret (`X-Bridge-Token`, Fail-Closed)**:
  - Every `POST /agentapi` request must carry a 256-bit `X-Bridge-Token` (`HOST_BRIDGE_TOKEN` generated in `secrets.env`, or domain-separated `HMAC-SHA256(PATH_SECRET, "agy-host-bridge-agentapi-v1")`) verified via `hmac.compare_digest`. If no secret (`>= 32` chars) is configured, the daemon refuses to start and fails closed (`503`).
- **Browser CSRF & Request Envelope Hardening**:
  - Rejects any request carrying a browser `Origin` header (`403`), rejects `OPTIONS` preflights (`405`), requires `Content-Type: application/json`, and caps request bodies at `1 MB` (`413`).

### Layer 5 — Zero-Trust LAN-Only `agy-praxis-mcp` Doorway (`/praxis/{PRAXIS_MCP_TOKEN}/mcp` & Legacy `/polyglot/`)
- **Domain-Separated 192-Bit Capability Token**:
  - Verified in constant time (`hmac.compare_digest`) against `PRAXIS_MCP_TOKEN` (`>= 32` chars) or `HMAC-SHA256(PATH_SECRET, "agy-praxis-mcp-v1")[:48]` (with backward-compatible `/polyglot/{POLYGLOT_MCP_TOKEN}/mcp` verification), failing closed (`503`) if unconfigured.
- **Anti-Proxy, Anti-CSRF & Anti-DNS-Rebinding Enforcement (`403 Forbidden`)**:
  - Immediately rejects any request carrying reverse-proxy/tunnel headers (`X-Forwarded-For`, `X-Real-IP`, `Forwarded`, `CF-Connecting-IP`, `X-Forwarded-Proto`, `X-Forwarded-Host`), any browser `Origin` header, any non-local `Host` header (only loopback IPs, `localhost`, `.lan` / `.local`, or private RFC1918 literals are accepted), or any non-private socket peer IP.
- **Sensitive-File Exclusion & `0700`/`0600` Index Permissions**:
  - Incremental SHA-256 index files (`~/.local/share/ag-bridge-mcp/polyglot_index/`) and staged handoff queues are written atomically with `0700` directory and `0600` file permissions, excluding sensitive filenames (`secrets.env`, `.env.*`, `mcp_config.json`, private keys/tokens) and redacting inline YAML scalar values.

---

## 2. File, Bucket, Media & Workspace Sandboxing

- **Read-Only Default for Research Tools**:
  - `list_saved_sessions`, `load_session_into_gemini`, `ask_workspace_readonly`, `inspect_git_diff`, `get_session_tree`, `polyglot_map`, `polyglot_search`, `polyglot_outline`, and `praxis_handoff_inbox` open SQLite databases in `?mode=ro` read-only URI mode (closed deterministically via `try/finally`) and never mutate source files.
- **Strict Path Traversal, Bucket `.zip` & Host `git-inspect` Sandboxing**:
  - Every file path resolved by `src/agy_nexus/search.py`, `src/agy_nexus/workspace.py`, `src/agy_nexus/bucket_api.py` (including `POST /web/api/sessions/{conv_id}/download-zip` and session file readers), `src/agy_nexus/uploads.py`, and `src/agy_nexus/polyglot_index.py` is canonicalized via `Path.resolve()` and checked with `.is_relative_to(allowed_root)` before access, explicitly blocking umbrella parent directories (`$HOME`, `/`, `~/gitlab`, `~/github`) and rejecting `../` or absolute-path escapes with `403 Forbidden`.
  - Fail-closed target resolution (`src/agy_nexus/target_resolver.py`) prevents cross-project handoff contamination and blocks accidental creation of unregistered workspace directories unless `create_new_project=True` is explicitly passed.
  - Host `git-inspect` (`host_bridge/bridge_security.py`) restricts inspection strictly to configured workspace pillars and `AGY_DATA_DIR/worktrees` and strips leading dashes on git refs to prevent option injection (`CWE-88`).
- **7-Day Ephemeral HMAC-SHA256 Media & Deep-Link Signing (`src/agy_nexus/media.py`)**:
  - `/web/media/{exp}/{hmac}/{scope}/{rel_path}` URLs and PWA `workspace_url` deep links are signed with `PATH_SECRET` (7-day `604800s` TTL), reject 12-hex Docker container hostnames and private `.lan` leaks on public links, and strip `PATH_SECRET` from public origins.

---

## 3. Secret Storage Requirements

- Runtime secrets (`SUBDOMAIN_HASH`, `PATH_SECRET`, `PASS_HASH`, `HOST_BRIDGE_TOKEN`, and optional `PRAXIS_MCP_TOKEN` / `POLYGLOT_MCP_TOKEN`) **must** live outside the Git repository in `~/.config/ag-bridge-mcp/secrets.env` with `0600` (`-rw-------`) file permissions.
- Never commit `secrets.env` or passphrases to version control.

---

## 4. Reporting a Vulnerability & Security Acknowledgments

If you discover a security vulnerability in **AGY-Nexus MCP**:
1. **Do not** open a public issue containing exploit details or live credentials.
2. Open a private GitHub Security Advisory on the repository's **Security $\rightarrow$ Advisories** tab with reproduction steps and affected module names in `src/agy_nexus/` or `host_bridge/`.

### Acknowledgments
- **Shiqiang Chen** (Independent Researcher) — Responsible disclosure of unauthenticated host bridge exposure and `$HOME` `git-inspect` scope (`CWE-306`), remediated in `v2.6.0`.
