# `agy-nexus-mcp` — Connect Google Gemini to Your Antigravity IDE, 2-Pane Workspace & Usage Studio (`v4.0.1`)

`agy-nexus-mcp` is a self-hosted **Dual-Doorway Model Context Protocol (MCP)** server connecting **Google Gemini** (Web, Mobile & Tasks) directly to your local **Google Antigravity IDE / CLI** workstation—paired with **`agy-praxis-mcp`** (deadbolt-free LAN-only semantic codebase index & `<repo-slug>-NN` handoff inbox) and the **Quiet UI `v9.3.0` Studio PWA (`/web`)** featuring live **8-Model Micro-USD Analytics** and a **2-Pane Session Workspace Explorer**.

> **[Try the Interactive Live Showcase (Real Workstation Telemetry, 0 Backend Required)](https://FrankXLT.github.io/agy-nexus-mcp/)**

---

## Live `/web` Unified Studio App (`Analytics` + 2-Pane `Workspace`)

### 1. `Analytics` — 8-Model Cost Ledger, Active-Day Whiskers & `Mon–Sun` Calendar Matrix
![AGY-NEXUS v4.0.1 Analytics Surface — Quiet UI v9.3.0 Studio, 6-Window Presets, 8-Model Micro-USD Cost Ledger, Single-Hue 52-Week Mon–Sun Calendar Matrix, Hourly Whiskers & Code Health](docs/assets/dashboard-desktop.png)

### 2. `Workspace` — Responsive 2-Pane Session Explorer, Editorial Reader & Capture Gallery
![AGY-NEXUS v4.0.1 2-Pane Workspace Explorer — Recency Project Rail, Editorial Markdown Tabs, Inline Walkthrough Captures & Direct PNG / Per Sheet Gallery](docs/assets/workspace-desktop.png)

<details>
<summary><strong>📱 Mobile Layouts (<code>390px</code> Portrait — Analytics <code>26w</code> Matrix &amp; Clean Wrapped Workspace Tabs)</strong></summary>

![AGY-NEXUS v4.0.1 Mobile Analytics View](docs/assets/dashboard-mobile.png)
![AGY-NEXUS v4.0.1 Mobile Workspace View](docs/assets/workspace-mobile.png)

</details>

---

## Key Capabilities (`v4.0.1`)

- **Dual-Doorway Parallel Isolation & `<repo-slug>-NN` Queue**: Concurrent Gemini Web/Mobile tabs work across separate repositories via `fcntl.flock` `active_contexts` slots (auto-pruning stale slots), 3-pillar fail-closed resolution (`target_resolver.py`), same-repo concurrent writer detection (`MAIN WRITER` / `WORKTREE` / `SHARED`), and atomic `<slug>-NN` handoffs (`handoff_queue.py`) with proportional **Surgical Fast-Path** vs. Full Dual-Review execution (`handoff_templates.py`).
- **8-Model Registry, Effective-Dated Cost Ledger & `01:45 AM` Drift Watchdog**: Tracks all 8 live models (`Gemini 4 Carbon`, `Neon`, `Argon`, `Hydrogen`, `Gemini 3.8 Flash`, `Claude Opus 5.5`, `Claude Sonnet 5.5`, `GPT-OSS 120B`) with immutable micro-USD epochs (`CACHE_VERSION = 8`, `cost_ledger.json`), deadbolt-safe `76`-col `models` ASCII status, `12`-subagent `sync_agents.py`, and read-only `01:45 AM` `agy-model-drift-check.timer`.
- **`agy-praxis-mcp` Local IDE Doorway (`6` Tools)**: Incremental SHA-256 Polyglot semantic indexing (`polyglot_map` strictly `<= 17.5 KB` with `directory_summary` + `drilldown_hint`, `polyglot_search`, `polyglot_outline`) + `<repo-slug>-NN` handoff queue (`/praxis/{PRAXIS_MCP_TOKEN}/mcp`, legacy `/polyglot/` alias, or `--stdio`) with strict LAN-only `403` proxy/Origin rejection.
- **Strict `< 20 KB` Wire Budget, Continuity Rollover & In-Place Closeout**: Sequential Read-Only Governance (`<= 4` hops/turn), `tools/list` (`<= 8.6 KB`), `get_session_tree` (`<= 17.5 KB`), `<= 18.5 KB` inner / `<= 19.8 KB` escaped outer wire caps, 5-tier context pressure (`FRESH` $\rightarrow$ `HARD_ROLLOVER`), `RETIRED.json` tombstones (`retire_after_closeout=True`), and `workflow:baseline`.
- **Quiet UI `v9.3.0` Studio (`/web`) & Public Interactive Showcase**: Direct `/web` live cutover (`/web/v9` compatible), offline vendored Apache ECharts, `[Steps | Tokens | $ Cost]`, `Activity by Hour of Day` active-day `Min / Avg / Max + Last 24h` whiskers, `Subscription Break-Even`, responsive `< 760px` Docs + `[Captures (N)]` modal, and zero-leak **GitHub Pages Showcase** (`scripts/build_github_showcase.py`).

---

## Quick Setup & Everyday Prompts

1. **Initialize & Self-Test**: Clone the repo, run `./scripts/setup.sh` (or `.\scripts\setup.ps1` / `python3 scripts/init_secrets.py --passphrase "..."`), then verify & start:
   ```bash
   python3 ag_bridge.py --self-test && python3 -m agy_nexus.tools_praxis --self-test && pytest
   python3 ag_bridge.py   # or docker compose up -d (see docs/DEPLOYMENT.md)
   ```
2. **Connect Clients**:
   - **Gemini Web / Mobile / Tasks**: Add custom MCP `https://<your-domain>/{PATH_SECRET}/mcp` (voice/text unlock strips filler via `unlock_sessions`).
   - **Antigravity IDE (`agy-praxis-mcp`)**: Point `~/.gemini/config/mcp_config.json` to `http://<host>.lan:8765/praxis/<PRAXIS_MCP_TOKEN>/mcp`.
   - **Quiet UI Studio PWA (`/web`) & Public Demo**: Open `https://<your-domain>/web` (`?demo=1` for depersonalized preview) or explore the [Public GitHub Pages Showcase](https://FrankXLT.github.io/agy-nexus-mcp/).
3. **Example Prompts**: *"Unlock Antigravity with [phrase] and load `agy-nexus-mcp`"* · *"Show me my session tree"* · *"Show model & subagent status"* · *"Search `cloud-gitops-stack` for compose healthcheck rules"* · *"Stage this bugfix (`allow_chained_publish=False`)"* · *"Show me my latest usage stats (`default` / `quick` / `rich`)."*

---

## Project Manager Mode & Plain-Language Handoffs (`v4.0.1`)

`agy-nexus-mcp` turns Google Gemini into a grounded **Engineering Project Manager**: Gemini scouts live state sequentially (`<= 4` calls/turn), stages `<repo-slug>-NN` handoffs with proportional `execution_mode="auto"` ceremony (`allow_chained_publish=False` for preview gates with 7-day `/web/media/` screenshots), and guides **Job-First `"Yes"`** transitions across `ready_to_run` (staged tickets), `in_flight` (running tasks), and `ready_to_ship` (in-place `retire_session=True` + `RETIRED.json` closeout).

| `handoff_mode` | Purpose & Behavior | Antigravity Execution |
| :--- | :--- | :--- |
| **`feature_update`** *(Default)* | Add features or refine workflows with `WORKFLOWS.md` baseline parity. | Full 4-Step (`flash-scout` $\rightarrow$ `surgeon` $\rightarrow$ `flash-auditor` $\rightarrow$ Dual-Review / Visual Gate; multi-deliverable/complex `fast` coerces to `plan`). |
| **`new_project`** | Stand up greenfield repos/packages (`create_new_project=True`, `<= 500L` modules). | Blueprinted via `argon-architect` (`plan` mode enforced), scaffolded modularly with `pytest` & self-tests. |
| **`bug_or_visual_fix`** | Pinpoint broken behavior, exact viewports (`390px`/`900px`/`1440px`/`2560px`), and fix criteria. | **Surgical Fast-Path** for compact non-security diffs (`fast`), or Full Dual-Review on auth/UI boundaries. |
| **`release_closeout`** | Verify tests, sync 3-2-1 backups, commit/tag/push, and write `RETIRED.json` tombstones. | Prunes worktrees, marks `<slug>-NN` tickets `COMPLETED`, defers `RETIRED.json` (`retire_after_closeout=True`) on headless runs until commit+push succeed. |

---

## Copy-Ready 76-Column Project, Chat & Session Hierarchy (`get_session_tree`)

Call `get_session_tree()` (or `manage_background_run(action="sessions")`) to render a copy-ready 76-column ASCII hierarchy grouping every conversation and staged `<repo-slug>-NN` handoff under its parent project with **untruncated** `project_id`, `session_id`, and `workspace` lines:

```text
╔══════════════════════════════════════════════════════════════════════════╗
║ AGY-NEXUS v4.0.1 // PROJECT -> CHAT -> SESSION ID HIERARCHY (COPY-READY) ║
╠══════════════════════════════════════════════════════════════════════════╣
║ SLOTS: 3 | STAGED: 2 | IN-WORK: 3 | PINNED: 24 | TTL: 119.5m             ║
║ 3-2-1 BACKUP: 2a8bf53 (SYNCED ✓ · 19105.3 KB · 37m ago)                  ║
╚══════════════════════════════════════════════════════════════════════════╝

[PROJECT 1] Mail Triage UI [SHARED REPO] [▶ 1 IN-WORK]
  project_id : 731500ec-2901-42e0-b143-0ce1d0a7cc3c
  workspaces : /home/dev/agentic_workspace/projects/mail-triage-ui
  ├─ [HANDOFF mail-triage-ui-27] Stage 7.2 — Holdout Verification & Delta Scoreboard
  │   pass_off   : [▶ IN-WORK] · plan/bug_or_visual_fix · 45m ago
  │   session_id : b69be2f9-7431-4d52-9f39-7ac175981dca
  ├─ [HANDOFF mail-triage-ui-26] Stages 1.0–3.8 — Core Classifier, Wizard & Sankey Audit
  │   pass_off   : [✓ COMPLETED] · plan/bug_or_visual_fix · 1h ago
  │   session_id : e6af5395-535f-42c7-b76d-41944779dc87
  ├─ (+4 older completed)
  ├─ [#1] Stage 7.2 — Holdout Verification & Delta Scoreboard
  │   session_id : b69be2f9-7431-4d52-9f39-7ac175981dca
  │   workspace  : /home/dev/agentic_workspace/projects/mail-triage-ui
  │   status     : [● RUNNING] · MAIN WRITER · 314 steps · 1s ago
  ├─ [#9] Stage 6.0 — Parent Vendor Consolidation & 6-Stage Sankey
  │   session_id : e6af5395-535f-42c7-b76d-41944779dc87
  │   workspace  : /home/dev/agentic_workspace/projects/mail-triage-ui
  │   status     : [◉ PINNED · IDLE] · SHARED (READ-ONLY) · 855 steps · 1h ago
  └─ [#11] Stages 1.0–3.8 — Core Classifier, Wizard & Sankey Audit
      session_id : c97628eb-64d8-4c6a-8b38-af6a4866d5fc
      workspace  : /home/dev/agentic_workspace/projects/mail-triage-ui
      status     : [○ COMPLETED] · SHARED (READ-ONLY) · 637 steps · 3h ago

[PROJECT 2] Stem Curriculum Lab [SHARED REPO] [◈ 1 STAGED] [▶ 1 IN-WORK]
  project_id : 8d13c66f-569c-42e0-a57e-dd4b111ab5f2
  workspaces : /home/dev/agentic_workspace/projects/stem-curriculum-lab
  ├─ [HANDOFF stem-curriculum-lab-60] [SCL-Core] Stepped & Hex Domain Mosaics + Skill Trees
  │   pass_off   : [◈ STAGED · UNCLAIMED] · plan/feature_update · 3d ago
  │   session_id : (unclaimed · new chat)
  ├─ [HANDOFF stem-curriculum-lab-82] [SCL-Portal] Landing Page, Control-Plane & OIDC Auth
  │   pass_off   : [▶ IN-WORK] · plan/bug_or_visual_fix · 20m ago
  │   session_id : 793805e4-320c-4d63-a627-b5448ca2ba0f
  ├─ (+15 older completed)
  ├─ [#2] [SCL-RF] Ch. I–VIII Interactive Signal Modules Overhaul
  │   session_id : 793805e4-320c-4d63-a627-b5448ca2ba0f
  │   workspace  : /home/dev/agentic_workspace/projects/stem-curriculum-lab
  │   status     : [● RUNNING] · MAIN WRITER · 815 steps · 2s ago
  ├─ [#12] [SCL-Core] Stepped & Hex Domain Mosaics + Skill Trees
  │   session_id : 6a6d8526-6e5c-4552-9789-35ab7606b379
  │   workspace  : /home/dev/agentic_workspace/projects/stem-curriculum-lab
  │   status     : [○ COMPLETED] · SHARED (READ-ONLY) · 837 steps · 3h ago
  └─ [#16] [SCL-Portal] Landing Page, Control-Plane & OIDC Auth
      session_id : d88c1dfc-c42b-4922-92c5-56c2b41d388c
      workspace  : /home/dev/agentic_workspace/projects/stem-curriculum-lab
      status     : [○ COMPLETED] · SHARED (READ-ONLY) · 379 steps · 8h ago

[PROJECT 3] Net Topology ANMS [SHARED REPO] [◈ 1 STAGED] [▶ 1 IN-WORK]
  project_id : 9be3dfc6-b9ff-415f-b8b0-8b2ac31dff9c
  workspaces : /home/dev/agentic_workspace/projects/net-topology-anms
  ├─ [HANDOFF edge-proxy-rs-03] net-topology-anms 2.0 Wave 2 (Passes 3–7) — Valid Gemini Models, Zero Fake Demo Data, Devices v2 Bridge, Local Probes & Full Rese
  │   pass_off   : [◈ STAGED · UNCLAIMED] · plan/bug_or_visual_fix · 7h ago
  │   session_id : (unclaimed · new chat)
  ├─ [HANDOFF edge-proxy-rs-05] net-topology-anms 2.0 Wave 3 — Multi-Instance Collectors, Worker Cadence, Multi-Switch Step 4, Live Canvas Sync & Compose/DB Hard
  │   pass_off   : [▶ IN-WORK] · plan/feature_update · 52m ago
  │   session_id : 3a580477-86a0-4409-87bd-7a8b9edc6587
  ├─ (+4 older completed)
  ├─ [#3] Rollout RCCA, Progressive Setup Wizard & Light UI
  │   session_id : 3a580477-86a0-4409-87bd-7a8b9edc6587
  │   workspace  : /home/dev/agentic_workspace/projects/net-topology-anms
  │   status     : [● RUNNING] · MAIN WRITER · 532 steps · 5s ago
  ├─ [#5] Deterministic Multi-MCP Entity Fusion & FSD Hierarchy
  │   session_id : fc7c9932-0a24-42ce-b09b-cd3aabb8f1cf
  │   workspace  : /home/dev/agentic_workspace/projects/net-topology-anms
  │   status     : [◉ PINNED · IDLE] · SHARED (READ-ONLY) · 922 steps · 20m ago
  └─ [#10] Deterministic Multi-MCP Entity Fusion & FSD Hierarchy
      session_id : d0791371-1319-45ff-befa-d898eb4de206
      workspace  : /home/dev/agentic_workspace/projects/net-topology-anms
      status     : [◉ PINNED · IDLE] · SHARED (READ-ONLY) · 1,510 steps · 1h ago
```

---

## Three-Tier ASCII Usage Reports in Chat

Ask Gemini for your usage stats (`get_session_tree(include_stats=True, period="last_90d", style=...)` or `manage_background_run(action="stats", ...)`) to render live Dual-Pool quota pacing, `Mon–Sun` calendar heatmaps, sub-daily curves, and workspace/subagent token breakdowns in **three plain-text layouts**:

| Style | Width | Best For | What It Shows |
| :--- | :---: | :--- | :--- |
| **`style="default"`** | **72 cols** | Standard Desktop & Tablet Chat | Split summary header, 22-week `Mon–Sun` heatmap, 8-hour activity & project stack (`░▒▓█`), model quota bars (`┼`), Praxis/Polyglot health, and project & subagent tables. |
| **`style="quick"`** | **`<= 40` cols** | Phone Screens (Portrait) | Fits strictly within 40 characters per line so it never wraps on mobile. Shows a 13-week heatmap, 8-hour pace curve, model quota bars, and top projects/subagents. |
| **`style="rich"`** | **76 cols** | Widescreen Desktop Chat | Full box-drawn rig (`v4.0.1`) with side-by-side quota and token panels, 13-week 3-character heatmap with Peak Day card, 6-row 8-hour curve, and share gauges. |

### 1. `style="default"` (72-Column Standard Layout)

```text
════════════════════════════════════════╤═══════════════════════════════
AGY-NEXUS v4.0.1 // 91d (Nov 22 ◄── Aug ┆ Up to Date (v4.0.1)           
════════════════════════════════════════╪═══════════════════════════════
GOOGLE 20x :  99.8% [████████┼█] HEALTHY┆ 0x 429s | Ultra-20x (T:>=90%) 
PARTNER 1x :  99.8% [░┼░░░░░░░░] ON PACE┆  0.0% Wk Left | Lim <=14.3%/d 
STEPS/TOOLS: 252,531s | 128,733t | 186c ┆ 4,951 s/act-d | 2,775 s/cal-d 
TOKEN BURN : ~12.0B | $2,979.04         ┆ 235.3M/d | $58.41/d (607r)    
MCP WIRE   : 96% <20KB (avg 12.7/38.6KB)┆ 139 req (484k tok) | Web+Praxi
CODE HEALTH: Poly 2360 syms | 84/84 <=50┆ 0 >650L | Praxis+Serena       
────────────────────────────────────────┴───────────────────────────────
DAILY HEATMAP (NOW: W01 ──► 22w AGO)   Peak: 11/14 (16,811s) | Act: 51d
Wk    01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22
Mon   ██ ▓▓ ▒▒ ▓▓ ░░ ░░ ·· ░░ ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ··
Tue   ██ ▓▓ ▒▒ ▒▒ ▒▒ ░░ ·· ·· ░░ ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ··
Wed   ██ ▓▓ ▓▓ ▒▒ ·· ░░ ·· ░░ ░░ ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ··
Thu   ██ ▒▒ ▒▒ ▒▒ ░░ ░░ ·· ·· ▒▒ ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ··
Fri   ██ ██ ▓▓ ▒▒ ▓▓ ░░ ·· ▒▒ ▓▓ ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ··
Sat   ██ ██ ██ ██ ▓▓ ░░ ·· ▓▓ ▒▒ ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ··
Sun   ██ ██ ██ ▓▓ ▓▓ ▒▒ ·· ▓▓ ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ··
Vol   ██ ▅▅ ▃▃ ▃▃ ▂▂ ▁▁ ── ▁▁ ▁▁ ── ── ── ── ── ── ── ── ── ── ── ── ──
────────────────────────────────────────────────────────────────────────
8H SUB-DAILY PACE (NOW ──► SEP 21)   [Avg: 562/8h | Peak: 1.8k | ░▒▓█]
1.8k ╷        █                   █                                    
 957 ┤     █  █     ▄             █                                    
 562 ┼▄▄▄─▄██─█─────█▄───────────▄█─█────────────────────█─────────────
   0 ╵▒▒█▄░██▄▒▒▄   ▒▒      ▄▄▄░ ░▓▄▓                    ░▄     ▄      
     └─▲────────────▲────────────▲────────────▲────────────▲──────────▲─
      Nov 22       Nov 09       Oct 28       Oct 15       Oct 02     Sep
      Stack: [█] stem-curricul (22%)  [▓] home-telemetr (12%)  [▒] mail-
────────────────────────────────────────────────────────────────────────
MODEL       [QUOTA ┼ TARGET] SHARE    CALLS     TOK    EST.$  DLT  STAT
Carbon 4    [█▓░┼░░░░░░░░░░]  9.6%  11,411    2.6B  $720.2  -10% OK  
Neon 4      [░┼░░░░░░░░░░░░]  0.0%       0       0   $0.00  -10% OK  
Argon 4     [███┼███░░░░░░░] 47.3%  56,258    8.3B  $2,099  +22% WARN
Hydrogen 4  [░░┼░░░░░░░░░░░]  0.0%       0       0   $0.00  -15% WARN
Flash 3.8   [███┼██▓░░░░░░░] 42.9%  50,984    1.0B  $150.7  +23% WARN
Opus 5.5    [▏░░░░░░░░░░░░░]  0.0%       0       0   $0.00   -3% OK  
Sonnet 5.5  [░┼░░░░░░░░░░░░]  0.2%     192   25.6M   $9.46   -5% OK  
GPT-OSS 120 [▏░░░░░░░░░░░░░]  0.0%       0       0   $0.00   -2% OK  
BILLING    Hist:$2,979 API | NextRate:$5,949 (+100%) | 20x:4.9x
────────────────────────────────────────────────────────────────────────
WORKSPACES (15)  CHATS  STEPS    TOK   TOK/D   TOK/WK   EST.$  SHARE
1. stem-curricul  65c 54,384    3.2B  63.3M  443.2M  $793.7  21.5%
2. home-telemetr   4c 31,473    2.0B  38.3M  267.8M  $480.1  12.5%
3. mail-triage-u  28c 29,397    2.0B  38.5M  269.8M  $401.8  11.6%
4. task-queue-en   1c 25,933  346.9M  6.80M   47.6M   $96.3  10.3%
5. quiet-ui-skil  29c 22,657    1.3B  26.1M  182.7M  $379.2   9.0%
6. net-topology-   4c 18,859  815.5M  16.0M  111.9M  $188.7   7.5%
7. agy-nexus-mcp  23c 18,347    1.2B  23.0M  161.0M  $316.4   7.3%
8. cloud-gitops-   4c 15,070   52.7M  1.03M   7.23M   $11.9   6.0%
9. edge-iot-cont   6c 12,250    9.5M   186k   1.30M   $1.51   4.9%
10. agent-harnes   8c  9,457  485.1M  9.51M   66.6M  $123.7   3.7%
11. scratch-prot   8c  7,797  350.8M  6.88M   48.1M  $110.1   3.1%
12. container-gi   4c  4,995  247.0M  4.84M   33.9M   $69.3   2.0%
13. astro-sky-ma   1c  1,126    294k   5.8k     40k   $0.02   0.4%
14. rf-dsp-modem   0c    609   34.6M   678k   4.75M   $4.37   0.2%
15. civic-map-en   1c    177    6.9M   136k    951k   $1.74   0.1%
────────────────────────────────────────────────────────────────────────
SUBAGENTS (10)    RUNS  STEPS    TOK   TOK/D   TOK/WK   EST.$  SHARE
1. flash-surgeon 154r 26,152  369.9M  7.25M   50.8M   $51.0  29.2%
2. argon-sentine 115r 23,586    1.1B  22.2M  155.3M  $401.3  26.4%
3. flash-auditor 183r 15,641  417.6M  8.19M   57.3M   $64.1  17.5%
4. research       68r  8,881  370.1M  7.26M   50.8M  $136.8   9.9%
5. argon-surgeon  13r  8,185  524.5M  10.3M   72.0M  $121.9   9.1%
6. flash-scout    64r  6,197  157.8M  3.09M   21.7M   $24.5   6.9%
7. claude-sentin   6r    601   25.9M   508k   3.56M   $9.45   0.7%
8. argon-archite   2r    132    3.8M    75k    528k   $1.79   0.1%
9. carbon-sentin   1r     60    3.0M    59k    410k   $1.35   0.1%
10. claude-speci   1r     31   11.8k    231    1.6k   $0.00   0.0%
════════════════════════════════════════════════════════════════════════
```

### 2. `style="quick"` (40-Column Mobile Layout)

```text
════════════════════════════════════════
AGY-NEXUS v4.0.1 // 91d (Nov 22 ◄── Aug 
════════════════════════════════════════
G-20x: 100% [████████┼█] OK | 0x 429s
P-1x : 100% [░┼░░░░░░░░] OK | 0% WkLft
Steps:252.5k | Tools:128.7k | Act:51d
Burn:12.0B | $2,979 | 235.3M/d
Health: Poly 2360s | 84/84 <=500L | up_t
────────────────────────────────────────
HEATMAP (NOW ──► 13w Ago)  │ PEAK & VOL
Mo █▓▒▓░░·░·····           │ Pk: 11/14
Tu █▓▒▒▒░··░····           │ 16,811 stp
We █▓▓▒·░·░░····           │ Avg:4,951/d
Th █▒▒▒░░··▒····           │ Cost: $2,97
Fr ██▓▒▓░·▒▓····           │ Subs : 607r
Sa ████▓░·▓▒····           │ Tok/d:235.3
Su ███▓▓▒·▓·····           │ Tok/w:1.65B
────────────────────────────────────────
8H PACE & STACK (NOW──►OLD) Pk:1.6k
1.6k╷ █  █                           
 779┤ █ ▄█                           
 484┼▄█─██───────────────────────────
   0╵▒█ █▒  ▄▄▄ ▄░ ▄                 
────────────────────────────────────────
MODEL   [PIN]    PCT   TOK  EST.$   DLT
Carbon4 [█┼░░░░░░] 10%  2.6B $720.2 -10
Neon 4  [░┼░░░░░░]  0%     0  $0.00 -10
Argon 4 [██┼█▓░░░] 47%  8.3B $2,099 +22
Hydro 4 [░┼░░░░░░]  0%     0  $0.00 -15
Flash38 [█┼█▓░░░░] 43%  1.0B $150.7 +23
Opus5.5 [▏░░░░░░░]  0%     0  $0.00  -3
Sonn5.5 [▏░░░░░░░]  0% 25.6M  $9.46  -5
GPT-120 [▏░░░░░░░]  0%     0  $0.00  -2
────────────────────────────────────────
WORKSPACES & SUBS  TOK   EST.$  TOK/WK
stem-curriculum  3.2B  $793.7  443.2M
home-telemetry-  2.0B  $480.1  267.8M
mail-triage-ui   2.0B  $401.8  269.8M
task-queue-engi 346.9M   $96.3   47.6M
quiet-ui-skills  1.3B  $379.2  182.7M
net-topology-an 815.5M  $188.7  111.9M
*flash-surgeon  369.9M   $51.0   50.8M
*argon-sentinel  1.1B  $401.3  155.3M
*flash-auditor  417.6M   $64.1   57.3M
════════════════════════════════════════
```

### 3. `style="rich"` (76-Column Widescreen Layout)

```text
╔══════════════════════════════════════════════════════════════════════════╗
║ ▄▀█ █▀▀ █▄█ ▄▄ █▄░█ █▀▀ ▀▄▀ █░█ █▀   v4.0.1 // RICH TELEMETRY RIG        ║
║ █▀█ █▄█ ░█░ ░░ █░▀█ ██▄ █░█ █▄█ ▄█   WINDOW: 91d (Nov 22 ◄── Aug 24)     ║
╠════════════════════════════════════╦═════════════════════════════════════╣
║ QUOTA POOLS & 429 COOLDOWNS        │ STEP & TOOL VELOCITY                ║
║ G-20x:  99.8% [████████┼█] OK      │ Total : 252,531 steps | 128,733 too ║
║ P-1x :  99.8% [░┼░░░░░░░░] OK      │ Active: 4,951 s/act-d (51d active)  ║
║ 429s : 0 events | 0.0% Wk Left     │ Calend: 2,775 s/cal-d (186c, 607r)  ║
╠════════════════════════════════════╬═════════════════════════════════════╣
║ TOKEN BURN & API COST LEDGER       │ MCP WIRE & CLIENT SURFACES          ║
║ Total : ~12.0B | $2,979.04         │ Wire  : 96% <20KB (avg 12.7/38.6KB) ║
║ Daily : 235.3M/d ($58.41/d)        │ Calls : 139 MCP reqs (484k tok)     ║
║ NextRt: $5,948.62 API Forecast     │ Client: Web 68% · Prx 32% · Mob 0%  ║
╠════════════════════════════════════╦═════════════════════════════════════╣
║ VERSION & RELEASE STATUS           │ POLYGLOT & MODULAR CODE HEALTH      ║
║ Installed: v4.0.1 (up_to_date)     │ Poly: 2360s | 84/84 <=500L 0>650L   ║
║ Remote   : v4.0.1                  │ IDE MCP  : agy-praxis-mcp + Serena  ║
╠════════════════════════════════════╩═════════════════════════════════════╣
║ DAILY ACTIVITY MATRIX (NOW: W01 ──► W13)     [·· 0  ░░ <1k  ▒▒ <4k  ██]  ║
║ Wk   W01 W02 W03 W04 W05 W06 W07 W08 W09 W10 W11 W12 W13  ┌─ PEAK DAY ─┐ ║
║ Mon  ███ ▓▓▓ ▒▒▒ ▓▓▓ ░░░ ░░░ ··· ░░░ ··· ··· ··· ··· ···  │ Nov 14     │ ║
║ Tue  ███ ▓▓▓ ▒▒▒ ▒▒▒ ▒▒▒ ░░░ ··· ··· ░░░ ··· ··· ··· ···  │ 16,811 stp │ ║
║ Wed  ███ ▓▓▓ ▓▓▓ ▒▒▒ ··· ░░░ ··· ░░░ ░░░ ··· ··· ··· ···  ├────────────┤ ║
║ Thu  ███ ▒▒▒ ▒▒▒ ▒▒▒ ░░░ ░░░ ··· ··· ▒▒▒ ··· ··· ··· ···  │ Act: 51d   │ ║
║ Fri  ███ ███ ▓▓▓ ▒▒▒ ▓▓▓ ░░░ ··· ▒▒▒ ▓▓▓ ··· ··· ··· ···  │ Avg:  5.0k │ ║
║ Sat  ███ ███ ███ ███ ▓▓▓ ░░░ ··· ▓▓▓ ▒▒▒ ··· ··· ··· ···  │ Sub: 607r  │ ║
║ Sun  ███ ███ ███ ▓▓▓ ▓▓▓ ▒▒▒ ··· ▓▓▓ ··· ··· ··· ··· ···  └────────────┘ ║
║ Vol  ███ ▅▅▅ ▃▃▃ ▃▃▃ ▂▂▂ ▁▁▁ ─── ▁▁▁ ▁▁▁ ─── ─── ─── ───  PeakWk:78.2k   ║
║ Steps 78k 53k 35k 31k 19k  7k  ·  16k 12k  ·   ·   ·   ·                 ║
╠══════════════════════════════════════════════════════════════════════════╣
║ 8H SUB-DAILY HORIZON CURVE & PROJECT STACK (NOW ──► SEP 21)              ║
║  796 ╷ ▄█                                                                ║
║  620 ┤▄██▄                                                               ║
║  437 ┤████   ▄        █     █ ▄  ▄                                       ║
║  288 ┼█████▄─█───█────█─────█▄█──█──▄─────────────────────────────────   ║
║  143 ┤██████ █   █  █ █   ▄ ███  ██ █                                    ║
║    0 ╵▒▒█░█░ █ ▄▒░  ▒ █▄  ▓ ▓▓▓ ░░▓▄░   ▓░     ▓                         ║
║      └─▲───────────▲───────────▲───────────▲───────────▲───────────▲───  ║
║       Nov 22      Nov 09      Oct 27      Oct 14      Oct 01      Sep 21 ║
║       Stack: [█]stem-curricu(22%)  [▓]home-telemet(12%)  [▒]mail-triage- ║
╠══════════════════════════════════════════════════════════════════════════╣
║ MODEL       [QUOTA ┼ TARGET] SHARE    CALLS     TOK    EST.$  DLT  STAT  ║
║ Carbon 4    [█▓░┼░░░░░░░░░░]  9.6%  11,411    2.6B  $720.2  -10% OK      ║
║ Neon 4      [░┼░░░░░░░░░░░░]  0.0%       0       0   $0.00  -10% OK      ║
║ Argon 4     [███┼███░░░░░░░] 47.3%  56,258    8.3B  $2,099  +22% WRN     ║
║ Hydrogen 4  [░░┼░░░░░░░░░░░]  0.0%       0       0   $0.00  -15% WRN     ║
║ Flash 3.8   [███┼██▓░░░░░░░] 42.9%  50,984    1.0B  $150.7  +23% WRN     ║
║ Opus 5.5    [▏░░░░░░░░░░░░░]  0.0%       0       0   $0.00   -3% OK      ║
║ Sonnet 5.5  [░┼░░░░░░░░░░░░]  0.2%     192   25.6M   $9.46   -5% OK      ║
║ GPT-OSS 120 [▏░░░░░░░░░░░░░]  0.0%       0       0   $0.00   -2% OK      ║
║ BILLING CMP: Hist $2,979 | NextRate $5,949 (+100%) | 20x 4.9x            ║
╠══════════════════════════════════════════════════════════════════════════╣
║ WORKSPACES (15)  CHATS   STEPS     TOK   TOK/D   EST.$ SHARE GAUGE       ║
║ 1. stem-curricul  65c  54,384    3.2B  63.3M  $793.7 █▍░░░░ 21.5%        ║
║ 2. home-telemetr   4c  31,473    2.0B  38.3M  $480.1 ▍░░░░░ 12.5%        ║
║ 3. mail-triage-u  28c  29,397    2.0B  38.5M  $401.8 ▍░░░░░ 11.6%        ║
║ 4. task-queue-en   1c  25,933  346.9M  6.80M   $96.3 ▍░░░░░ 10.3%        ║
║ 5. quiet-ui-skil  29c  22,657    1.3B  26.1M  $379.2 ▍░░░░░  9.0%        ║
║ 6. net-topology-   4c  18,859  815.5M  16.0M  $188.7 ▍░░░░░  7.5%        ║
║ 7. agy-nexus-mcp  23c  18,347    1.2B  23.0M  $316.4 ▍░░░░░  7.3%        ║
║ 8. cloud-gitops-   4c  15,070   52.7M  1.03M   $11.9 ▍░░░░░  6.0%        ║
║ 9. edge-iot-cont   6c  12,250    9.5M   186k   $1.51 ▍░░░░░  4.9%        ║
║ 10. agent-harnes   8c   9,457  485.1M  9.51M  $123.7 ░░░░░░  3.7%        ║
║ 11. scratch-prot   8c   7,797  350.8M  6.88M  $110.1 ░░░░░░  3.1%        ║
║ 12. container-gi   4c   4,995  247.0M  4.84M   $69.3 ░░░░░░  2.0%        ║
║ 13. astro-sky-ma   1c   1,126    294k   5.8k   $0.02 ░░░░░░  0.4%        ║
║ 14. rf-dsp-modem   0c     609   34.6M   678k   $4.37 ░░░░░░  0.2%        ║
║ 15. civic-map-en   1c     177    6.9M   136k   $1.74 ░░░░░░  0.1%        ║
╟──────────────────────────────────────────────────────────────────────────╢
║ SUBAGENTS (10)    RUNS   STEPS     TOK   TOK/D   EST.$ SHARE GAUGE       ║
║ 1. flash-surgeon 154r  26,152  369.9M  7.25M   $51.0 █▍░░░░ 29.2%        ║
║ 2. argon-sentine 115r  23,586    1.1B  22.2M  $401.3 █▍░░░░ 26.4%        ║
║ 3. flash-auditor 183r  15,641  417.6M  8.19M   $64.1 █░░░░░ 17.5%        ║
║ 4. research       68r   8,881  370.1M  7.26M  $136.8 ▍░░░░░  9.9%        ║
║ 5. argon-surgeon  13r   8,185  524.5M  10.3M  $121.9 ▍░░░░░  9.1%        ║
║ 6. flash-scout    64r   6,197  157.8M  3.09M   $24.5 ▍░░░░░  6.9%        ║
║ 7. claude-sentin   6r     601   25.9M   508k   $9.45 ░░░░░░  0.7%        ║
║ 8. argon-archite   2r     132    3.8M    75k   $1.79 ░░░░░░  0.1%        ║
║ 9. carbon-sentin   1r      60    3.0M    59k   $1.35 ░░░░░░  0.1%        ║
║ 10. claude-speci   1r      31   11.8k    231   $0.00 ░░░░░░  0.0%        ║
╚══════════════════════════════════════════════════════════════════════════╝
```

---

## Advanced Workflows: Gemini Notebook, Scheduled Gemini Tasks & Split-Trust

1. **Zero-Token Reference Lookup with Gemini Notebook**: Store large hardware manuals, RFCs, or API specs in Gemini Notebook, extract exact cited excerpts in Gemini, and dispatch a concise brief via `send_handoff_and_resume` so local agents start coding immediately without burning local context scanning PDFs.
2. **Searchable Project Memory (`export_notebook` with `dry_run` Preview)**: Export completed session plans and walkthroughs into SHA-256 deduplicated Markdown files (`YYYY-MM-DD_<repo>_<title>_<id>.md`) via `manage_background_run(action="export_notebook")` (pass `dry_run=True` first to preview pending exports).
3. **Scheduled Gemini Tasks & Split-Trust Lock Options**:
   - **`AG_BRIDGE_ALLOW_LOCKED_STATS=true`**: Allows `get_session_tree(include_stats=True)` and `manage_background_run(action="stats")` to return policy-safe usage/quota summaries while locked without exposing code, paths, or chat messages.
   - **`AG_BRIDGE_ALLOW_LOCKED_STAGING=true`**: Allows `send_handoff_and_resume(..., resume_headless=False)` while locked to stage incoming notes into `sidecar_data/ag-bridge-bg/quarantine_handoffs/`.
   - **Single-Turn Multi-Repo Drift Audits**: Call `inspect_git_diff(workspace_override="ALL")` to audit uncommitted changes across every repository in one turn.
4. **Virtual URI Dispatcher (`virtual_uris.py`)**: Read untruncated conversation turns (`transcript:<conv_id>:turn:latest`), nested session artifacts (`brain:<conv_id>/scratch/...`), Praxis/Polyglot maps (`praxis:map`, `praxis:handoffs`, `polyglot:search:<q>`), and policy-safe telemetry (`telemetry:stats`) directly via `ask_workspace_readonly`.

---

## Available MCP Tools (`17` Total Across Dual Doorways)

### 1. `agy-nexus-mcp` Remote & Mobile Bridge Surface (`11` Tools)

| Tool | What It Does |
| :--- | :--- |
| `unlock_sessions(spoken_passphrase, search_query="")` | Verifies your voice/text passphrase, unlocks the sliding-TTL deadbolt, and returns numbered recent sessions (`1..N`) plus live usage telemetry. |
| `lock_bridge()` | Immediately engages the deadbolt and clears unlocked session state. |
| `list_saved_sessions(limit, status_filter, include_subagents)` | Lists recent Antigravity chats with live status (`RUNNING`, `STALLED_WAITING_APPROVAL`, `COMPLETED`, `IDLE`, `RETIRED`), continuity tier, project path, and summary. |
| `load_session_into_gemini(session_identifier, include_files)` | Loads a chat by `#N`, `<repo-slug>-NN`, UUID prefix, or title keyword—returning `task.md`, `implementation_plan.md`, `walkthrough.md`, git status, 7-day signed `visual_artifacts`, `workspace_url`, continuity tier, and job-first `suggested_actions`. |
| `get_session_tree(active_only, project_filter, limit, include_stats, period, style)` | Renders the copy-ready 76-column ASCII `Project -> Chat -> Session ID` + `[HANDOFF <slug>-NN]` hierarchy, 3-2-1 backup status, and optional `include_stats=True` three-tier ASCII telemetry. |
| `ask_workspace_readonly(question, search_query, file_subpath, start_line, end_line, session_identifier, workspace)` | Searches code (bounded multi-repo `git grep` + live `transcript_full.jsonl`/`brain/` search) or reads up to 12 files with line slicing, Virtual URIs (`transcript:`, `brain:`, `praxis:`, `telemetry:`), and cached Polyglot outlines. |
| `inspect_git_diff(target_branch, include_untracked, workspace_override, file_path, offset_chars, start_line, end_line, session_identifier, workspace)` | Inspects current branch, status, and paginated git diff for a repository—or pass `workspace_override="ALL"` to audit drift across all repositories in one call. |
| `inspect_visual_artifacts(session_identifier, artifact_filter, max_images, include_binary)` | Encodes crisp adaptive WebP previews (`< 20 KB` wire budget) alongside 7-day HMAC-SHA256 signed `/web/media/` links and canonical `/web#workspace` deep links. |
| `send_handoff_and_resume(research_markdown, resume_headless, execution_mode, session_identifier, workspace_path, project_name, create_new_project, session_continuity, retire_session, retirement_summary, ...)` | Stages repo-prefixed `<slug>-NN` handoffs, enforces fail-closed `PROJECT_NOT_FOUND` & `[RETIRED_SESSION_GUARD]` checks, handles `RESUME_STAGED`, continuity-aware rollover, in-place closeout/retirement (`RETIRED.json`), and wakes Antigravity. |
| `manage_background_run(action, job_id, tail_lines, period, style, dry_run)` | Monitors background jobs (`status`, `tail`, `stop`), renders `sessions` or 3-tier `stats`, or exports SHA-256 deduplicated plans/walkthroughs (`export_notebook` with `dry_run` preview). |
| `list_models_and_agents(include_skills, include_rules, skill_scope_filter, inspect_name)` | Lists configured Agent Roles, Skills, Rules, and Dual-Pool quota settings, or reads a specific skill/rule contract via `inspect_name`. |

### 2. `agy-praxis-mcp` Local Antigravity IDE Surface (`6` Tools — LAN-Only / `--stdio`)

| Tool | What It Does |
| :--- | :--- |
| `polyglot_map(workspace="", path_prefix="", limit=120, force_refresh=False)` | Builds or incrementally refreshes the SHA-256 Polyglot index for a workspace and returns its semantic file map, line counts, and top symbol spans. |
| `polyglot_search(query, workspace="", kind="", limit=25, force_refresh=False)` | Searches indexed functions, classes, methods, headings, JSON/YAML keys, CSS rules, and 1-liner docstrings with exact `Lstart-Lend` slice hints. |
| `polyglot_outline(file_subpath, workspace="", include_callers=False)` | Returns the complete `Lstart-Lend` structural outline, signatures, `>100L` function warnings, and 1-liner docstrings for a single file. |
| `praxis_handoff_inbox(workspace="", status_filter="ALL", include_superseded=True, limit=25)` | Lists repo-prefixed Gemini handoffs (`<repo-slug>-01`, `<repo-slug>-02`, ...) across `STAGED`, `IN_WORK`, `SUPERSEDED`, and `COMPLETED` states. |
| `praxis_claim_handoff(handoff_id="", workspace="", conversation_id="", force=False)` | Atomically claims a staged `<repo-slug>-NN` ticket for IDE execution (`STAGED` $\rightarrow$ `IN_WORK`), returning unwrapped `specification_markdown` (or disambiguating candidates). |
| `praxis_update_handoff(handoff_id, status="COMPLETED", conversation_id="", notes="")` | Updates a handoff ticket's lifecycle state (`COMPLETED`, `IN_WORK`, `STAGED`, or `SUPERSEDED`). |

---

## Comparison with Typical Antigravity Bridges

| Feature | Typical Community Bridges (`agy-bridge`, `meridian`, `ag-local-bridge`) | `agy-nexus-mcp` (`v4.0.1`) |
| :--- | :--- | :--- |
| **Connection Architecture** | Local `stdio` pipe or single-chat Telegram/WhatsApp bot | **Dual-Doorway Streamable HTTP MCP** (`agy-nexus-mcp` for Gemini Web/Mobile/Tasks + LAN-only `agy-praxis-mcp` for local Antigravity IDE) |
| **Zero-Trust Security** | None or static chat-ID allowlist | **5-Layer Defense**: Secret URL Path + Voice/Text Deadbolt + LAN-Only Praxis Gate + Sandboxed ZIP/File Readers + HMAC Host Bridge |
| **Parallel Isolation & Routing** | Single active chat; parallel tabs overwrite state | **Keyed Context Slots (`active_contexts` + Auto-Prune) + Fail-Closed 3-Pillar Resolver + `<repo-slug>-NN` Queue + Proportional Fast-Path** |
| **Session Lifecycle & Closeout** | Blind context overflows or manual chat juggling | **Strict Recency Sorting + Continuity-Aware Rollover + In-Place Closeout & `RETIRED.json` Tombstones + Job-First `"Yes"` Flow** |
| **Web Studio & Showcase App** | None | **Quiet UI `v9.3.0` Studio (`/web`) + Static GitHub Pages Showcase**: 8-Model Micro-USD Cost Ledger, Active-Day Whiskers, 2-Pane Workspace & Gallery |
| **Visual Artifact Round-Trip** | None | **7-Day HMAC-SHA256 `/web/media/` Links + Press-and-Glide Selection + `Per Sheet 2/4/8` `3072px` Sheets + Direct `.png` Downloads + Web Share v2 + `.zip`** |
| **Chat ASCII Telemetry** | None | **Dynamic 8-Model Three-Tier ASCII** (`default` 72-col, `quick` 40-col mobile, `rich` 76-col desktop) + **76-Col Session & Model Matrices** |

---

## Bundled 12-Agent Orthogonal Roster (`agents/`)

`agy-nexus-mcp` ships with the synced Dual-Pool subagent roster in [`agents/`](agents/) (`swarm-orchestrator`, `flash-scout`, `argon-architect`, `flash-surgeon`, `hydrogen-surgeon`, `neon-surgeon`, `argon-surgeon`, `flash-auditor`, `argon-sentinel`, `claude-specialist`, `claude-sentinel`, `pool-failover`) verified via `scripts/sync_agents.py --check`.

```bash
python3 scripts/sync_agents.py --apply   # Sync agents/*.md -> ~/.gemini/config/agents/
```

Subagent runs, `$ Est. Cost`, and `Avg Tok/Run` appear in `/web` and ASCII reports. See [`AGENTS.md`](AGENTS.md) and [`agents/README.md`](agents/README.md).

---

## Repository Layout (`v4.0.1`)

*(See [`AGENTS.md`](AGENTS.md) for the complete modular architecture reference.)*

```text
agy-nexus-mcp/
├── src/agy_nexus/        # Modular backend/MCP modules (<=500L target, 650L ceiling):
│                         #   model_pricing, cost_ledger, project_stats, ascii_{default,rich,models},
│                         #   config, hygiene, polyglot_*, handoff_*, tools_praxis, stats*, media*,
│                         #   bucket_*, web_routes, uploads, sessions, routing, target_resolver, server
├── ag_bridge.py          # Backward-compatible 75-line root entrypoint shim
├── web/                  # Quiet UI v9.3.0 Studio PWA (primary /web + /web/v9 + offline vendored ECharts):
│                         #   index.html, manifest.webmanifest, sw.js, demo_snapshot.js, v9/* & v9/vendor/*
├── host_bridge/          # Loopback-only authenticated Host Companion (:8098), CreateProject & HMAC security
├── agents/ & skills/     # Synced 12-Agent Dual-Pool Roster & agy-nexus-stats SKILL.md
├── docs/                 # DEPLOYMENT.md, WORKFLOWS.md, QUIET_UI_V9_FIELD_REPORT.md & assets/ screenshots
├── scripts/              # setup, sync_agents, check_model_drift, export_depersonalized_showcase, build_github_showcase, publish_to_github
├── systemd/ & .github/   # 01:45 AM drift watchdog timer & issue/PR templates
├── tests/                # Pytest regression suites + conftest STATE_FILE isolation (v2.6 – v4.0.1)
└── README.md, AGENTS.md, CHANGELOG.md, SECURITY.md, CONTRIBUTING.md, ACCESSIBILITY.md, LICENSE, NOTICE
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
   - The voice-passphrase deadbolt (`PASS_HASH`), unguessable `PATH_SECRET` routing, LAN-only `agy-praxis-mcp` isolation, path-traversal sandboxing, and read-only SQLite isolation are core security guarantees of `agy-nexus-mcp`.
   - Any fork or derivative work that weakens, bypasses, or strips these security controls **must** prominently disclose that its security boundary has been removed or altered and may not present itself under the unmodified `agy-nexus-mcp` / `AGY-NEXUS` identity.
