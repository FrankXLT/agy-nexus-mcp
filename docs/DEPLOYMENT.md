# `agy-nexus-mcp` Setup & Deployment Guide

`agy-nexus-mcp` connects Google Gemini (Web and Mobile) to your local Antigravity sessions and serves a live `/web` usage dashboard. It protects your workstation with two simple layers:
1. **Private Route URL**: A random subdomain and secret URL path (`https://ag-{SUBDOMAIN_HASH}.<your-domain>/{PATH_SECRET}/mcp`).
2. **Spoken or Typed Passphrase**: Punctuation- and case-insensitive passphrase verification (stored only as a SHA-256 hash) with a 2-hour (`7200s`) inactivity auto-lock.

---

## 1. Generate Your Passphrase & Secret URL

All secrets live outside the Git repository in `~/.config/ag-bridge-mcp/secrets.env` (`0600` file permissions).

Run the interactive setup script:
```bash
python3 scripts/init_secrets.py --domain <your-domain>
```
You'll be prompted for a passphrase. The script writes `~/.config/ag-bridge-mcp/secrets.env` with:
- `SUBDOMAIN_HASH`: 12-character random subdomain (used as `ag-{SUBDOMAIN_HASH}`)
- `PATH_SECRET`: 48-character random URL path
- `PASS_HASH`: SHA-256 hash of your normalized passphrase
- `HOST_BRIDGE_TOKEN`: 64-character shared secret authenticating local `agy-host-bridge` `/agentapi` RPCs
- `TTL_SECONDS`: `7200` (2-hour inactivity lock timer)
- `BIND_HOST`: `0.0.0.0` (MCP server port `8765`)
- `HOST_BRIDGE_BIND_HOST`: `127.0.0.1` (loopback-only host companion port `8098`; set to `172.17.0.1` on Linux if running `ag-bridge-mcp` inside Docker bridge networking)

To change your passphrase later without changing your MCP URL or host bridge token:
```bash
python3 scripts/init_secrets.py --keep-existing-urls
```

---

## 2. Start the Host Companion Service (`agy-host-bridge.service`)

`agy-nexus-mcp` reads your chats and git repositories directly, and uses an authenticated loopback companion service on `127.0.0.1:8098` whenever it needs to wake up an Antigravity session (`agentapi send-message` / `new-conversation`) or inspect worktree git state on the host. Every `POST /agentapi` call requires `X-Bridge-Token` from `~/.config/ag-bridge-mcp/secrets.env`.

Install and start the user service:
```bash
cp systemd/agy-host-bridge.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now agy-host-bridge.service
```

Verify liveness and authenticated `discover` access (unauthenticated requests return `401`):
```bash
curl -s http://127.0.0.1:8098/health

# Authenticated /agentapi check using HOST_BRIDGE_TOKEN from secrets.env:
 BRIDGE_TOK=$(grep '^HOST_BRIDGE_TOKEN=' ~/.config/ag-bridge-mcp/secrets.env | cut -d= -f2)
curl -s -X POST http://127.0.0.1:8098/agentapi \
  -H "Content-Type: application/json" \
  -H "X-Bridge-Token: ${BRIDGE_TOK}" \
  -d '{"action": "discover"}'
```
Expected output:
```json
{
  "ok": true,
  "ls_address": "localhost:<port>",
  "app_data_dir": "/home/<user>/.gemini/antigravity"
}
```

---

## 3. Run the `agy-nexus-mcp` Server

### Option A: Docker Compose / Portainer (Recommended)
Deploy using `docker-compose.yml`:
- `~/.config/ag-bridge-mcp` $\rightarrow$ `/config:ro`
- `~/.gemini/antigravity` $\rightarrow$ `/home/<user>/.gemini/antigravity:rw`
- `~/gitlab` $\rightarrow$ `/home/<user>/gitlab:ro`
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
   - Select your certificate (`*.<your-domain>`)
   - **Force SSL**: `ON`
   - **HTTP/2 Support**: `ON`
3. **Advanced Tab (Prevents Proxy Buffering on MCP Calls)**:
   Paste the following Nginx rules so responses stream immediately without buffering:
   ```nginx
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

## 5. Connect Google Gemini & Open the `/web` Dashboard

### Connect in Google Gemini
1. Open Google Gemini (`gemini.google.com`) $\rightarrow$ **Settings** $\rightarrow$ **Connected Apps** $\rightarrow$ **Add Custom MCP Server**.
2. Enter:
   - **Server Name**: `agy-nexus-mcp`
   - **Server URL**: `https://ag-{SUBDOMAIN_HASH}.<your-domain>/{PATH_SECRET}/mcp`
   - **Transport**: `Streamable HTTP / SSE`
3. Save and confirm the status shows **Connected**.

### Open the Web Dashboard & Install as a Chromium Standalone App (PWA)
- **Local Network (HTTP)**: `http://<host>.lan:8765/web`
- **Secret Path (HTTPS)**: `https://ag-{SUBDOMAIN_HASH}.<your-domain>/{PATH_SECRET}/web`
- **Dedicated Dashboard Hostname (HTTPS — Recommended for Mobile/Desktop PWA Install)**:
  - Because Chromium browsers require a trusted `https://` origin (or `http://localhost`) to enable native PWA installation (`beforeinstallprompt`) and Service Workers (`/web/sw.js`), you can optionally create a dedicated SSL proxy host in Nginx Proxy Manager (for example, `https://agy-mcp.<your-domain>`) forwarding to `http://<host>.lan:8765` with the following **Advanced** Nginx snippet to allow `/` and `/web/*` while keeping `/mcp` isolated on your secret subdomain:
    ```nginx
    if ($request_method !~ ^(GET|HEAD|POST|OPTIONS)$) {
        return 405;
    }
    if ($request_uri !~ "^/(web([/?].*)?)?$") {
        return 404;
    }
    proxy_buffering off;
    ```
  - **Install on Android / iOS / Desktop Chrome**: Open `https://agy-mcp.<your-domain>/web` and click the top-bar **App** button (or Chrome's **⋮ → Add to Home screen / Install page as app…**).
  - **Linux / macOS / Windows Workstation `--app` Mode**: Launch a frameless Chromium window directly from your terminal or desktop launcher:
    ```bash
    google-chrome --app="https://agy-mcp.<your-domain>/web" --class="AGYNexusOverwatch" --window-size=1420,960
    ```

---

## 6. Viewing Request Logs & Troubleshooting

`agy-nexus-mcp` logs each request on a single clean line without exposing your secret URL or passphrase in the logs.

### View Live Logs
```bash
# Docker / Portainer:
docker logs -f --tail 50 ag-bridge-mcp

# Systemd user service:
journalctl --user -u ag-bridge.service -f
```

### Example Log Output
```text
[*] Starting ag-bridge-mcp on 0.0.0.0:8765 (stateless_http=True, json_response=True)
[agy-nexus] http=POST rpc=tools/list tool=- status=200 bytes=7476 ms=1
[agy-nexus] http=POST rpc=tools/call tool=unlock_sessions status=200 bytes=11420 ms=34
[agy-nexus] http=POST rpc=tools/call tool=load_session_into_gemini status=200 bytes=19374 ms=142
[agy-nexus] http=GET rpc=web_stats tool=last_90d status=200 bytes=18412 ms=6
```

- **`rpc=` & `tool=`**: Shows which MCP method and tool ran.
- **`bytes=`**: Response size in bytes. `agy-nexus-mcp` keeps MCP tool responses under `20 KB` so Gemini Mobile and Web never stall on large payloads.
- **`ms=`**: Execution time in milliseconds.

---

## 7. Automated Test Suite

Run the end-to-end test suite anytime to verify all 9 MCP tools, passphrase locking, line-range file reads, and git diff pagination:
```bash
AG_BRIDGE_URL="http://127.0.0.1:8765/${PATH_SECRET}/mcp" \
AG_BRIDGE_PASSPHRASE="<your passphrase>" \
uv run python3 tests/run_permutation_suite.py
```
