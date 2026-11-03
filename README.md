# `agy-nexus-mcp` — Connect Google Gemini to Your Antigravity IDE, Projects & Usage Dashboard

`agy-nexus-mcp` is a self-hosted Model Context Protocol (MCP) server that connects **Google Gemini** (on the web or mobile app) directly to your local **Google Antigravity IDE / CLI** workstation.

From your phone or browser, you can check on running coding sessions, see what a paused session is waiting for, search and read local repository files, send research plans straight into the right project chat, view **three-tier ASCII usage stats** in chat, or open the **installable Chromium Web App (`/web`)** for live charts and model quota tracking.

---

## Live `/web` Dashboard & Installable Chromium App

![AGY-NEXUS Overwatch Desktop Dashboard — True Mon–Sun Calendar Heatmap, Sub-Daily Stacked Area Charts, Token Telemetry & Chromium Standalone App Launcher](docs/assets/dashboard-desktop.png)

<details>
<summary><strong>📱 View Mobile Layout (Centered <code>This Month — MTD</code> Calendar & Responsive Cards)</strong></summary>

<br/>

![AGY-NEXUS Overwatch Mobile Dashboard](docs/assets/dashboard-mobile.png)

</details>

---

## Best Features & Advantages

### 1. Control Your Coding Sessions from Anywhere
- **Browse All Sessions**: Lists your active, paused, and completed Antigravity chats with step counts, active branches, and task checklists.
- **See What Paused Sessions Need**: When an Antigravity chat pauses for confirmation (`STALLED_WAITING_APPROVAL`), you can see the exact tool, command, or file path waiting for your approval.
- **Smart Project Routing**: When you send research notes or instructions back to Antigravity (`send_handoff_and_resume`), the server automatically matches your target project name, workspace path, or repository keywords so your handoff always lands in the right chat—never in an unrelated project tab.

### 2. Built for Reliability on Gemini Web & Mobile
- **One-Call Bundled Responses**: Google Gemini's web and mobile confirmation cards can hang if an MCP server forces back-to-back tool calls in the same turn. Every tool in `agy-nexus-mcp` bundles the context you need into a single turn.
- **Fast `< 20 KB` Payloads**: Large files and git diffs are automatically sliced by line range (`src/app.py:100-250`) or paged so responses never time out over mobile or cloud connections.
- **Voice-Friendly Passphrase Lock**: Protected by a randomized URL path plus an interactive passphrase lock (`unlock_sessions`). It automatically strips punctuation and voice filler (like *"The passphrase is ..."*) so you can unlock it hands-free using Gemini Live or Mobile Voice, and auto-locks after a configurable timeout.

### 3. Installable Chromium App (PWA) & Visual Usage Dashboard (`/web`)
- **One-Click Standalone App**: Open `/web` over HTTPS and click the top-bar **`App`** button to install the dashboard as a native-feeling **Chromium Standalone App** on desktop or mobile (or copy the `--app=` terminal launcher).
- **Consistent `Mon–Sun` Activity Heatmap**: Every day sits on its real `Mon–Sun` row with a global color scale across **`This Month (MTD)`**, **`Last Month`**, **`Rolling 90 Days`**, and **`Rolling 52 Weeks`**, so switching views never scrambles day positions or shades.
- **4-Hour & 8-Hour Stacked Usage Charts**: Breaks down activity, subagent runs, and project usage into sub-daily 4-hour and 8-hour intervals instead of flat daily averages.
- **4 Themes & 4 Spacing Modes**: Choose between `Obsidian`, `Dark Paper`, `Warm Paper`, and `Pure White` themes alongside 4 compactness levels (`D1`–`D4`) in a single dropdown—automatically remembered in your browser.

---

## How to Set It Up & Use It

### Step 1: Run the Setup Script
Clone the repository on your workstation and run the interactive setup script to generate your passphrase hash, secret URL path, and local service config:

```bash
# Linux / macOS / WSL
./scripts/setup.sh

# Windows PowerShell
.\scripts\setup.ps1
```

Or run the self-test and start the server directly with `uv` or Python:

```bash
python3 scripts/init_secrets.py --passphrase "your-secret-passphrase"
python3 ag_bridge.py --self-test
python3 ag_bridge.py
```

*(See [DEPLOYMENT.md](DEPLOYMENT.md) for Docker Compose, reverse proxy, and Cloudflare Tunnel setup.)*

### Step 2: Connect It in Google Gemini
1. Open **Google Gemini** on the web $\rightarrow$ **Settings** $\rightarrow$ **Connected Apps** $\rightarrow$ **Add custom MCP server**.
2. Paste your secret MCP endpoint URL:
   `https://<your-subdomain>.<your-domain>/{PATH_SECRET}/mcp`
3. Open your dashboard in any browser at:
   `https://<your-dashboard-host>/web`

### Step 3: Everyday Prompts You Can Use in Gemini
Once connected, just talk or type naturally in Gemini Web or Gemini Mobile:
- **Unlock & check status**: *"Unlock Antigravity with passphrase [your phrase] and show me my active sessions."*
- **Inspect a session**: *"Load session 1 and tell me what it's working on or waiting for."*
- **Search & read code**: *"Search my workspace for the authentication middleware and read lines 50 to 150."*
- **Audit uncommitted git changes**: *"Check git diff across all my repositories to see what hasn't been committed yet."*
- **Send a plan back to Antigravity**: *"Send this implementation plan to my `web-dashboard-ui` session and wake it up in plan mode."*
- **View ASCII stats in chat**: *"Show me my latest usage stats"* (or ask for `quick` mobile view or `rich` desktop view).

---

## Three-Tier ASCII Usage Reports in Chat

When you ask Gemini for your usage stats (`manage_background_run(action="stats", period="last_90d", style=...)`), `agy-nexus-mcp` formats your live quota pools, `Mon–Sun` calendar heatmap, 8-hour activity curve, and project/subagent token breakdowns into one of **three plain-text layouts**:

| Style | Width | Best For | What It Shows |
| :--- | :---: | :--- | :--- |
| **`style="default"`** | **72 cols** | Standard Desktop & Tablet Chat | Split summary header, 22-week `Mon–Sun` heatmap, 8-hour activity & project stack (`░▒▓█`), model quota bars (`┼`), and full project & subagent tables. |
| **`style="quick"`** | **`<= 40` cols** | Phone Screens (Portrait) | Fits strictly within 40 characters per line so it never wraps on mobile. Shows a 13-week heatmap, 8-hour pace curve, model quota bars, and top projects/subagents. |
| **`style="rich"`** | **76 cols** | Widescreen Desktop Chat | Full box-drawn dashboard with side-by-side quota and token panels, 13-week 3-character heatmap with a Peak Day card, 6-row 8-hour activity curve, and share gauges. |

### 1. `style="default"` (72-Column Standard Layout)

```text
════════════════════════════════════════╤═══════════════════════════════
AGY-NEXUS // 90d (Nov 03 ◄── Aug 06)    ┆ EXTENDED TELEMETRY & AVERAGES 
════════════════════════════════════════╪═══════════════════════════════
GOOGLE 20x : 100.0% [████████┼█] HEALTHY┆ 0x 429s | Ultra-20x (T:>=90%) 
PARTNER 1x : 100.0% [░┼░░░░░░░░] ON PACE┆ 71.4% Wk Left | Lim <=14.3%/d 
STEPS/TOOLS: 187,877s | 93,195t | 54c   ┆ 4,369 s/act-d | 2,020 s/cal-d 
TOKEN BURN : ~69.3M Total (227 sub runs)┆ 1.61M tok/d   | 11.28M tok/wk 
MCP WIRE   : 100% <20KB (avg 3.0/17.5 KB┆ 77 Reqs (62.5k tok) | Gemini W
────────────────────────────────────────┴───────────────────────────────
DAILY HEATMAP (NOW: W01 ──► 22w AGO)   Peak: 10/31 (11,118s) | Act: 43d
Wk    01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22
Mon   ▒▒ ██ ░░ ▒▒ ▓▓ ▒▒ ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ··
Tue   ░░ ▓▓ ▒▒ ▒▒ ▒▒ ░░ ░░ ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ··
Wed   ·· ▓▓ ░░ ░░ ▒▒ ▓▓ ░░ ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ··
Thu   ·· ██ ░░ ▒▒ ▓▓ ██ ░░ ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ··
Fri   ·· ▓▓ ██ ▓▓ ▒▒ ▓▓ ▓▓ ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ··
Sat   ·· ██ ██ ░░ ▒▒ ██ ██ ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ··
Sun   ·· ██ ██ ▓▓ ▓▓ ██ ▒▒ ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ··
Vol   ▁▁ ██ ▅▅ ▃▃ ▄▄ ▅▅ ▃▃ ── ── ── ── ── ── ── ── ── ── ── ── ── ── ──
────────────────────────────────────────────────────────────────────────
8H SUB-DAILY PACE (NOW ──► SEP 21)   [Avg: 1.5k/8h | Peak: 3.7k | ░▒▓█]
3.7k ╷     █        ▄▄                                                 
1.9k ┤   ▄██  ▄▄  ▄████▄                     ▄    █▄  ▄▄      ▄        
1.5k ┼──▄████▄██▄███████───▄──▄──█──────█▄──▄█───████████───▄─███──────
   0 ╵ ▄▒█▒▒▓▓█████▒█▒▒▒▒▄▒▒▄▒▒▄▄███▄▄█▓███▄████████████▓▓▄▓▓▓▓▓▓▄▓▄   
     └─▲────────────▲────────────▲────────────▲────────────▲──────────▲─
      Nov 03       Oct 26       Oct 17       Oct 08       Sep 29     Sep
      Stack: [█] core-platform (42%)  [▓] web-dashboard (25%)  [▒] agent
────────────────────────────────────────────────────────────────────────
MODEL QUOTA vs TARGET (┼ = Target Pin)      CALLS   EST TOK  DELTA  STAT
Argon 4 Pro [████████████┼█▓░░░░░]  70.4%   77,856    ~18.0M  +5.4%  OK
Flash 3.8   [█████┼▓░░░░░░░░░░░░░]  29.6%   32,675  FastTier  +4.6%  OK
Claude 5.5  [░░┼░░░░░░░░░░░░░░░░░]   0.0%       31         0  -8.0%  OK
GPT-OSS 120 [▏░░░░░░░░░░░░░░░░░░░]   0.0%        0         0  -2.0%  OK
────────────────────────────────────────────────────────────────────────
WORKSPACES (9)       CHATS   STEPS   TOTAL TOK  TOK/DAY   TOK/WK   SHARE
1. core-platform-ap  10c  65,811     ~29.2M     679k    4.75M   42.1%
2. web-dashboard-ui  19c  45,032     ~17.2M     400k    2.80M   24.8%
3. agent-orchestrat   5c  20,107     ~16.5M     384k    2.69M   23.8%
4. cloud-infra-gito   8c   5,991      ~2.2M      52k     362k    3.2%
5. mobile-sync-engi   1c   5,092      ~2.0M      46k     322k    2.9%
6. telemetry-pipeli   7c   2,878      ~897k      21k     146k    1.3%
7. auth-gateway       2c   2,691      ~1.0M      23k     164k    1.5%
8. docs-portal        1c   1,126      ~294k     6.8k      48k    0.4%
9. sdk-client-py      1c      21      ~4.5k      104      727    0.0%
────────────────────────────────────────────────────────────────────────
SUBAGENTS (8)         RUNS   STEPS   TOTAL TOK  TOK/DAY   TOK/WK   SHARE
1. flash-surgeon    116r  21,704      ~8.9M     207k    1.45M   58.2%
2. flash-auditor     78r   8,170      ~2.7M      63k     441k   17.7%
3. argon-sentinel     3r   3,142      ~1.3M      30k     209k    8.4%
4. flash-scout       20r   2,801      ~1.1M      25k     173k    6.9%
5. argon-surgeon      2r   2,287      ~920k      21k     150k    6.0%
6. research           5r     862      ~333k     7.7k      54k    2.2%
7. argon-architect    2r     132     ~64.2k     1.5k      10k    0.4%
8. claude-specialis   1r      31     ~16.3k      380     2.7k    0.1%
════════════════════════════════════════════════════════════════════════
```

### 2. `style="quick"` (40-Column Mobile Layout)

```text
════════════════════════════════════════
AGY-NEXUS // 90d (Nov 03 ◄── Aug 06)
════════════════════════════════════════
G-20x: 100% [████████┼█] OK | 0x 429s
P-1x : 100% [░┼░░░░░░░░] OK | 71% WkLft
Steps:187.9k | Tools:93.2k | Act:43d
Burns:~69.3M | 1.61M/d | 11.28M/wk
────────────────────────────────────────
HEATMAP (NOW ──► 13w Ago)  │ PEAK & VOL
Mo ▒█░▒▓▒·······           │ Pk: 10/31
Tu ░▓▒▒▒░░······           │ 11,118 step
We ·▓░░▒▓░······           │ Avg:4,369/d
Th ·█░▒▓█░······           │ Chats: 54c
Fr ·▓█▓▒▓▓······           │ Subs : 227r
Sa ·██░▒██······           │ Tok/d:1.61M
Su ·██▓▓█▒······           │ Tok/w:11.28
────────────────────────────────────────
8H PACE & STACK (NOW──►OLD) Pk:3.2k
3.2k╷  ▄   █▄▄                       
1.6k┤  █ █ ███             ▄▄   █▄   
1.4k┼─▄███▄███─▄──▄───█▄▄─███▄─▄██───
   0╵ ▒▒▓████▒▄▒▒▒██▓▓███████▓▄▓▓▓▓  
────────────────────────────────────────
MODEL QUOTA (┼=Target)  PCT   TOK   DLT
Argon 4 [██████┼▓░░]  70% 18.0M   +5%
Flash38 [██┼▓░░░░░░]  30%  Fast   +5%
Claude5 [░┼░░░░░░░░]   0%     0   -8%
GPT-120 [▏░░░░░░░░░]   0%     0   -2%
────────────────────────────────────────
WORKSPACES & SUBS  TOK   TOK/D   TOK/WK
core-platform-ap 29.2M   679k   4.75M
web-dashboard-ui 17.2M   400k   2.80M
agent-orchestrat 16.5M   384k   2.69M
cloud-infra-gito  2.2M    52k    362k
mobile-sync-engi  2.0M    46k    322k
telemetry-pipeli  897k    21k    146k
*flash-surgeon    8.9M   207k   1.45M
*flash-auditor    2.7M    63k    441k
*argon-sentinel   1.3M    30k    209k
════════════════════════════════════════
```

### 3. `style="rich"` (76-Column Widescreen Layout)

```text
╔══════════════════════════════════════════════════════════════════════════╗
║ ▄▀█ █▀▀ █▄█ ▄▄ █▄░█ █▀▀ ▀▄▀ █░█ █▀   v3.8 // RICH TELEMETRY RIG          ║
║ █▀█ █▄█ ░█░ ░░ █░▀█ ██▄ █░█ █▄█ ▄█   WINDOW: 90d (Nov 03 ◄── Aug 06)     ║
╠════════════════════════════════════╦═════════════════════════════════════╣
║ QUOTA POOLS & 429 COOLDOWNS        │ STEP & TOOL VELOCITY                ║
║ G-20x: 100.0% [████████┼█] OK      │ Total : 187,877 steps | 93,195 tool ║
║ P-1x : 100.0% [░┼░░░░░░░░] OK      │ Active: 4,369 s/act-d (43d active)  ║
║ 429s : 0 events | 71.4% Wk Left    │ Calend: 2,020 s/cal-d (54c, 227r)   ║
╠════════════════════════════════════╬═════════════════════════════════════╣
║ TOKEN BURN & ROLLING AVERAGES      │ MCP WIRE & CLIENT SURFACES          ║
║ Total : ~69.3M (~63.0M direct)     │ Wire  : 100% <20KB (avg 3.0/17.5KB) ║
║ Daily : 1.61M tok/act-d            │ Calls : 77 MCP reqs (62.5k tok)     ║
║ Weekly: 11.28M tok/wk              │ Client: Gemini Web (100% / 0 Mob)   ║
╠════════════════════════════════════╩═════════════════════════════════════╣
║ DAILY ACTIVITY MATRIX (NOW: W01 ──► W13)     [·· 0  ░░ <1k  ▒▒ <4k  ██]  ║
║ Wk   W01 W02 W03 W04 W05 W06 W07 W08 W09 W10 W11 W12 W13  ┌─ PEAK DAY ─┐ ║
║ Mon  ▒▒▒ ███ ░░░ ▒▒▒ ▓▓▓ ▒▒▒ ··· ··· ··· ··· ··· ··· ···  │ Oct 31     │ ║
║ Tue  ░░░ ▓▓▓ ▒▒▒ ▒▒▒ ▒▒▒ ░░░ ░░░ ··· ··· ··· ··· ··· ···  │ 11,118 stp │ ║
║ Wed  ··· ▓▓▓ ░░░ ░░░ ▒▒▒ ▓▓▓ ░░░ ··· ··· ··· ··· ··· ···  ├────────────┤ ║
║ Thu  ··· ███ ░░░ ▒▒▒ ▓▓▓ ███ ░░░ ··· ··· ··· ··· ··· ···  │ Act: 43d   │ ║
║ Fri  ··· ▓▓▓ ███ ▓▓▓ ▒▒▒ ▓▓▓ ▓▓▓ ··· ··· ··· ··· ··· ···  │ Avg:  4.4k │ ║
║ Sat  ··· ███ ███ ░░░ ▒▒▒ ███ ███ ··· ··· ··· ··· ··· ···  │ Sub: 227r  │ ║
║ Sun  ··· ███ ███ ▓▓▓ ▓▓▓ ███ ▒▒▒ ··· ··· ··· ··· ··· ···  └────────────┘ ║
║ Vol  ▁▁▁ ███ ▅▅▅ ▃▃▃ ▄▄▄ ▅▅▅ ▃▃▃ ─── ─── ─── ─── ─── ───  PeakWk:46.8k   ║
║ Steps2.9 46. 35. 20. 27. 36. 19.  ·   ·   ·   ·   ·   ·                  ║
╠══════════════════════════════════════════════════════════════════════════╣
║ 8H SUB-DAILY HORIZON CURVE & PROJECT STACK (NOW ──► SEP 21)              ║
║ 3.7k ╷     █       ▄ ▄                                                   ║
║ 2.9k ┤    ▄█       █▄█▄                               █                  ║
║ 2.0k ┤   ▄██  ▄▄  █████                     ▄    ██▄ ▄█      ▄▄          ║
║ 1.5k ┼───████─██▄██████▄─────────▄──────█───█────██████▄█────███──────   ║
║  662 ┤  ████████████████▄ █▄ ██ ▄█▄ ▄▄▄███ ▄█ █▄█████████ ▄█▄███         ║
║    0 ╵ ▄▒█▒▒▓▓█████▒█▒▒▒▒▒▒▒▄▒▒▒██▓▄█▓████▄████████████▓▓▄▓▓▓▓▓▓▓▓▓▄     ║
║      └─▲───────────▲───────────▲───────────▲───────────▲───────────▲───  ║
║       Nov 03      Oct 25      Oct 16      Oct 07      Sep 28      Sep 21 ║
║       Stack: [█]core-platfor(42%)  [▓]web-dashboar(25%)  [▒]agent-orches ║
╠══════════════════════════════════════════════════════════════════════════╣
║ MODEL QUOTA vs TARGET (┼ = Target Pin)       CALLS   EST TOK  DELTA STAT ║
║ Argon 4 Pro [█████████████┼█▓░░░░░]  70.4%  77,856    ~18.0M  +5.4%  OK  ║
║ Flash 3.8   [█████┼▓░░░░░░░░░░░░░░]  29.6%  32,675  FastTier  +4.6%  OK  ║
║ Claude 5.5  [░░┼░░░░░░░░░░░░░░░░░░]   0.0%      31         0  -8.0%  OK  ║
║ GPT-OSS 120 [▏░░░░░░░░░░░░░░░░░░░░]   0.0%       0         0  -2.0%  OK  ║
╠══════════════════════════════════════════════════════════════════════════╣
║ WORKSPACES (9)     CHATS   STEPS  TOTAL TOK  TOK/DAY  TOK/WK SHARE GAUGE ║
║ 1. core-platform-  10c  65,811     ~29.2M     679k   4.75M ██▍░░░ 42.1%  ║
║ 2. web-dashboard-  19c  45,032     ~17.2M     400k   2.80M █▍░░░░ 24.8%  ║
║ 3. agent-orchestr   5c  20,107     ~16.5M     384k   2.69M █▍░░░░ 23.8%  ║
║ 4. cloud-infra-gi   8c   5,991      ~2.2M      52k    362k ░░░░░░  3.2%  ║
║ 5. mobile-sync-en   1c   5,092      ~2.0M      46k    322k ░░░░░░  2.9%  ║
║ 6. telemetry-pipe   7c   2,878      ~897k      21k    146k ░░░░░░  1.3%  ║
║ 7. auth-gateway     2c   2,691      ~1.0M      23k    164k ░░░░░░  1.5%  ║
║ 8. docs-portal      1c   1,126      ~294k     6.8k     48k ░░░░░░  0.4%  ║
║ 9. sdk-client-py    1c      21      ~4.5k      104     727 ░░░░░░  0.0%  ║
╟──────────────────────────────────────────────────────────────────────────╢
║ SUBAGENTS (8)       RUNS   STEPS  TOTAL TOK  TOK/DAY  TOK/WK SHARE GAUGE ║
║ 1. flash-surgeon  116r  21,704      ~8.9M     207k   1.45M ███▍░░ 58.2%  ║
║ 2. flash-auditor   78r   8,170      ~2.7M      63k    441k █░░░░░ 17.7%  ║
║ 3. argon-sentinel   3r   3,142      ~1.3M      30k    209k ▍░░░░░  8.4%  ║
║ 4. flash-scout     20r   2,801      ~1.1M      25k    173k ▍░░░░░  6.9%  ║
║ 5. argon-surgeon    2r   2,287      ~920k      21k    150k ▍░░░░░  6.0%  ║
║ 6. research         5r     862      ~333k     7.7k     54k ░░░░░░  2.2%  ║
║ 7. argon-architec   2r     132     ~64.2k     1.5k     10k ░░░░░░  0.4%  ║
║ 8. claude-special   1r      31     ~16.3k      380    2.7k ░░░░░░  0.1%  ║
╚══════════════════════════════════════════════════════════════════════════╝
```

---

## Advanced & Future Workflows: Pairing with Gemini Notebook & Gemini Tasks

When you combine `agy-nexus-mcp` with **Gemini Notebook** (formerly NotebookLM) and **Gemini Tasks** (formerly Spark), Gemini becomes a scheduled, citation-backed control center for your local Antigravity projects:

### 1. Zero-Token Reference Lookup with Gemini Notebook
Normally, if a local coding agent needs to check hardware manuals, API specs, RFCs, or large architecture docs, it spends local steps and model quota reading files.
- **Pre-Flight Context Compression**: Store large reference manuals and specs in **Gemini Notebook**. Ask Gemini to pull the exact cited excerpts from your Notebook first, then send a concise `<= 4,500`-character brief into Antigravity via `send_handoff_and_resume`.
- **Fast Handoffs**: Local agents skip broad file discovery and start coding immediately, while large Notebook briefs automatically write to `scratch/gemini_research_handoff.md` with a compact wakeup prompt so CLI handoffs never time out.

### 2. Scheduled Automation with Gemini Tasks (Spark)
Because Gemini Tasks supports recurring schedules, event triggers, Gemini Notebook, and custom MCP connectors, it can run unattended checks for your local projects:
- **Morning Usage & Audio Briefings**: Schedule a morning Gemini Task to call `manage_background_run(action="stats")`, combine your quota pacing with open tasks, and prepare a morning summary or Notebook Audio Overview.
- **Single-Turn Multi-Repo Drift Audits**: A nightly Gemini Task can call `inspect_git_diff(workspace_override="ALL")` to scan all of your local Git repositories in one turn—flagging uncommitted changes, active branches, or paused sessions without hitting Gemini's single-tool-per-turn limit.
- **Event-Driven Plan Staging**: When an important release note or alert arrives, a triggered Gemini Task can check impact against your Gemini Notebook docs and stage a `plan`-mode handoff (`resume_headless=False`) for you to review.

### 3. Searchable Project Memory (`walkthrough.md` $\rightarrow$ Gemini Notebook Sync)
Every completed Antigravity session produces an `implementation_plan.md` and `walkthrough.md` that normally sit isolated inside individual session UUID folders.
- **Clean Notebook Exports**: Calling `manage_background_run(action="export_notebook")` exports completed session plans and walkthroughs into human-named, dated Markdown files (`YYYY-MM-DD_<repo>_<title>_<id>.md`) inside `sidecar_data/ag-bridge-bg/notebook_exports/` (configurable via `AGY_NOTEBOOK_EXPORT_DIR`).
- **SHA-256 Deduplication (Zero Re-Sync Loops)**: Before writing each file, `export_notebook` checks a SHA-256 hash of the content and skips unchanged sessions (`sync_state="unchanged"`), so syncing that folder to Google Drive and Gemini Notebook never causes duplicate uploads or sync loops.

### 4. Split-Trust Lock Options for Unattended Scheduled Runs
Because `agy-nexus-mcp` requires your interactive passphrase to unlock, a scheduled 6:00 AM Gemini Task would normally hit the lock screen unless you include the passphrase in the task prompt. If you want unattended scheduled tasks without storing your passphrase in a cloud prompt, you can enable two optional split-trust settings in `secrets.env`:
- **`AG_BRIDGE_ALLOW_LOCKED_STATS=true`**: Allows `manage_background_run(action="stats")` to return usage and quota summaries while locked—without exposing any code, file paths, or chat messages.
- **`AG_BRIDGE_ALLOW_LOCKED_STAGING=true`**: Allows `send_handoff_and_resume(..., resume_headless=False)` while locked to save incoming research notes into a quarantine folder (`sidecar_data/ag-bridge-bg/quarantine_handoffs/`), keeping file reads and live execution strictly behind your passphrase.

---

## Available MCP Tools (9 Tools)

| Tool | What It Does |
| :--- | :--- |
| `unlock_sessions(spoken_passphrase, search_query="")` | Verifies your passphrase, unlocks the server, and returns your numbered list of recent Antigravity chats (`1..N`) plus a live usage summary. |
| `lock_bridge()` | Immediately locks the server and clears the active session selection. |
| `list_saved_sessions(limit, status_filter, include_subagents)` | Lists recent Antigravity chats with live status (`RUNNING`, `STALLED_WAITING_APPROVAL`, `COMPLETED`, `IDLE`), waiting approval details, project path, and task summary. |
| `load_session_into_gemini(session_identifier, include_files)` | Opens a chat by number (`"1"`), `#2`, ID prefix, or title keyword and returns its `task.md`, `implementation_plan.md`, `walkthrough.md`, git status, and recent messages. |
| `ask_workspace_readonly(question, search_query, file_subpath, start_line, end_line)` | Searches code or reads files across the active project (with line-range support like `src/app.py:100-250` or `skill:agy-nexus-stats`). |
| `inspect_git_diff(target_branch, include_untracked, workspace_override, file_path, offset_chars, start_line, end_line)` | Shows the current branch, modified/untracked files, and git diff for a repo—or pass `workspace_override="ALL"` (or `"repo1,repo2"`) to audit all repositories in one turn. |
| `send_handoff_and_resume(research_markdown, resume_headless, session_identifier, workspace_path, project_name, activate_skills, target_agent_role, ...)` | Routes your research notes or implementation plan to the right project session (`scratch/gemini_research_handoff.md`), and optionally wakes up Antigravity to continue working. |
| `manage_background_run(action, job_id, tail_lines, period, style)` | Checks background session progress (`status`, `tail`, `stop`), renders three-tier ASCII stats (`action="stats"`), or exports completed session plans/walkthroughs for Gemini Notebook (`action="export_notebook"`). |
| `list_models_and_agents(include_skills, include_rules, skill_scope_filter, inspect_name)` | Lists your configured Agent Roles, Skills, Rules, and pool quota settings, or reads a specific skill/rule file via `inspect_name`. |

---

## Comparison with Typical Antigravity Bridges

| Feature | Typical Community Bridges (`agy-bridge`, `gemini-antigravity-bridge`, `meridian`, `ag-local-bridge`) | `agy-nexus-mcp` |
| :--- | :--- | :--- |
| **Connection Type** | Local `stdio` pipe, localhost proxy, or single-chat Telegram/WhatsApp bot | **Streamable HTTP MCP** reachable directly from Google Gemini Web, Mobile & Scheduled Gemini Tasks |
| **Security** | None or static chat-ID allowlist | **Secret URL Path + Voice/Text Passphrase Lock** with optional split-trust staging |
| **Multi-Chat History & Routing** | Single active chat only | Browse all chats and subagents with full-text search and **automatic multi-project handoff routing** |
| **Web Dashboard & Chromium App** | None | **Installable Chromium Standalone App (`/web`)** with `Mon–Sun` Calendar Heatmap, 4 Themes × 4 Densities, and 4h/8h Stacked Area Charts |
| **Chat ASCII Usage Reports** | None | **Three-Tier Monospace ASCII Reports** (`default` 72-col, `quick` 40-col mobile, `rich` 76-col desktop) |
| **Gemini Notebook & Tasks Ready** | None | **One-turn multi-repo drift audits (`workspace_override="ALL"`)** & SHA-256 deduplicated `walkthrough.md` exports (`action="export_notebook"`) |
| **Large File & Diff Handling** | Raw dumps that can hang cloud proxies | **Automatic `< 20 KB` Responses** with line-range file reads and paged git diffs |

---

## Optional: Starter Subagents Prompt

If you haven't set up custom subagents in Antigravity yet and want a ready-made set of helper agents (`flash-scout`, `flash-surgeon`, `flash-auditor`, `argon-sentinel`), paste this prompt into an Antigravity chat:

> *"Create four global subagent definitions in `~/.gemini/config/agents/`: `flash-scout.md` (read-only codebase search on `flash`), `flash-surgeon.md` (focused code edits and refactors on `flash`), `flash-auditor.md` (test and linter runner on `flash`), and `argon-sentinel.md` (read-only architecture and bug reviewer on `pro`)."*

As soon as Antigravity runs those subagents, their activity and token usage will automatically appear in the `/web` dashboard and ASCII reports.

---

## Repository Layout

```text
agy-nexus-mcp/
├── ag_bridge.py                      # Main FastMCP HTTP server (9 tools + /web & PWA routes)
├── ag_bridge_workflows.py            # Gemini Notebook export, multi-repo drift audit & quarantine staging
├── ag_bridge_hygiene.py              # File line-range slicer, diff paginator & code modularity helper
├── ag_bridge_inventory.py            # Skills, Agent Roles & Rules discovery helper
├── ag_bridge_stats.py                # Usage stats, Mon–Sun heatmap, sub-daily series & ASCII router
├── ag_bridge_telemetry_scanner.py    # Transcript & SQLite step/token/subagent/workspace scanner
├── ag_bridge_ascii_default.py        # Tier 1 (72-col Default) & Tier 2 (40-col Quick) ASCII renderers
├── ag_bridge_ascii_rich.py           # Tier 3 (76-col Rich Widescreen) ASCII renderer
├── web/
│   ├── index.html                    # Responsive /web Dashboard (4 Themes × 4 Densities + PWA client)
│   ├── manifest.webmanifest          # Chromium Standalone Web App Manifest
│   ├── sw.js                         # Root-scoped network-first Service Worker
│   ├── icon.svg                      # Vector radar & heatmap app icon
│   ├── icon-192.png                  # 192×192 RGBA PWA icon
│   └── icon-512.png                  # 512×512 RGBA PWA icon
├── docs/
│   └── assets/
│       ├── dashboard-desktop.png     # Depersonalized desktop dashboard & App popover screenshot
│       └── dashboard-mobile.png      # Depersonalized mobile dashboard screenshot
├── skills/
│   └── agy-nexus-stats/
│       └── SKILL.md                  # Bundled skill for rendering 3-tier ASCII & web stats in Gemini
├── host_bridge/
│   └── agy_host_bridge.py            # Lightweight host daemon (:8098) for waking sessions & git inspection
├── scripts/
│   ├── setup.sh                      # Interactive setup script (Linux / macOS / WSL)
│   ├── setup.ps1                     # Interactive setup script (Windows PowerShell)
│   ├── init_secrets.py               # Passphrase & secret URL generator
│   └── sync_repo.sh                  # Repo sync utility
├── systemd/
│   ├── ag-bridge.service             # Systemd user service for running ag_bridge.py on the host
│   └── agy-host-bridge.service       # Systemd user service for the host companion daemon
├── tests/
│   └── run_permutation_suite.py      # End-to-end automated test suite
├── docker-compose.yml                # Docker Compose manifest
├── DEPLOYMENT.md                     # Step-by-step setup, reverse proxy & HTTPS PWA guide
├── LICENSE                           # GNU Affero General Public License v3.0 (AGPL-3.0-or-later)
├── NOTICE                            # AGPLv3 Section 7 Attribution, Brand & Security-Integrity Terms
├── pyproject.toml                    # Python package metadata (v2.3.0)
└── requirements.txt                  # Python dependencies
```

---

## License, Attribution & Security Integrity (`GNU AGPLv3`)

`agy-nexus-mcp` is free and open-source software licensed under the **GNU Affero General Public License v3.0 or later (`AGPL-3.0-or-later`)** — see [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE) for full terms.

### What This Means in Plain Language
1. **Always Open & Share-Alike (Including Network / Hosted Use — AGPLv3 §13)**:
   - You are free to use, study, modify, and self-host `agy-nexus-mcp`.
   - If you distribute modified versions—or run a modified version as a hosted service or network-accessible MCP / `/web` server for others—you **must** make the complete corresponding source code publicly available under `AGPLv3`. Nobody can take this project private or wrap it into a proprietary commercial offering.
2. **Required Attribution & Brand Protection (AGPLv3 §7(b), §7(c) & §7(e))**:
   - All copies, forks, and derivative works must preserve the copyright notices, license notices, and upstream attribution in [`NOTICE`](NOTICE) and in the `/web` and ASCII telemetry interfaces.
   - Modified versions must be clearly marked as modified and **may not** be advertised or misrepresented as the official original `agy-nexus-mcp` release.
3. **Security-Integrity Disclosure (AGPLv3 §7(c) & §5(a))**:
   - The voice-passphrase deadbolt (`PASS_HASH`), unguessable `PATH_SECRET` routing, path-traversal sandboxing, and read-only SQLite isolation are core security guarantees of `agy-nexus-mcp`.
   - Any fork or derivative work that weakens, bypasses, or strips these security controls **must** prominently disclose that its security boundary has been removed or altered and may not present itself under the unmodified `agy-nexus-mcp` / `AGY-NEXUS` identity.

