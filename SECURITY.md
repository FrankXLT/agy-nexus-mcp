# Security Policy & 3-Layer Deadbolt Architecture

**AGY-Nexus MCP** (`agy-nexus-mcp`) bridges public cloud AI surfaces (Gemini Mobile, Gemini Web) to your private local Antigravity IDE workspaces. Security is treated as a first-class architectural invariant.

---

## 1. Three-Layer Zero-Trust Defense Model

Every incoming request to AGY-Nexus MCP is protected by three independent security barriers:

### Layer 1 — Unlisted Subdomain (`SUBDOMAIN_HASH`)
- Generated via `scripts/init_secrets.py` using CSPRNG (`secrets.token_hex(6)`).
- Prevents automated subdomain enumeration and opportunistic scanners from discovering the bridge endpoint.

### Layer 2 — 192-Bit Unguessable Route Secret (`PATH_SECRET`)
- Generated via `secrets.token_hex(24)` (`48 hex chars` / `192 bits` of entropy).
- Requests that do not match `/{PATH_SECRET}/mcp` (or `/web` when authenticated) are immediately rejected before touching the MCP router.

### Layer 3 — Voice-Normalized SHA-256 Spoken Passphrase Deadbolt (`PASS_HASH`)
- Even if a client knows the full URL, **the bridge starts in a `LOCKED` state**.
- All session, workspace, and telemetry tools refuse to return data until unlocked via `unlock_sessions(spoken_passphrase=...)` or an inline `spoken_passphrase` parameter.
- **Voice-Normalized Hashing (`normalize_phrase`)**:
  - Converts input to lowercase and strips all whitespace and punctuation (`re.sub(r"[^a-z0-9]", "", phrase.lower())`) before computing SHA-256 (`hashlib.sha256(...).hexdigest()`).
  - Compares against `PASS_HASH` in constant time (`hmac.compare_digest`) so speech-to-text punctuation differences on mobile never cause false rejections, and the plaintext passphrase is never stored on disk.
- **Sliding Inactivity TTL (`TTL_SECONDS`)**:
  - Automatically re-locks the bridge after `TTL_SECONDS` (default `7200s`, minimum `300s`), or immediately when `lock_bridge()` is invoked.

---

## 2. File & Workspace Sandboxing

- **Read-Only Default for Research Tools**:
  - `list_saved_sessions`, `load_session_into_gemini`, `ask_workspace_readonly`, `inspect_git_diff`, `get_quota_and_system_stats`, and `audit_multi_repo_drift` open SQLite databases in `?mode=ro` read-only URI mode and never mutate source files.
- **Strict Path Traversal Prevention**:
  - Every file path resolved by `src/agy_nexus/search.py` and `src/agy_nexus/workspace.py` is canonicalized via `Path.resolve()` and checked with `.is_relative_to(workspace_root)` before access.

---

## 3. Secret Storage Requirements

- Runtime secrets (`SUBDOMAIN_HASH`, `PATH_SECRET`, `PASS_HASH`) **must** live outside the Git repository in `~/.config/ag-bridge-mcp/secrets.env` with `0600` (`-rw-------`) file permissions.
- Never commit `secrets.env` or passphrases to version control.

---

## 4. Reporting a Vulnerability

If you discover a security vulnerability in **AGY-Nexus MCP**:
1. **Do not** open a public issue containing exploit details or live credentials.
2. Open a private GitHub Security Advisory on the repository's **Security $\rightarrow$ Advisories** tab with reproduction steps and affected module names in `src/agy_nexus/`.
