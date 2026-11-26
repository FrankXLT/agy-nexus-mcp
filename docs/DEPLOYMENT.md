# `agy-nexus-mcp` Setup & Deployment Guide

`agy-nexus-mcp` connects Google Gemini (Web and Mobile) to your local Antigravity sessions and gives you a live `/web` dashboard to track activity, inspect code changes, and browse session captures.

### Two-Doorway Setup (Remote HTTPS vs. Local IDE)

To keep remote access locked down without slowing down your local workstation, `agy-nexus-mcp` uses **two separate doorways**:

1. **Remote HTTPS Doorway (`ag-bridge-mcp`)**: Used by Google Gemini on Web and Mobile over HTTPS (`https://ag-{SUBDOMAIN_HASH}.<your-domain>/{PATH_SECRET}/mcp`). It pairs a private random URL with a **Thirty-Minute Passphrase Lock** (configurable auto-lock timeout).
2. **Local IDE Doorway (`agy-praxis-mcp` & `--stdio` Mode)**: Used on your own machine or LAN (`http://<host>.lan:8765/praxis/<PRAXIS_MCP_TOKEN>/mcp`, plus legacy `/polyglot/`). It needs no spoken passphrase, blocks any request arriving through a public reverse proxy (`403 Forbidden`), and also runs directly inside local IDEs via the `--stdio` container (`ghcr.io/frankxlt/agy-nexus-mcp:4.2.0 --stdio`) with zero open ports.

---

## 1. Set Up Your Passphrase, Secret URL & Lock Timer

All secrets stay outside the Git repository in `~/.config/ag-bridge-mcp/secrets.env` (`0600` file permissions).

Run the interactive setup helper:
```bash
python3 scripts/init_secrets.py --domain <your-domain>
```
Enter a passphrase when prompted (punctuation and capitalization are ignored so voice dictation works smoothly; only its SHA-256 hash is saved). The script writes `~/.config/ag-bridge-mcp/secrets.env` with:
- `SUBDOMAIN_HASH`: 12-character random subdomain (`ag-{SUBDOMAIN_HASH}`)
- `AG_BRIDGE_DOMAIN` & `AG_BRIDGE_PUBLIC_URL`: Public `https://` origin (`https://ag-{SUBDOMAIN_HASH}.<your-domain>`, without `PATH_SECRET`) used for 7-day signed `/web/media/` and dashboard links
- `PATH_SECRET`: 48-character random URL path (`192 bits`)
- `PASS_HASH`: SHA-256 hash of your normalized passphrase
- `HOST_BRIDGE_TOKEN`: 64-character secret used by `agy-host-bridge` `/agentapi` calls
- `PRAXIS_MCP_TOKEN` *(optional override; defaults to `HMAC-SHA256(PATH_SECRET, "agy-praxis-mcp-v1")[:48]`, alongside legacy `POLYGLOT_MCP_TOKEN`)*
- `TTL_SECONDS`: Inactivity auto-lock timer (`7200` default = 2 hours; set `TTL_SECONDS=1800` for a **Thirty-Minute Passphrase Lock**, with a `300`-second / 5-minute minimum via `MIN_TTL_SECONDS`)
- `BIND_HOST`: `0.0.0.0` (MCP server port `8765`)
- `HOST_BRIDGE_BIND_HOST`: `127.0.0.1` (host companion port `8098`; set to `172.17.0.1` on Linux if running `ag-bridge-mcp` inside Docker bridge networking)

To change your passphrase later while keeping your existing URL and tokens:
```bash
python3 scripts/init_secrets.py --keep-existing-urls
```

---

## 2. Start the Host Companion Service (`agy-host-bridge.service`)

`agy-nexus-mcp` reads your chats and repositories directly, and calls a small companion service on `127.0.0.1:8098` whenever it needs to wake an Antigravity chat (`agentapi send-message` / `new-conversation`), register a new project (`CreateProject`), or check host worktree git state. Every `POST /agentapi` request checks `X-Bridge-Token` from `~/.config/ag-bridge-mcp/secrets.env`.

Install and start the user service:
```bash
cp systemd/agy-host-bridge.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now agy-host-bridge.service
```

Check health and authenticated discovery (requests without a valid token return `401`):
```bash
curl -s http://127.0.0.1:8098/health

BRIDGE_TOK=$(grep '^HOST_BRIDGE_TOKEN=' ~/.config/ag-bridge-mcp/secrets.env | cut -d= -f2)
curl -s -X POST http://127.0.0.1:8098/agentapi \
  -H "Content-Type: application/json" \
  -H "X-Bridge-Token: ${BRIDGE_TOK}" \
  -d '{"action": "discover"}'
```
Expected response:
```json
{
  "ok": true,
  "ls_address": "localhost:<port>",
  "app_data_dir": "/home/<user>/.gemini/antigravity"
}
```

---

## 3. Start the `agy-nexus-mcp` Server

### Option A: Docker Compose / Portainer (Recommended)
Deploy `docker-compose.yml` with these volume mounts and port mapping:
- `~/.config/ag-bridge-mcp` $\rightarrow$ `/config:ro`
- `~/.gemini/antigravity` $\rightarrow$ `/home/<user>/.gemini/antigravity:rw`
- `~/agentic_workspace` $\rightarrow$ `/home/<user>/agentic_workspace:ro` (`projects/`, `devops/`, `ideation/`, plus optional legacy `~/gitlab:ro`)
- `~/.gemini/config` $\rightarrow$ `/home/<user>/.gemini/config:ro`
- Port: `8765:8765`

### Option B: Direct Systemd User Service
```bash
python3 -m venv ~/.local/share/ag-bridge-mcp/venv
~/.local/share/ag-bridge-mcp/venv/bin/pip install -r requirements.txt
cp systemd/ag-bridge.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now ag-bridge.service
```

### Option C: Public GHCR OCI Container (`--stdio` Mode for Local IDEs)
Run directly inside VS Code, Copilot CLI, Claude Code, or MCP Inspector over zero-stdout JSON-RPC without opening an HTTP port or needing `PATH_SECRET`:
```bash
docker run -i --rm ghcr.io/frankxlt/agy-nexus-mcp:4.2.0 --stdio
```
To unlock private session and workspace tools in `--stdio` mode, pass a 64-hex `PASS_HASH` (or mount `secrets.env` with `-e AG_BRIDGE_ENV_FILE=/config/secrets.env`):
```bash
docker run -i --rm \
  -e PASS_HASH="<your-64-hex-sha256>" \
  -v "${HOME}/.gemini/antigravity:${HOME}/.gemini/antigravity:rw" \
  -v "${HOME}/agentic_workspace:${HOME}/agentic_workspace:ro" \
  ghcr.io/frankxlt/agy-nexus-mcp:4.2.0 --stdio
```
- **First-Push GHCR Visibility Recovery (`Package validation failed`)**: GitHub creates new `ghcr.io/<owner>/<repo>` packages as Private on the first tagged push. If `Publish GHCR OCI & MCP Registry` fails at `./mcp-publisher publish`, open **GitHub Package Settings -> Change visibility -> Public** once, then re-run **Actions -> Publish GHCR OCI & MCP Registry -> Run workflow** (`workflow_dispatch`, `release_tag`: `v4.2.0`).

---

## 4. Reverse Proxy Setup (Nginx Proxy Manager & Cloudflare)

### Step 1: DNS Record
Create an `A` or `CNAME` record for `ag-{SUBDOMAIN_HASH}.<your-domain>` pointing to your reverse proxy or Cloudflare Tunnel.

### Step 2: Nginx Proxy Manager (NPM)
1. Create a **Proxy Host**:
   - **Domain Names**: `ag-{SUBDOMAIN_HASH}.<your-domain>`
   - **Scheme**: `http`
   - **Forward Hostname**: `<host>.lan`
   - **Forward Port**: `8765`
   - **Cache Assets**: `OFF`
   - **Block Common Exploits**: `ON`
   - **Websockets Support**: `ON`
2. **SSL Tab**:
   - Certificate: `*.<your-domain>`
   - **Force SSL**: `ON`
   - **HTTP/2 Support**: `ON`
3. **Advanced Tab (Allows `/mcp` + 7-Day Signed `/web/media/` Links & Disables Buffering)**:
   Paste these Nginx rules so streamed MCP responses arrive right away, Gemini mobile query parameters like `?hl=en-US` pass through cleanly, and `/web` stays off the public MCP subdomain:
   ```nginx
   if ($request_method !~ ^(GET|HEAD|POST|DELETE|OPTIONS)$) {
       return 405;
   }
   if ($request_uri ~* "(\.\.|%2e%2e)") {
       return 404;
   }
   if ($request_uri !~ "^(/[0-9a-f]{48}/mcp([/?].*)?|/web/media/[0-9]+/[0-9a-f]{32}/[^?]+(\?.*)?)$") {
       return 404;
   }

   proxy_buffering off;
   proxy_cache off;
   proxy_request_buffering off;
   proxy_http_version 1.1;
   proxy_set_header Connection "";
   proxy_read_timeout 3600s;
   proxy_send_timeout 3600s;
   chunked_transfer_encoding on;
   add_header X-Accel-Buffering no always;
   ```

---

## 5. Connect Google Gemini, Local `agy-praxis-mcp` & the `/web` App

### Connect in Google Gemini
1. Open Google Gemini (`gemini.google.com`) $\rightarrow$ **Settings** $\rightarrow$ **Connected Apps** $\rightarrow$ **Add Custom MCP Server**.
2. Enter:
   - **Server Name**: `agy-nexus-mcp`
   - **Server URL**: `https://ag-{SUBDOMAIN_HASH}.<your-domain>/{PATH_SECRET}/mcp`
   - **Transport**: `Streamable HTTP / SSE`
3. Save and check that the status reads **Connected**.

### Connect `agy-praxis-mcp` in Your Local IDE (LAN-Only, Deadbolt-Free)
The local workstation doorway (**`agy-praxis-mcp`**, 6 tools: `polyglot_map`, `polyglot_search`, `polyglot_outline`, `praxis_handoff_inbox`, `praxis_claim_handoff`, `praxis_update_handoff`) gives your IDE fast code outlines and `<repo-slug>-NN` handoff access. Requests to `/praxis/*` (and `/polyglot/*`) immediately return `403 Forbidden` if they carry reverse-proxy headers (`X-Forwarded-For`, `CF-Connecting-IP`, etc.), browser `Origin` headers, or public `Host` names.

Add it to `~/.gemini/config/mcp_config.json` (and `~/.gemini/antigravity/mcp_config.json` if used):
```json
{
  "mcpServers": {
    "agy-praxis-mcp": {
      "serverUrl": "http://<host>.lan:8765/praxis/<PRAXIS_MCP_TOKEN>/mcp"
    }
  }
}
```
*(You can copy the exact `serverUrl` printed by `init_secrets.py`, or run `python3 -m agy_nexus.tools_praxis --stdio` locally over stdio.)*

### Open the `/web` Dashboard & Install as an App (PWA)
- **Local Network (HTTP)**: `http://<host>.lan:8765/web` (append `?demo=1` for sample data, or `#workspace` for the 2-Pane Workspace Explorer)
- **Secret Path (HTTPS)**: `https://ag-{SUBDOMAIN_HASH}.<your-domain>/{PATH_SECRET}/web`
- **Dedicated Dashboard Hostname (HTTPS — Recommended for App Install & Deep Links)**:
  Create a second SSL proxy host in Nginx Proxy Manager (for example, `https://agy-mcp.<your-domain>`) forwarding to `http://<host>.lan:8765` with this **Advanced** snippet so `/` and `/web/*` work while `/mcp` and `/praxis/*` remain unreachable there:
  ```nginx
  if ($request_method !~ ^(GET|HEAD|POST|OPTIONS)$) {
      return 405;
  }
  if ($request_uri !~ "^/(web([/?].*)?)?$") {
      return 404;
  }
  proxy_buffering off;
  ```
  - **Install on Mobile or Desktop Chrome**: Visit `https://agy-mcp.<your-domain>/web`, open **Settings (`⚙`)**, and click **Install App** (or Chrome **⋮ → Install page as app…**).
  - **Desktop Window (`--app` Mode)**:
    ```bash
    google-chrome --app="https://agy-mcp.<your-domain>/web" --class="AGYNexusOverwatch" --window-size=1440,960
    ```

### 7-Day Signed `/web/media/` Links & Screenshot Sharing
- **7-Day Signed Links**: `/web/media/{exp}/{sig}/{scope}/{filename}` URLs (`604800s` / 7-day lifetime) and `workspace_url` deep links automatically use your verified public `https://` origin, keep `PATH_SECRET` out of media URLs, ignore trailing query parameters like `?hl=en-US`, and reject private `.lan` or container hostnames.
- **Multi-Select Gallery**: In `/web#workspace`, select captures with checkboxes, `Shift+Click`, or drag-select to share via **Web Share API v2**, copy a **`<canvas>` Contact Sheet**, or download a **`.zip` archive** (`POST /web/api/sessions/{conv_id}/download-zip`).
- **In-Chat Visual Inspection**: `inspect_visual_artifacts(session_identifier="...", artifact_filter="...", max_images=2)` sends compact WebP previews (`max_edge=840px`) within the `< 20 KB` wire limit alongside 7-day HTTPS links.

---

## 6. Viewing Request Logs & Troubleshooting

Every request prints a single clean log line with zero secrets or passphrases:
```bash
# Docker / Portainer:
docker logs -f --tail 50 ag-bridge-mcp

# Systemd user service:
journalctl --user -u ag-bridge.service -f
```
Example output:
```text
[*] Starting ag-bridge-mcp on 0.0.0.0:8765 (stateless_http=True, json_response=True)
[agy-nexus] http=POST rpc=tools/list tool=- status=200 bytes=9420 ms=1
[agy-nexus] http=POST rpc=tools/call tool=unlock_sessions status=200 bytes=11420 ms=34
[agy-nexus] http=POST rpc=tools/call tool=load_session_into_gemini status=200 bytes=19374 ms=48
[agy-nexus] http=POST rpc=tools/call tool=get_session_tree status=200 bytes=14210 ms=19
[agy-nexus] http=GET rpc=web_stats tool=last_90d status=200 bytes=18412 ms=6
```
`rpc=` and `tool=` name the call, `bytes=` confirms responses stay under `20 KB` so Gemini Mobile and Web stay responsive, and `ms=` shows execution time.

---

## 7. Automated Tests, Price Book Sync & Three-Route Public Project Site (`v4.2.0`)

Run the test suite, built-in self-tests, and sync checks anytime:
```bash
uv run --with pytest --with pytest-asyncio pytest
python3 ag_bridge.py --self-test
python3 -m agy_nexus.tools_praxis --self-test
python3 scripts/sync_agents.py --check
python3 scripts/catalog_sync.py --render-docs --check

AG_BRIDGE_URL="http://127.0.0.1:8765/${PATH_SECRET}/mcp" \
AG_BRIDGE_PASSPHRASE="<your passphrase>" \
uv run python3 tests/run_permutation_suite.py
```

### Shared Price Book Sync (`catalog_override.json` & `bot/catalog-sync`)
- **Opt-In Updates (`/web` & `${AGY_DATA_DIR}/catalog_override.json`)**: Live `/web` checks `raw.githubusercontent.com/FrankXLT/agy-nexus-mcp/main/src/agy_nexus/data/` at most once every 24h (continuing smoothly if offline). Saving an update writes to `${AGY_DATA_DIR}/catalog_override.json` (`chmod 600`) without touching your checkout.
- **Weekly Automated PRs (`.github/workflows/catalog-sync.yml`)**: Updates changed `public_api` / `cost_ledger.json` rates (`antigravity_ide` stays locked), refreshes `docs/PRICING_HISTORY.md`, runs `pytest`, and updates one `bot/catalog-sync` PR targeting `main`. Enable **Allow GitHub Actions to create and approve pull requests** and protect `main` with PR approval + the **`verify`** status check.

### Build the Three-Route Public Project Site (`build/gh-pages/`)
Build the privacy-checked static site for GitHub Pages (`./` landing overview, `./demo/` interactive sample dashboard & workspace, and `./docs/` documentation hub):
```bash
python3 scripts/build_github_showcase.py            # Generates ./, ./demo/, and ./docs/ under build/gh-pages/
python3 scripts/build_github_showcase.py --refresh  # Refresh bundled sample data and PNGs first
python3 scripts/publish_to_github.py --dry-run
python3 scripts/publish_to_github.py                # Pushes main + gh-pages + configures GitHub Pages + Release
```
Every build strips PNG metadata, hashes private identifiers via SHA-256, and verifies zero leaks with `scan_showcase_privacy()`.
