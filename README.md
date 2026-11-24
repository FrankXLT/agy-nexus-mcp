# `agy-nexus-mcp` — Connect Google Gemini to Your Antigravity IDE, 2-Pane Workspace & Usage Studio (`v4.0.8`)

<!-- mcp-name: io.github.FrankXLT/agy-nexus-mcp -->

`agy-nexus-mcp` is a self-hosted **Dual-Doorway Model Context Protocol (MCP)** server connecting **Google Gemini** (Web, Mobile & Tasks) directly to your local **Google Antigravity IDE / CLI** workstation—paired with **`agy-praxis-mcp`** (deadbolt-free LAN-only semantic codebase index & `<repo-slug>-NN` handoff inbox), a **Public GHCR OCI `--stdio` Container** (`ghcr.io/frankxlt/agy-nexus-mcp`) published to the Official MCP Registry, and the **Quiet UI `v9.3.0` Studio PWA (`/web`)** featuring live **8-Model Micro-USD Analytics**, **Hybrid Range Whiskers & Target/Seam Caret Bars**, **Multi-Column Sortable Tables**, **Desktop Sidebar Pinning**, and a **2-Pane Session Workspace Explorer**.

> **[Try the Interactive Live Showcase (Real Workstation Telemetry, 0 Backend Required)](https://FrankXLT.github.io/agy-nexus-mcp/)**

---

## Live `/web` Unified Studio App (`Analytics` + 2-Pane `Workspace`)

### 1. `Analytics` — 8-Model Cost Ledger, Range Whiskers & `Mon–Sun` Calendar Matrix
![AGY-NEXUS v4.0.8 Analytics Surface — Quiet UI v9.3.0 Studio, 6-Window Presets, 8-Model Micro-USD Cost Ledger, Hybrid Range Whiskers & Target/Seam Caret Bars, Single-Hue 52-Week Mon–Sun Calendar Matrix, Sortable Tables & Code Health](docs/assets/dashboard-desktop.png)

### 2. `Workspace` — Responsive 2-Pane Session Explorer, Editorial Reader & Capture Gallery
![AGY-NEXUS v4.0.8 2-Pane Workspace Explorer — Recency Project Rail, Editorial Markdown Tabs, Inline Walkthrough Captures & Direct PNG / Per Sheet Gallery](docs/assets/workspace-desktop.png)

<details>
<summary><strong>📱 Mobile Layouts (<code>390px</code> Portrait — Analytics <code>26w</code> Matrix &amp; Clean Wrapped Workspace Tabs)</strong></summary>

![AGY-NEXUS v4.0.8 Mobile Analytics View](docs/assets/dashboard-mobile.png)
![AGY-NEXUS v4.0.8 Mobile Workspace View](docs/assets/workspace-mobile.png)

</details>

---

## Key Capabilities (`v4.0.8`)

- **Public GHCR OCI Container, Zero-Stdout `--stdio` & MCP Registry OIDC**: One-click installation (`ghcr.io/frankxlt/agy-nexus-mcp:4.0.8` via `--stdio`) for VS Code, Copilot CLI, Claude Code, and MCP Inspector without `PATH_SECRET`—serving deadbolt-safe `list_models_and_agents(style="ascii")` immediately while keeping private workspace tools fail-closed unless a valid 64-hex `PASS_HASH` is configured, backed by `server.json` (`2025-12-11`) and Sigstore `cosign` + `github-oidc` CI publishing.
- **Dual-Doorway Parallel Isolation & `<repo-slug>-NN` Queue**: Concurrent Gemini Web/Mobile tabs work across separate repositories via `fcntl.flock` `active_contexts` slots (auto-pruning stale slots), 3-pillar fail-closed resolution (`target_resolver.py`), same-repo concurrent writer detection (`MAIN WRITER` / `WORKTREE` / `SHARED`), and atomic `<slug>-NN` handoffs (`handoff_queue.py`) with proportional **Surgical Fast-Path** vs. Full Dual-Review execution (`handoff_templates.py`).
- **8-Model Registry, Effective-Dated Cost Ledger & `01:45 AM` Drift Watchdog**: Tracks all 8 live models (`Gemini 4 Carbon`, `Neon`, `Argon`, `Hydrogen`, `Gemini 3.8 Flash`, `Claude Opus 5.5`, `Claude Sonnet 5.5`, `GPT-OSS 120B`) with immutable micro-USD epochs (`CACHE_VERSION = 8`, `cost_ledger.json`), deadbolt-safe `76`-col `models` ASCII status, `12`-subagent `sync_agents.py`, and read-only `01:45 AM` `agy-model-drift-check.timer`.
- **`agy-praxis-mcp` Local IDE Doorway (`6` Tools)**: Incremental SHA-256 Polyglot semantic indexing (`polyglot_map` strictly `<= 17.5 KB` with `directory_summary` + `drilldown_hint`, `polyglot_search`, `polyglot_outline`) + `<repo-slug>-NN` handoff queue (`/praxis/{PRAXIS_MCP_TOKEN}/mcp`, legacy `/polyglot/` alias, or `--stdio`) with strict LAN-only `403` proxy/Origin rejection.
- **Strict `< 20 KB` Wire Budget, `@Agy Nexus Mcp` 1-Tap Chips & In-Place Closeout**: Sequential Read-Only Governance (`<= 4` hops/turn), `tools/list` (`<= 8.6 KB`), `get_session_tree` (`<= 17.5 KB`), `<= 18.5 KB` inner / `<= 19.8 KB` escaped outer wire caps, `REPLY_PROMPT_GUIDANCE` + XML `followup_xml` 1-tap `<FollowUp>` / `<ElicitationsGroup>` reply chips prefixed with `@Agy Nexus Mcp ` across every tool, 5-tier context pressure (`FRESH` $\rightarrow$ `HARD_ROLLOVER`), `RETIRED.json` tombstones (`retire_after_closeout=True`), and `workflow:baseline`.
- **Quiet UI `v9.3.0` Studio (`/web`) & Public Interactive Showcase**: Direct `/web` live cutover (`/web/v9` compatible), offline vendored Apache ECharts, `[Steps | Tokens | $ Cost]`, **Option A Hybrid Range Whiskers & Target/Seam Caret Bars** (`Avg · Peak · 24h` project/subagent whiskers with `>120` step-cap alerts, model `Guide │ + 24h ▾`, session `320│ / 700▾` seams), multi-column sortable tables with preserved swatch colors, `>= 1100px` desktop sidebar pinning, `Activity by Hour of Day` active-day whiskers, `Subscription Break-Even`, responsive `< 760px` Docs + `[Captures (N)]` modal, and zero-leak **GitHub Pages Showcase** (`scripts/build_github_showcase.py`).

---

## Quick Setup & Everyday Prompts

1. **Initialize & Self-Test** *(or launch `--stdio` directly via Docker)*:
   ```bash
   docker run -i --rm ghcr.io/frankxlt/agy-nexus-mcp:4.0.8 --stdio
   # Or run locally from source:
   python3 ag_bridge.py --self-test && python3 -m agy_nexus.tools_praxis --self-test && pytest
   python3 ag_bridge.py   # or docker compose up -d (see docs/DEPLOYMENT.md)
   ```
2. **Connect Clients**:
   - **MCP Registry / Local IDE (`--stdio`)**: Install `io.github.FrankXLT/agy-nexus-mcp` from `github.com/mcp` (`ghcr.io/frankxlt/agy-nexus-mcp:4.0.8 --stdio`), optionally passing `PASS_HASH` to unlock private workspace tools.
   - **Gemini Web / Mobile / Tasks**: Add custom MCP `https://<your-domain>/{PATH_SECRET}/mcp` (voice/text unlock strips filler via `unlock_sessions`).
   - **Antigravity IDE (`agy-praxis-mcp`)**: Point `~/.gemini/config/mcp_config.json` to `http://<host>.lan:8765/praxis/<PRAXIS_MCP_TOKEN>/mcp`.
   - **Quiet UI Studio PWA (`/web`) & Public Demo**: Open `https://<your-domain>/web` (`?demo=1` for depersonalized preview) or explore the [Public GitHub Pages Showcase](https://FrankXLT.github.io/agy-nexus-mcp/).
3. **Example Prompts**: *"Unlock Antigravity with [phrase] and load `agy-nexus-mcp`"* · *"Show me my session tree"* · *"Show model & subagent status"* · *"Search `cloud-gitops-stack` for compose healthcheck rules"* · *"Stage this bugfix (`allow_chained_publish=False`)"* · *"Show me my latest usage stats (`default` / `quick` / `rich`)."*

---

## Project Manager Mode & Plain-Language Handoffs (`v4.0.8`)

`agy-nexus-mcp` turns Google Gemini into a grounded **Engineering Project Manager**: Gemini scouts live state sequentially (`<= 4` calls/turn), stages `<repo-slug>-NN` handoffs with proportional `execution_mode="auto"` ceremony (`allow_chained_publish=False` for preview gates with 7-day `/web/media/` screenshots), and guides **Job-First `"Yes"`** `@Agy Nexus Mcp` 1-tap chips (`followup_xml`) across `ready_to_run` (staged tickets), `in_flight` (running tasks), `ready_to_ship` (in-place `retire_session=True` + `RETIRED.json` closeout), and `retired`.

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
║ AGY-NEXUS v4.0.8 // PROJECT -> CHAT -> SESSION ID HIERARCHY (COPY-READY) ║
╠══════════════════════════════════════════════════════════════════════════╣
║ SLOTS: 3 | STAGED: 1 | IN-WORK: 2 | PINNED: 24 | TTL: 119.5m             ║
║ 3-2-1 BACKUP: a64b93c (SYNCED ✓ · 21496.5 KB · 3h ago)                   ║
╚══════════════════════════════════════════════════════════════════════════╝

[PROJECT 1] AGY Nexus MCP [SHARED REPO] [▶ 1 IN-WORK]
  project_id : f1378431-5b09-4545-a48c-ac5c67c04fd3
  workspaces : /home/dev/agentic_workspace/projects/agy-nexus-mcp
  ├─ [HANDOFF agy-nexus-mcp-51] AGY-Nexus MCP v4.0.8 — GHCR OCI Package, --stdio Mode & MCP Registry OIDC
  │   pass_off   : [▶ IN-WORK] · plan/feature_update · 1h ago
  │   session_id : a93c8689-f63d-4bb1-af92-3c610d5ab3ad
  ├─ [HANDOFF agy-nexus-mcp-50] AGY-Nexus v4.0.7 — Closeout: DEPLOYMENT.md (?.*)? Sync, Publish & Retire
  │   pass_off   : [✓ COMPLETED] · fast/release_closeout · 17h ago
  │   session_id : 5fb0708a-e4cf-443d-bea2-e9f9a4b9dfee
  ├─ (+14 older completed)
  ├─ [#1] AGY-Nexus MCP v4.0.8 — GHCR OCI Package, --stdio Mode & MCP Registry OIDC
  │   session_id : a93c8689-f63d-4bb1-af92-3c610d5ab3ad
  │   workspace  : /home/dev/agentic_workspace/projects/agy-nexus-mcp
  │   status     : [● RUNNING] · MAIN WRITER · 550 steps · 8s ago
  ├─ [#12] AGY-Nexus v4.0.7 — 4-Gate WF-XX Workflow Engine, Thicker Mobile Topbar & Chart/Table Legends
  │   session_id : 5fb0708a-e4cf-443d-bea2-e9f9a4b9dfee
  │   workspace  : /home/dev/agentic_workspace/projects/agy-nexus-mcp
  │   status     : [○ COMPLETED] · SHARED (READ-ONLY) · 763 steps · 16h ago
  └─ [#16] AGY-Nexus v4.0.6 — Enforce @Agy Nexus Mcp 1-Tap Reply Chips Across All Tools
      session_id : 30287b28-f5b2-4852-8812-e2153b2549cd
      workspace  : /home/dev/agentic_workspace/projects/agy-nexus-mcp
      status     : [○ COMPLETED] · SHARED (READ-ONLY) · 350 steps · 20h ago

[PROJECT 2] Stem Curriculum Lab [SHARED REPO] [◈ 1 STAGED] [▶ 1 IN-WORK]
  project_id : 8d13c66f-569c-42e0-a57e-dd4b111ab5f2
  workspaces : /home/dev/agentic_workspace/projects/stem-curriculum-lab
  ├─ [HANDOFF stem-curriculum-lab-60] [SCL-Core] Stepped & Hex Domain Mosaics + Skill Trees
  │   pass_off   : [◈ STAGED · UNCLAIMED] · plan/feature_update · 5d ago
  │   session_id : (unclaimed · new chat)
  ├─ [HANDOFF stem-curriculum-lab-97] [SCL-Chem] Sprint 12 Release Closeout & Live Preview
  │   pass_off   : [▶ IN-WORK] · plan/feature_update · 12m ago
  │   session_id : f15bfe77-9e2e-41bf-8dfa-4200e832fc44
  ├─ (+18 older completed)
  ├─ [#2] [SCL-Arch] Sprints 1–14 — Curriculum Engine & Edge CI
  │   session_id : f15bfe77-9e2e-41bf-8dfa-4200e832fc44
  │   workspace  : /home/dev/agentic_workspace/projects/stem-curriculum-lab
  │   status     : [● RUNNING] · MAIN WRITER · 59 steps · 1m ago
  ├─ [#4] [SCL-RF] Ch. I–VIII Interactive Signal Modules Overhaul
  │   session_id : 35a81d19-4221-4b76-857d-81601469fb3a
  │   workspace  : /home/dev/agentic_workspace/projects/stem-curriculum-lab
  │   status     : [◉ PINNED · IDLE] · SHARED (READ-ONLY) · 377 steps · 42m ago
  └─ [#9] [SCL-RF] Ch. I–VIII Interactive Signal Modules Overhaul
      session_id : c76a0d4e-0e37-4f6a-9c47-3c5323646989
      workspace  : /home/dev/agentic_workspace/projects/stem-curriculum-lab
      status     : [○ COMPLETED] · SHARED (READ-ONLY) · 559 steps · 11h ago

[PROJECT 3] Quiet UI Skills [SHARED REPO]
  project_id : 696506de-5df1-41da-9b5c-03c2e1b9128c
  workspaces : /home/dev/agentic_workspace/projects/quiet-ui-skills
  ├─ [HANDOFF quiet-ui-skills-52] User Goal and Why
  │   pass_off   : [✓ COMPLETED] · fast/bug_or_visual_fix · 1s ago
  │   session_id : 08d20d27-df37-43ee-8084-9932b822c669
  ├─ [HANDOFF quiet-ui-skills-51] Quiet UI Skills v9.6.0 — Public Data, Research & Multi-Format Storytelling
  │   pass_off   : [✓ COMPLETED] · plan/feature_update · 1h ago
  │   session_id : 08d20d27-df37-43ee-8084-9932b822c669
  ├─ (+12 older completed)
  ├─ [#3] Quiet UI Skills v9.6.0 — Public Data, Research & Multi-Format Storytelling
  │   session_id : 08d20d27-df37-43ee-8084-9932b822c669
  │   workspace  : /home/dev/agentic_workspace/projects/quiet-ui-skills
  │   status     : [◉ PINNED · IDLE] · PINNED (VISION) · 803 steps · 3m ago
  ├─ [#14] Quiet UI Skills v9.4.0 Wave 2 — Cleanfield Workbench Archetypes, Flow Primitives & Brownfield CDP Probes
  │   session_id : 0b9b559c-8aee-49b1-97e8-ffd906b5744b
  │   workspace  : /home/dev/agentic_workspace/projects/quiet-ui-skills
  │   status     : [○ COMPLETED] · MAIN TREE · 458 steps · 18h ago
  └─ [#17] Quiet UI Skills v9.5.0 — Release Closeout, Tag, GitHub Release & Live Pages Verification
      session_id : c291b3c0-2dee-4443-83fe-97067037c8cb
      workspace  : /home/dev/agentic_workspace/projects/quiet-ui-skills
      status     : [○ COMPLETED] · MAIN TREE · 240 steps · 20h ago
```

---

## Three-Tier ASCII Usage Reports in Chat

Ask Gemini for your usage stats (`get_session_tree(include_stats=True, period="last_90d", style=...)` or `manage_background_run(action="stats", ...)`) to render live Dual-Pool quota pacing, `Mon–Sun` calendar heatmaps, sub-daily curves, and workspace/subagent token breakdowns in **three plain-text layouts**:

| Style | Width | Best For | What It Shows |
| :--- | :---: | :--- | :--- |
| **`style="default"`** | **72 cols** | Standard Desktop & Tablet Chat | Split summary header, 22-week `Mon–Sun` heatmap, 8-hour activity & project stack (`░▒▓█`), model quota bars (`┼`), Praxis/Polyglot health, and project & subagent tables. |
| **`style="quick"`** | **`<= 40` cols** | Phone Screens (Portrait) | Fits strictly within 40 characters per line so it never wraps on mobile. Shows a 13-week heatmap, 8-hour pace curve, model quota bars, and top projects/subagents. |
| **`style="rich"`** | **76 cols** | Widescreen Desktop Chat | Full box-drawn rig (`v4.0.4`) with side-by-side quota and token panels, 13-week 3-character heatmap with Peak Day card, 6-row 8-hour curve, and share gauges. |

### 1. `style="default"` (72-Column Standard Layout)

```text
════════════════════════════════════════╤═══════════════════════════════
AGY-NEXUS v4.0.8 // 91d (Nov 24 ◄── Aug ┆ Up to Date (v4.0.8)           
════════════════════════════════════════╪═══════════════════════════════
GOOGLE 20x :  99.5% [████████┼█] HEALTHY┆ 0x 429s | Ultra-20x (T:>=90%) 
PARTNER 1x :  99.5% [░┼░░░░░░░░] ON PACE┆ 71.4% Wk Left | Lim <=14.3%/d 
STEPS/TOOLS: 276,515s | 145,540t | 216c ┆ 5,217 s/act-d | 3,038 s/cal-d 
TOKEN BURN : ~13.6B | $3,409.82         ┆ 257.1M/d | $64.34/d (707r)    
MCP WIRE   : 99% <20KB (avg 12.0/26.4KB)┆ 112 req (370k tok) | Web+Praxi
CODE HEALTH: Poly 2630 syms | 88/88 <=50┆ 0 >650L | Praxis+Serena       
────────────────────────────────────────┴───────────────────────────────
DAILY HEATMAP (NOW: W01 ──► 22w AGO)   Peak: 11/22 (20,915s) | Act: 53d
Wk    01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22
Mon   ██ ██ ▒▒ ▒▒ ▓▓ ░░ ░░ ·· ░░ ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ··
Tue   ▓▓ ██ ▓▓ ▒▒ ▒▒ ░░ ░░ ·· ·· ░░ ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ··
Wed   ·· ██ ▓▓ ▓▓ ▒▒ ·· ░░ ·· ░░ ░░ ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ··
Thu   ·· ██ ▒▒ ▒▒ ▒▒ ░░ ░░ ·· ·· ▒▒ ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ··
Fri   ·· ██ ██ ▓▓ ▒▒ ▓▓ ░░ ·· ▒▒ ▓▓ ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ··
Sat   ·· ██ ██ ██ ██ ▓▓ ░░ ·· ▓▓ ▒▒ ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ··
Sun   ·· ██ ██ ██ ▓▓ ▓▓ ▒▒ ·· ▓▓ ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ··
Vol   ▂▂ ██ ▄▄ ▃▃ ▃▃ ▂▂ ▁▁ ── ▁▁ ▁▁ ── ── ── ── ── ── ── ── ── ── ── ──
────────────────────────────────────────────────────────────────────────
8H SUB-DAILY PACE (NOW ──► SEP 21)   [Avg: 374/8h | Peak: 1.0k | ░▒▓█]
1.0k ╷  █  █    ▄             ▄    ▄                                   
 531 ┤█ █  █    █             █   ██                                   
 374 ┼████─█─█▄▄█─────█─────▄─█───██──▄▄───────────────────────────────
   0 ╵████ █ ███▓░▓▄░ ▓ ▄▄█░░ ▒ ▄ ░░▒▄░░ ▄▒▄    ▒                  ▄   
     └─▲────────────▲────────────▲────────────▲────────────▲──────────▲─
      Nov 24       Nov 11       Oct 29       Oct 16       Oct 03     Sep
      Stack: [█] stem-curricul (22%)  [▓] mail-triage-u (12%)  [▒] home-
────────────────────────────────────────────────────────────────────────
MODEL       [QUOTA ┼ TARGET] SHARE    CALLS     TOK    EST.$  DLT  STAT
Carbon 4    [██▓┼░░░░░░░░░░] 13.0%  16,330    3.9B  $1,030   -7% OK  
Neon 4      [░┼░░░░░░░░░░░░]  0.1%     103   30.2M   $9.59  -10% OK  
Argon 4     [███┼██▓░░░░░░░] 45.6%  57,179    8.5B  $2,178  +21% WARN
Hydrogen 4  [░░┼░░░░░░░░░░░]  0.0%      34    2.2M   $1.13  -15% WARN
Flash 3.8   [███┼██▓░░░░░░░] 40.8%  51,192    1.0B  $153.7  +21% WARN
Opus 5.5    [▏░░░░░░░░░░░░░]  0.0%       0       0   $0.00   -3% OK  
Sonnet 5.5  [░┼░░░░░░░░░░░░]  0.4%     555   99.2M   $38.1   -5% OK  
GPT-OSS 120 [▏░░░░░░░░░░░░░]  0.0%       0       0   $0.00   -2% OK  
BILLING    Hist:$3,410 API | NextRate:$6,771 (+99%) | 20x:5.6x
────────────────────────────────────────────────────────────────────────
WORKSPACES (16)  CHATS  STEPS    TOK   TOK/D   TOK/WK   EST.$  SHARE
1. stem-curricul  72c 60,790    3.6B  68.2M  477.2M  $905.9  22.0%
2. mail-triage-u  31c 32,207    2.1B  40.4M  282.6M  $448.0  11.6%
3. home-telemetr   4c 31,912    2.0B  37.8M  264.7M  $492.6  11.5%
4. quiet-ui-skil  37c 27,638    1.7B  31.7M  222.2M  $472.7  10.0%
5. task-queue-en   1c 25,933  346.9M  6.55M   45.8M   $96.3   9.4%
6. agy-nexus-mcp  30c 23,111    1.5B  28.6M  200.2M  $398.0   8.4%
7. net-topology-   6c 20,803  955.2M  18.0M  126.2M  $219.2   7.5%
8. cloud-gitops-   4c 15,070   52.7M   995k   6.96M   $11.9   5.4%
9. edge-iot-cont   6c 12,250    9.5M   179k   1.25M   $1.51   4.4%
10. agent-harnes   9c 10,028  514.9M  9.71M   68.0M  $132.2   3.6%
11. scratch-prot   8c  7,797  350.8M  6.62M   46.3M  $110.1   2.8%
12. container-gi   4c  4,995  247.0M  4.66M   32.6M   $69.3   1.8%
13. telemetry-in   2c  2,069  150.5M  2.84M   19.9M   $46.0   0.7%
14. astro-sky-ma   1c  1,126    294k   5.5k     39k   $0.02   0.4%
15. rf-dsp-modem   0c    609   34.6M   653k   4.57M   $4.37   0.2%
16. civic-map-en   1c    177    6.9M   131k    915k   $1.74   0.1%
────────────────────────────────────────────────────────────────────────
SUBAGENTS (15)    RUNS  STEPS    TOK   TOK/D   TOK/WK   EST.$  SHARE
1. argon-sentine 144r 26,626    1.3B  24.4M  171.1M  $466.6  27.5%
2. flash-surgeon 158r 26,330  372.9M  7.04M   49.3M   $51.6  27.2%
3. flash-auditor 204r 16,100  426.4M  8.04M   56.3M   $65.9  16.7%
4. research       86r 10,277  447.3M  8.44M   59.1M  $164.9  10.6%
5. argon-surgeon  14r  8,282  527.2M  9.95M   69.6M  $122.9   8.6%
6. flash-scout    68r  6,290  159.9M  3.02M   21.1M   $24.9   6.5%
7. claude-sentin  23r  1,981  100.4M  1.89M   13.3M   $38.1   2.0%
8. neon-surgeon    1r    245   30.3M   572k   4.00M   $9.59   0.3%
9. v960-argon-se   1r    160    5.1M    97k    679k   $2.27   0.2%
10. argon-archit   2r    132    3.8M    73k    508k   $1.79   0.1%
11. hydrogen-sur   2r    105    2.2M    41k    289k   $1.13   0.1%
12. carbon-senti   1r     60    3.0M    56k    394k   $1.35   0.1%
13. flash-doc-su   1r     38    251k   4.7k     33k   $0.12   0.0%
14. claude-speci   1r     31   11.8k    222    1.6k   $0.00   0.0%
15. SCL-flash-au   1r     18    341k   6.4k     45k   $0.10   0.0%
════════════════════════════════════════════════════════════════════════
```

### 2. `style="quick"` (40-Column Mobile Layout)

```text
════════════════════════════════════════
AGY-NEXUS v4.0.8 // 91d (Nov 24 ◄── Aug 
════════════════════════════════════════
G-20x: 100% [████████┼█] OK | 0x 429s
P-1x : 100% [░┼░░░░░░░░] OK | 71% WkLft
Steps:276.5k | Tools:145.5k | Act:53d
Burn:13.6B | $3,410 | 257.1M/d
Health: Poly 2630s | 88/88 <=500L | up_t
────────────────────────────────────────
HEATMAP (NOW ──► 13w Ago)  │ PEAK & VOL
Mo ██▒▒▓░░·░····           │ Pk: 11/22
Tu ▓█▓▒▒░░··░···           │ 20,915 stp
We ·█▓▓▒·░·░░···           │ Avg:5,217/d
Th ·█▒▒▒░░··▒···           │ Cost: $3,41
Fr ·██▓▒▓░·▒▓···           │ Subs : 707r
Sa ·████▓░·▓▒···           │ Tok/d:257.1
Su ·███▓▓▒·▓····           │ Tok/w:1.80B
────────────────────────────────────────
8H PACE & STACK (NOW──►OLD) Pk:1.9k
1.9k╷ █                              
 936┤ █                              
 433┼▄█▄─────▄───────────────────────
   0╵███     ▓  ▄   ░░ ▄      ▄   ▄  
────────────────────────────────────────
MODEL   [PIN]    PCT   TOK  EST.$   DLT
Carbon4 [█┼░░░░░░] 13%  3.9B $1,030  -7
Neon 4  [░┼░░░░░░]  0% 30.2M  $9.59 -10
Argon 4 [██┼█░░░░] 46%  8.5B $2,178 +21
Hydro 4 [░┼░░░░░░]  0%  2.2M  $1.13 -15
Flash38 [█┼█▓░░░░] 41%  1.0B $153.7 +21
Opus5.5 [▏░░░░░░░]  0%     0  $0.00  -3
Sonn5.5 [▏░░░░░░░]  0% 99.2M  $38.1  -5
GPT-120 [▏░░░░░░░]  0%     0  $0.00  -2
────────────────────────────────────────
WORKSPACES & SUBS  TOK   EST.$  TOK/WK
stem-curriculum  3.6B  $905.9  477.2M
mail-triage-ui   2.1B  $448.0  282.6M
home-telemetry-  2.0B  $492.6  264.7M
quiet-ui-skills  1.7B  $472.7  222.2M
task-queue-engi 346.9M   $96.3   45.8M
agy-nexus-mcp    1.5B  $398.0  200.2M
*argon-sentinel  1.3B  $466.6  171.1M
*flash-surgeon  372.9M   $51.6   49.3M
*flash-auditor  426.4M   $65.9   56.3M
════════════════════════════════════════
```

### 3. `style="rich"` (76-Column Widescreen Layout)

```text
╔══════════════════════════════════════════════════════════════════════════╗
║ ▄▀█ █▀▀ █▄█ ▄▄ █▄░█ █▀▀ ▀▄▀ █░█ █▀   v4.0.8 // RICH TELEMETRY RIG        ║
║ █▀█ █▄█ ░█░ ░░ █░▀█ ██▄ █░█ █▄█ ▄█   WINDOW: 91d (Nov 24 ◄── Aug 26)     ║
╠════════════════════════════════════╦═════════════════════════════════════╣
║ QUOTA POOLS & 429 COOLDOWNS        │ STEP & TOOL VELOCITY                ║
║ G-20x:  99.5% [████████┼█] OK      │ Total : 276,515 steps | 145,540 too ║
║ P-1x :  99.5% [░┼░░░░░░░░] OK      │ Active: 5,217 s/act-d (53d active)  ║
║ 429s : 0 events | 71.4% Wk Left    │ Calend: 3,038 s/cal-d (216c, 707r)  ║
╠════════════════════════════════════╬═════════════════════════════════════╣
║ TOKEN BURN & API COST LEDGER       │ MCP WIRE & CLIENT SURFACES          ║
║ Total : ~13.6B | $3,409.82         │ Wire  : 99% <20KB (avg 12.0/26.4KB) ║
║ Daily : 257.1M/d ($64.34/d)        │ Calls : 112 MCP reqs (370k tok)     ║
║ NextRt: $6,770.82 API Forecast     │ Client: Web 77% · Prx 23% · Mob 0%  ║
╠════════════════════════════════════╦═════════════════════════════════════╣
║ VERSION & RELEASE STATUS           │ POLYGLOT & MODULAR CODE HEALTH      ║
║ Installed: v4.0.8 (up_to_date)     │ Poly: 2630s | 88/88 <=500L 0>650L   ║
║ Remote   : v4.0.8                  │ IDE MCP  : agy-praxis-mcp + Serena  ║
╠════════════════════════════════════╩═════════════════════════════════════╣
║ DAILY ACTIVITY MATRIX (NOW: W01 ──► W13)     [·· 0  ░░ <1k  ▒▒ <4k  ██]  ║
║ Wk   W01 W02 W03 W04 W05 W06 W07 W08 W09 W10 W11 W12 W13  ┌─ PEAK DAY ─┐ ║
║ Mon  ███ ███ ▒▒▒ ▒▒▒ ▓▓▓ ░░░ ░░░ ··· ░░░ ··· ··· ··· ···  │ Nov 22     │ ║
║ Tue  ▓▓▓ ███ ▓▓▓ ▒▒▒ ▒▒▒ ░░░ ░░░ ··· ··· ░░░ ··· ··· ···  │ 20,915 stp │ ║
║ Wed  ··· ███ ▓▓▓ ▓▓▓ ▒▒▒ ··· ░░░ ··· ░░░ ░░░ ··· ··· ···  ├────────────┤ ║
║ Thu  ··· ███ ▒▒▒ ▒▒▒ ▒▒▒ ░░░ ░░░ ··· ··· ▒▒▒ ··· ··· ···  │ Act: 53d   │ ║
║ Fri  ··· ███ ███ ▓▓▓ ▒▒▒ ▓▓▓ ░░░ ··· ▒▒▒ ▓▓▓ ··· ··· ···  │ Avg:  5.2k │ ║
║ Sat  ··· ███ ███ ███ ███ ▓▓▓ ░░░ ··· ▓▓▓ ▒▒▒ ··· ··· ···  │ Sub: 707r  │ ║
║ Sun  ··· ███ ███ ███ ▓▓▓ ▓▓▓ ▒▒▒ ··· ▓▓▓ ··· ··· ··· ···  └────────────┘ ║
║ Vol  ▂▂▂ ███ ▄▄▄ ▃▃▃ ▃▃▃ ▂▂▂ ▁▁▁ ─── ▁▁▁ ▁▁▁ ─── ─── ───  PeakWk:83.6k   ║
║ Steps 19k 84k 53k 35k 31k 19k  7k  ·  16k 12k  ·   ·   ·                 ║
╠══════════════════════════════════════════════════════════════════════════╣
║ 8H SUB-DAILY HORIZON CURVE & PROJECT STACK (NOW ──► SEP 21)              ║
║ 1.9k ╷  █                                                                ║
║ 1.5k ┤  █                                                                ║
║ 1.0k ┤  █                                                                ║
║  411 ┼▄ █  ▄▄█                     ▄ ▄                                   ║
║  336 ┤███──███──────────▄─────▄───▄█─█───────────────────▄────────────   ║
║    0 ╵███░░███▄         █ ▄   ▒▒ ░▒▒ ░  ▄   ▄           ▄░▄     ▄        ║
║      └─▲───────────▲───────────▲───────────▲───────────▲───────────▲───  ║
║       Nov 24      Nov 11      Oct 28      Oct 15      Oct 02      Sep 21 ║
║       Stack: [█]stem-curricu(22%)  [▓]mail-triage-(12%)  [▒]home-telemet ║
╠══════════════════════════════════════════════════════════════════════════╣
║ MODEL       [QUOTA ┼ TARGET] SHARE    CALLS     TOK    EST.$  DLT  STAT  ║
║ Carbon 4    [██▓┼░░░░░░░░░░] 13.0%  16,330    3.9B  $1,030   -7% OK      ║
║ Neon 4      [░┼░░░░░░░░░░░░]  0.1%     103   30.2M   $9.59  -10% OK      ║
║ Argon 4     [███┼██▓░░░░░░░] 45.6%  57,179    8.5B  $2,178  +21% WRN     ║
║ Hydrogen 4  [░░┼░░░░░░░░░░░]  0.0%      34    2.2M   $1.13  -15% WRN     ║
║ Flash 3.8   [███┼██▓░░░░░░░] 40.8%  51,192    1.0B  $153.7  +21% WRN     ║
║ Opus 5.5    [▏░░░░░░░░░░░░░]  0.0%       0       0   $0.00   -3% OK      ║
║ Sonnet 5.5  [░┼░░░░░░░░░░░░]  0.4%     555   99.2M   $38.1   -5% OK      ║
║ GPT-OSS 120 [▏░░░░░░░░░░░░░]  0.0%       0       0   $0.00   -2% OK      ║
║ BILLING CMP: Hist $3,410 | NextRate $6,771 (+99%) | 20x 5.6x             ║
╠══════════════════════════════════════════════════════════════════════════╣
║ WORKSPACES (16)  CHATS   STEPS     TOK   TOK/D   EST.$ SHARE GAUGE       ║
║ 1. stem-curricul  72c  60,790    3.6B  68.2M  $905.9 █▍░░░░ 22.0%        ║
║ 2. mail-triage-u  31c  32,207    2.1B  40.4M  $448.0 ▍░░░░░ 11.6%        ║
║ 3. home-telemetr   4c  31,912    2.0B  37.8M  $492.6 ▍░░░░░ 11.5%        ║
║ 4. quiet-ui-skil  37c  27,638    1.7B  31.7M  $472.7 ▍░░░░░ 10.0%        ║
║ 5. task-queue-en   1c  25,933  346.9M  6.55M   $96.3 ▍░░░░░  9.4%        ║
║ 6. agy-nexus-mcp  30c  23,111    1.5B  28.6M  $398.0 ▍░░░░░  8.4%        ║
║ 7. net-topology-   6c  20,803  955.2M  18.0M  $219.2 ▍░░░░░  7.5%        ║
║ 8. cloud-gitops-   4c  15,070   52.7M   995k   $11.9 ▍░░░░░  5.4%        ║
║ 9. edge-iot-cont   6c  12,250    9.5M   179k   $1.51 ▍░░░░░  4.4%        ║
║ 10. agent-harnes   9c  10,028  514.9M  9.71M  $132.2 ░░░░░░  3.6%        ║
║ 11. scratch-prot   8c   7,797  350.8M  6.62M  $110.1 ░░░░░░  2.8%        ║
║ 12. container-gi   4c   4,995  247.0M  4.66M   $69.3 ░░░░░░  1.8%        ║
║ 13. telemetry-in   2c   2,069  150.5M  2.84M   $46.0 ░░░░░░  0.7%        ║
║ 14. astro-sky-ma   1c   1,126    294k   5.5k   $0.02 ░░░░░░  0.4%        ║
║ 15. rf-dsp-modem   0c     609   34.6M   653k   $4.37 ░░░░░░  0.2%        ║
║ 16. civic-map-en   1c     177    6.9M   131k   $1.74 ░░░░░░  0.1%        ║
╟──────────────────────────────────────────────────────────────────────────╢
║ SUBAGENTS (15)    RUNS   STEPS     TOK   TOK/D   EST.$ SHARE GAUGE       ║
║ 1. argon-sentine 144r  26,626    1.3B  24.4M  $466.6 █▍░░░░ 27.5%        ║
║ 2. flash-surgeon 158r  26,330  372.9M  7.04M   $51.6 █▍░░░░ 27.2%        ║
║ 3. flash-auditor 204r  16,100  426.4M  8.04M   $65.9 █░░░░░ 16.7%        ║
║ 4. research       86r  10,277  447.3M  8.44M  $164.9 ▍░░░░░ 10.6%        ║
║ 5. argon-surgeon  14r   8,282  527.2M  9.95M  $122.9 ▍░░░░░  8.6%        ║
║ 6. flash-scout    68r   6,290  159.9M  3.02M   $24.9 ▍░░░░░  6.5%        ║
║ 7. claude-sentin  23r   1,981  100.4M  1.89M   $38.1 ░░░░░░  2.0%        ║
║ 8. neon-surgeon    1r     245   30.3M   572k   $9.59 ░░░░░░  0.3%        ║
║ 9. v960-argon-se   1r     160    5.1M    97k   $2.27 ░░░░░░  0.2%        ║
║ 10. argon-archit   2r     132    3.8M    73k   $1.79 ░░░░░░  0.1%        ║
║ 11. hydrogen-sur   2r     105    2.2M    41k   $1.13 ░░░░░░  0.1%        ║
║ 12. carbon-senti   1r      60    3.0M    56k   $1.35 ░░░░░░  0.1%        ║
║ 13. flash-doc-su   1r      38    251k   4.7k   $0.12 ░░░░░░  0.0%        ║
║ 14. claude-speci   1r      31   11.8k    222   $0.00 ░░░░░░  0.0%        ║
║ 15. SCL-flash-au   1r      18    341k   6.4k   $0.10 ░░░░░░  0.0%        ║
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

| Feature | Typical Community Bridges (`agy-bridge`, `meridian`, `ag-local-bridge`) | `agy-nexus-mcp` (`v4.0.8`) |
| :--- | :--- | :--- |
| **Connection Architecture** | Local `stdio` pipe or single-chat Telegram/WhatsApp bot | **Dual-Doorway Streamable HTTP + Zero-Stdout `--stdio` OCI Container** (`agy-nexus-mcp` for Gemini Web/Mobile/Tasks & MCP Registry + LAN-only `agy-praxis-mcp` for local Antigravity IDE) |
| **Zero-Trust Security** | None or static chat-ID allowlist | **5-Layer Defense**: Secret URL Path + Voice/Text Deadbolt (`64`-hex `PASS_HASH`) + LAN-Only Praxis Gate + Sandboxed ZIP/File Readers + HMAC Host Bridge |
| **Parallel Isolation & Routing** | Single active chat; parallel tabs overwrite state | **Keyed Context Slots (`active_contexts` + Auto-Prune) + Fail-Closed 3-Pillar Resolver + `<repo-slug>-NN` Queue + Proportional Fast-Path** |
| **Session Lifecycle & Closeout** | Blind context overflows or manual chat juggling | **Strict Recency Sorting + Continuity-Aware Rollover + In-Place Closeout & `RETIRED.json` Tombstones + `@Agy Nexus Mcp` 1-Tap Chips** |
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

## Repository Layout (`v4.0.8`)

*(See [`AGENTS.md`](AGENTS.md) for the complete modular architecture reference.)*

```text
agy-nexus-mcp/
├── src/agy_nexus/        # Modular backend/MCP modules (<=500L target, 650L ceiling):
│                         #   model_pricing, cost_ledger, project_stats, ascii_{default,rich,models},
│                         #   config, hygiene, polyglot_*, handoff_*, tools_praxis, stats*, media*,
│                         #   bucket_*, web_routes, uploads, sessions, routing, target_resolver, server
├── ag_bridge.py          # Backward-compatible 75-line root entrypoint shim
├── Dockerfile & server.json  # GHCR OCI container (python:3.12-slim) & 2025-12-11 MCP Registry manifest
├── web/                  # Quiet UI v9.3.0 Studio PWA (primary /web + /web/v9 + offline vendored ECharts):
│                         #   index.html, manifest.webmanifest, sw.js, demo_snapshot.js, v9/* & v9/vendor/*
├── host_bridge/          # Loopback-only authenticated Host Companion (:8098), CreateProject & HMAC security
├── agents/ & skills/     # Synced 12-Agent Dual-Pool Roster & agy-nexus-stats SKILL.md
├── docs/                 # DEPLOYMENT.md, WORKFLOWS.md, QUIET_UI_V9_FIELD_REPORT.md & assets/ screenshots
├── scripts/              # setup, sync_agents, check_model_drift, export_depersonalized_showcase, build_github_showcase, publish_to_github
├── systemd/ & .github/   # 01:45 AM drift watchdog timer, OIDC publish-mcp.yml & issue/PR templates
├── tests/                # Pytest regression suites + conftest STATE_FILE isolation (v2.6 – v4.0.8)
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
