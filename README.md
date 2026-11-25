# `agy-nexus-mcp` — Connect Google Gemini to Your Antigravity IDE, 2-Pane Workspace & Usage Studio (`v4.0.9`)

<!-- mcp-name: io.github.FrankXLT/agy-nexus-mcp -->

`agy-nexus-mcp` is a self-hosted **Dual-Doorway Model Context Protocol (MCP)** server connecting **Google Gemini** (Web, Mobile & Tasks) directly to your local **Google Antigravity IDE / CLI** workstation—paired with **`agy-praxis-mcp`** (deadbolt-free LAN-only semantic codebase index & `<repo-slug>-NN` handoff inbox), a **Public GHCR OCI `--stdio` Container** (`ghcr.io/frankxlt/agy-nexus-mcp`) published to the Official MCP Registry, a **Versioned Two-File Price Book & Intended-vs-Actual Subagent Auditor**, and the **Quiet UI `v9.3.0` Studio PWA (`/web`)** featuring live **8-Model Micro-USD Analytics**, **Hybrid Range Whiskers & Target/Seam Caret Bars**, **Multi-Column Sortable Tables**, **Desktop Sidebar Pinning**, and a **2-Pane Session Workspace Explorer**.

> **[Try the Interactive Live Showcase (Real Workstation Telemetry, 0 Backend Required)](https://FrankXLT.github.io/agy-nexus-mcp/)**

---

## Live `/web` Unified Studio App (`Analytics` + 2-Pane `Workspace`)

### 1. `Analytics` — 8-Model Cost Ledger, Range Whiskers & `Mon–Sun` Calendar Matrix
![AGY-NEXUS v4.0.9 Analytics Surface — Quiet UI v9.3.0 Studio, 6-Window Presets, 8-Model Micro-USD Cost Ledger, Hybrid Range Whiskers & Target/Seam Caret Bars, Single-Hue 52-Week Mon–Sun Calendar Matrix, Sortable Tables & Code Health](docs/assets/dashboard-desktop.png)

### 2. `Workspace` — Responsive 2-Pane Session Explorer, Editorial Reader & Capture Gallery
![AGY-NEXUS v4.0.9 2-Pane Workspace Explorer — Recency Project Rail, Editorial Markdown Tabs, Inline Walkthrough Captures & Direct PNG / Per Sheet Gallery](docs/assets/workspace-desktop.png)

<details>
<summary><strong>📱 Mobile Layouts (<code>390px</code> Portrait — Analytics <code>26w</code> Matrix &amp; Clean Wrapped Workspace Tabs)</strong></summary>

![AGY-NEXUS v4.0.9 Mobile Analytics View](docs/assets/dashboard-mobile.png)
![AGY-NEXUS v4.0.9 Mobile Workspace View](docs/assets/workspace-mobile.png)

</details>

---

## Key Capabilities (`v4.0.9`)

- **Shared Two-File Price Book, 1-Click `/web` Overrides & `bot/catalog-sync` PRs**: Partitions `src/agy_nexus/data/model_catalog.json` (`catalog_revision`, `public_api` vs. locked `antigravity_ide`) and `src/agy_nexus/data/cost_ledger.json` (effective-dated `rate_epochs` with `source_url` / `verified_at`), compiles deterministic [`docs/PRICING_HISTORY.md`](docs/PRICING_HISTORY.md), surfaces 24h fail-open upstream update banners with native diff preview + `0600` `AGY_DATA_DIR/catalog_override.json` acceptance, and automates weekly fail-closed `bot/catalog-sync` PRs targeting protected `main`.
- **Intended-vs.-Actual Subagent Adjudication & Unmapped `M*` Alerts**: Cross-checks each subagent's `targetModel` against actual transcript execution (correctly catching `model: inherit` redirects when switching chat models) across `390px`/`900px`/`1440px` `/web` rows and `list_models_and_agents`, and alerts with a 1-click GitHub Issue URL whenever unknown `M*` barcodes appear (`CACHE_VERSION = 9`).
- **Public GHCR OCI Container, Zero-Stdout `--stdio` & MCP Registry OIDC**: One-click installation (`ghcr.io/frankxlt/agy-nexus-mcp:4.0.9` via `--stdio`) for VS Code, Copilot CLI, Claude Code, and MCP Inspector without `PATH_SECRET`—serving deadbolt-safe `list_models_and_agents(style="ascii")` immediately while keeping private workspace tools fail-closed unless a valid 64-hex `PASS_HASH` is configured, backed by `server.json` (`2025-12-11`) and Sigstore `cosign` + `github-oidc` CI publishing.
- **Dual-Doorway Parallel Isolation & `<repo-slug>-NN` Queue**: Concurrent Gemini Web/Mobile tabs work across separate repositories via `fcntl.flock` `active_contexts` slots (auto-pruning stale slots), 3-pillar fail-closed resolution (`target_resolver.py`), same-repo concurrent writer detection (`MAIN WRITER` / `WORKTREE` / `SHARED`), and atomic `<slug>-NN` handoffs (`handoff_queue.py`) with proportional **Surgical Fast-Path** vs. Full Dual-Review execution (`handoff_templates.py`).
- **8-Model Registry, Effective-Dated Cost Ledger & `01:45 AM` Drift Watchdog**: Tracks all 8 live models (`Gemini 4 Carbon`, `Neon`, `Argon`, `Hydrogen`, `Gemini 3.8 Flash`, `Claude Opus 5.5`, `Claude Sonnet 5.5`, `GPT-OSS 120B`) with immutable micro-USD epochs (`CACHE_VERSION = 9`, `cost_ledger.json`), deadbolt-safe `76`-col `models` ASCII status, `12`-subagent `sync_agents.py`, and read-only `01:45 AM` `agy-model-drift-check.timer`.
- **`agy-praxis-mcp` Local IDE Doorway (`6` Tools)**: Incremental SHA-256 Polyglot semantic indexing (`polyglot_map` strictly `<= 17.5 KB` with `directory_summary` + `drilldown_hint`, `polyglot_search`, `polyglot_outline`) + `<repo-slug>-NN` handoff queue (`/praxis/{PRAXIS_MCP_TOKEN}/mcp`, legacy `/polyglot/` alias, or `--stdio`) with strict LAN-only `403` proxy/Origin rejection.
- **Strict `< 20 KB` Wire Budget, `@Agy Nexus Mcp` 1-Tap Chips & In-Place Closeout**: Sequential Read-Only Governance (`<= 4` hops/turn), `tools/list` (`<= 8.6 KB`), `get_session_tree` (`<= 17.5 KB`), `<= 18.5 KB` inner / `<= 19.8 KB` escaped outer wire caps, `REPLY_PROMPT_GUIDANCE` + XML `followup_xml` 1-tap `<FollowUp>` / `<ElicitationsGroup>` reply chips prefixed with `@Agy Nexus Mcp ` across every tool, 5-tier context pressure (`FRESH` $\rightarrow$ `HARD_ROLLOVER`), `RETIRED.json` tombstones (`retire_after_closeout=True`), and `workflow:baseline`.
- **Quiet UI `v9.3.0` Studio (`/web`) & Public Interactive Showcase**: Direct `/web` live cutover (`/web/v9` compatible), offline vendored Apache ECharts, `[Steps | Tokens | $ Cost]`, **Option A Hybrid Range Whiskers & Target/Seam Caret Bars** (`Avg · Peak · 24h` project/subagent whiskers with `>120` step-cap alerts, model `Guide │ + 24h ▾`, session `320│ / 700▾` seams), multi-column sortable tables with preserved swatch colors, `>= 1100px` desktop sidebar pinning, `Activity by Hour of Day` active-day whiskers, `Subscription Break-Even`, responsive `< 760px` Docs + `[Captures (N)]` modal, and zero-leak **GitHub Pages Showcase** (`scripts/build_github_showcase.py`).

---

## Quick Setup & Everyday Prompts

1. **Initialize & Self-Test** *(or launch `--stdio` directly via Docker)*:
   ```bash
   docker run -i --rm ghcr.io/frankxlt/agy-nexus-mcp:4.0.9 --stdio
   # Or run locally from source:
   python3 ag_bridge.py --self-test && python3 -m agy_nexus.tools_praxis --self-test && pytest
   python3 ag_bridge.py   # or docker compose up -d (see docs/DEPLOYMENT.md)
   ```
2. **Connect Clients**:
   - **MCP Registry / Local IDE (`--stdio`)**: Install `io.github.FrankXLT/agy-nexus-mcp` from `github.com/mcp` (`ghcr.io/frankxlt/agy-nexus-mcp:4.0.9 --stdio`), optionally passing `PASS_HASH` to unlock private workspace tools.
   - **Gemini Web / Mobile / Tasks**: Add custom MCP `https://<your-domain>/{PATH_SECRET}/mcp` (voice/text unlock strips filler via `unlock_sessions`).
   - **Antigravity IDE (`agy-praxis-mcp`)**: Point `~/.gemini/config/mcp_config.json` to `http://<host>.lan:8765/praxis/<PRAXIS_MCP_TOKEN>/mcp`.
   - **Quiet UI Studio PWA (`/web`) & Public Demo**: Open `https://<your-domain>/web` (`?demo=1` for depersonalized preview) or explore the [Public GitHub Pages Showcase](https://FrankXLT.github.io/agy-nexus-mcp/).
3. **Example Prompts**: *"Unlock Antigravity with [phrase] and load `agy-nexus-mcp`"* · *"Show me my session tree"* · *"Show model & subagent status"* · *"Search `cloud-gitops-stack` for compose healthcheck rules"* · *"Stage this bugfix (`allow_chained_publish=False`)"* · *"Show me my latest usage stats (`default` / `quick` / `rich`)."*

## Project Manager Mode & Plain-Language Handoffs (`v4.0.9`)

`agy-nexus-mcp` turns Google Gemini into a grounded **Engineering Project Manager**: Gemini scouts live state sequentially (`<= 4` calls/turn), stages `<repo-slug>-NN` handoffs with proportional `execution_mode="auto"` ceremony (`allow_chained_publish=False` for preview gates with 7-day `/web/media/` screenshots), and guides **Job-First `"Yes"`** `@Agy Nexus Mcp` 1-tap chips (`followup_xml`) across `ready_to_run`, `in_flight`, `ready_to_ship` (`RETIRED.json` closeout), and `retired`.

| `handoff_mode` | Purpose & Behavior | Antigravity Execution |
| :--- | :--- | :--- |
| **`feature_update`** *(Default)* | Add features or refine workflows with `WORKFLOWS.md` baseline parity. | Full 4-Step (`flash-scout` $\rightarrow$ `surgeon` $\rightarrow$ `flash-auditor` $\rightarrow$ Dual-Review / Visual Gate; multi-deliverable/complex `fast` coerces to `plan`). |
| **`new_project`** | Stand up greenfield repos/packages (`create_new_project=True`, `<= 500L` modules). | Blueprinted via `argon-architect` (`plan` mode enforced), scaffolded modularly with `pytest` & self-tests. |
| **`bug_or_visual_fix`** | Pinpoint broken behavior, exact viewports (`390px`/`900px`/`1440px`), and fix criteria. | **Surgical Fast-Path** for compact non-security diffs (`fast`), or Full Dual-Review on auth/UI boundaries. |
| **`release_closeout`** | Verify tests, sync 3-2-1 backups, commit/tag/push, and write `RETIRED.json` tombstones. | Prunes worktrees, marks `<slug>-NN` tickets `COMPLETED`, defers `RETIRED.json` (`retire_after_closeout=True`) until push succeeds. |

## Copy-Ready 76-Column Project, Chat & Session Hierarchy (`get_session_tree`)
Call `get_session_tree()` (or `manage_background_run(action="sessions")`) to render a copy-ready 76-column ASCII hierarchy grouping every conversation and `<repo-slug>-NN` handoff with **untruncated** `project_id`, `session_id`, and `workspace` lines:

```text
╔══════════════════════════════════════════════════════════════════════════╗
║ AGY-NEXUS v4.0.9 // PROJECT -> CHAT -> SESSION ID HIERARCHY (COPY-READY) ║
╠══════════════════════════════════════════════════════════════════════════╣
║ SLOTS: 3 | STAGED: 0 | IN-WORK: 3 | PINNED: 24 | TTL: 119.5m             ║
║ 3-2-1 BACKUP: 41e7a2b (SYNCED ✓ · 22007.6 KB · 4h ago)                   ║
╚══════════════════════════════════════════════════════════════════════════╝

[PROJECT 1] Quiet UI Skills [SHARED REPO] [▶ 2 IN-WORK]
  project_id : 696506de-5df1-41da-9b5c-03c2e1b9128c
  workspaces : /home/dev/agentic_workspace/projects/quiet-ui-skills
  ├─ [HANDOFF quiet-ui-skills-62] Quiet UI v9.7.0 Wave 1.5 — Integrated Card-Bound Alarm Trace & Visual Polish
  │   pass_off   : [▶ IN-WORK] · plan/bug_or_visual_fix · 29m ago
  │   session_id : 2827d6f8-0e09-4dc9-b258-878044db081b
  ├─ [HANDOFF quiet-ui-skills-60] User Goal & Why
  │   pass_off   : [▶ IN-WORK] · fast/release_closeout · 4h ago
  │   session_id : bb01e6db-7615-4259-8a98-f96aa9b4025d
  ├─ (+16 older completed)
  ├─ [#1] Quiet UI v9.7.0 Wave 1.5 — Integrated Card-Bound Alarm Trace & Visual Polish
  │   session_id : 2827d6f8-0e09-4dc9-b258-878044db081b
  │   workspace  : /home/dev/agentic_workspace/projects/quiet-ui-skills
  │   status     : [● RUNNING] · MAIN WRITER · 311 steps · 4s ago
  ├─ [#3] Quiet UI v9.7.0 Wave 1 — Automated Alarm Lifecycle & Console Overhaul
  │   session_id : ede660d7-7b18-4c56-a867-0419aefb393f
  │   workspace  : /home/dev/agentic_workspace/projects/quiet-ui-skills
  │   status     : [◉ PINNED · IDLE] · SHARED (READ-ONLY) · 780 steps · 57m ago
  └─ [#9] Quiet UI v9.6.0 — Final Table Return Bar & Front-Door Micro-Polish
      session_id : bb01e6db-7615-4259-8a98-f96aa9b4025d
      workspace  : /home/dev/agentic_workspace/projects/quiet-ui-skills
      status     : [● RUNNING] · MAIN WRITER · 406 steps · 3h ago

[PROJECT 2] AGY Nexus MCP [SHARED REPO] [▶ 1 IN-WORK]
  project_id : f1378431-5b09-4545-a48c-ac5c67c04fd3
  workspaces : /home/dev/agentic_workspace/projects/agy-nexus-mcp
  ├─ [HANDOFF agy-nexus-mcp-62] AGY-Nexus MCP v4.0.9 Wave 5.2 (develop) — Pool Split Tug-of-War & Two-Line Quota Race Cards
  │   pass_off   : [▶ IN-WORK] · plan/feature_update · 18m ago
  │   session_id : c99ae480-06d7-45ec-9589-81141d8b6641
  ├─ [HANDOFF agy-nexus-mcp-61] AGY-Nexus MCP v4.0.9 Wave 5.1 (develop) — 3px Heatmap Gutters, Larger Cells & 1px Zigzag Divider
  │   pass_off   : [✓ COMPLETED] · fast/bug_or_visual_fix · 1h ago
  │   session_id : c99ae480-06d7-45ec-9589-81141d8b6641
  ├─ (+17 older completed)
  ├─ [#2] AGY-Nexus MCP v4.0.9 Wave 5.1 (develop) — 3px Heatmap Gutters, Larger Cells & 1px Zigzag Divider
  │   session_id : c99ae480-06d7-45ec-9589-81141d8b6641
  │   workspace  : /home/dev/agentic_workspace/projects/agy-nexus-mcp
  │   status     : [● RUNNING] · MAIN WRITER · 291 steps · 11s ago
  ├─ [#5] AGY-Nexus MCP v4.0.9 Wave 4 (develop) — Pricing Soak & Node 24 Actions
  │   session_id : 35f9b080-cc9f-41f0-8320-40426e7de7f7
  │   workspace  : /home/dev/agentic_workspace/projects/agy-nexus-mcp
  │   status     : [○ COMPLETED] · SHARED (READ-ONLY) · 865 steps · 2h ago
  └─ [#10] AGY-Nexus MCP v4.0.9 Wave 3 (develop) — PR/Data READMEs & Anti-Injection Schema Validator
      session_id : f21bdc4f-6fef-4b71-b75d-f174308e20d7
      workspace  : /home/dev/agentic_workspace/projects/agy-nexus-mcp
      status     : [● RUNNING] · MAIN WRITER · 504 steps · 11h ago

[PROJECT 3] SCL Biblical Research [SHARED REPO]
  project_id : 63524eb2-fb6e-4f0a-bbc8-9305ee26956a
  workspaces : /home/dev/agentic_workspace/projects/telemetry-ingestor
  ├─ [HANDOFF telemetry-ingestor-10] Phase 0.2b — Canvas-Aligned Study Bible, Cyclops Git Rows & 10-Viewport Polish
  │   pass_off   : [✓ COMPLETED] · plan/feature_update · 18m ago
  │   session_id : b7d7ad04-058a-4920-a69b-78c8ba242a03
  ├─ [HANDOFF telemetry-ingestor-09] Phase 0.2 v2 — Unified Two-Entry-Point SCL Workbench (Cyclops Git-Graph Timeline + Continuous Study Bible)
  │   pass_off   : [✓ COMPLETED] · plan/feature_update · 2h ago
  │   session_id : 16c2d90d-dfb4-4a0a-815e-ad99eff9c2ea
  ├─ (+7 older completed)
  ├─ [#4] Phase 0.2b — Canvas-Aligned Study Bible, Cyclops Git Rows & 10-Viewport Polish
  │   session_id : b7d7ad04-058a-4920-a69b-78c8ba242a03
  │   workspace  : /home/dev/agentic_workspace/projects/telemetry-ingestor
  │   status     : [◉ PINNED · IDLE] · MAIN TREE · 384 steps · 1h ago
  ├─ [#7] Phase 0.2 Option A — Interactive Cyclops & 4-Layer Study Guide Visual Showcase (9 Viewports)
  │   session_id : 16c2d90d-dfb4-4a0a-815e-ad99eff9c2ea
  │   workspace  : /home/dev/agentic_workspace/projects/telemetry-ingestor
  │   status     : [○ COMPLETED] · MAIN TREE · 725 steps · 2h ago
  └─ [#13] Phase 0.1 Spec-Hardening — Fix All 9 Murder-Board Drift & Schema Gaps (Zero App Code)
      session_id : 5924eced-c390-4bc4-8667-915812176385
      workspace  : /home/dev/agentic_workspace/projects/telemetry-ingestor
      status     : [○ COMPLETED] · MAIN TREE · 271 steps · 13h ago
```

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
AGY-NEXUS v4.0.9 // 91d (Nov 25 ◄── Aug ┆ Up to Date (v4.0.9)           
════════════════════════════════════════╪═══════════════════════════════
GOOGLE 20x : 100.0% [████████┼█] HEALTHY┆ 0x 429s | Ultra-20x (T:>=90%) 
PARTNER 1x : 100.0% [░┼░░░░░░░░] ON PACE┆ 57.2% Wk Left | Lim <=14.3%/d 
STEPS/TOOLS: 291,186s | 155,966t | 233c ┆ 5,392 s/act-d | 3,199 s/cal-d 
TOKEN BURN : ~14.6B | $3,669.38         ┆ 270.1M/d | $67.95/d (754r)    
MCP WIRE   : 95% <20KB (avg 10.9/43.5KB)┆ 140 req (417k tok) | Web+Praxi
CODE HEALTH: Poly 3048 syms | 92/94 <=50┆ 0 >650L | Praxis+Serena       
────────────────────────────────────────┴───────────────────────────────
DAILY HEATMAP (NOW: W01 ──► 22w AGO)   Peak: 11/22 (20,915s) | Act: 54d
Wk    01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22
Mon   ██ ██ ▒▒ ▒▒ ▓▓ ░░ ░░ ·· ░░ ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ··
Tue   ██ ██ ▓▓ ▒▒ ▒▒ ░░ ░░ ·· ·· ░░ ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ··
Wed   ▓▓ ██ ▓▓ ▓▓ ▒▒ ·· ░░ ·· ░░ ░░ ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ··
Thu   ·· ██ ▒▒ ▒▒ ▒▒ ░░ ░░ ·· ·· ▒▒ ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ··
Fri   ·· ██ ▓▓ ▓▓ ▒▒ ▓▓ ░░ ·· ▒▒ ▓▓ ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ··
Sat   ·· ██ ██ ██ ██ ▓▓ ░░ ·· ▓▓ ▒▒ ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ··
Sun   ·· ██ ██ ██ ▓▓ ▒▒ ▒▒ ·· ▓▓ ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ··
Vol   ▃▃ ██ ▄▄ ▃▃ ▃▃ ▂▂ ▁▁ ── ▁▁ ▁▁ ── ── ── ── ── ── ── ── ── ── ── ──
────────────────────────────────────────────────────────────────────────
8H SUB-DAILY PACE (NOW ──► SEP 21)   [Avg: 415/8h | Peak: 2.2k | ░▒▓█]
2.2k ╷       █                                                         
1.1k ┤       █                                                         
 415 ┼───█──▄██────▄──────────────────▄────────────────────────────────
   0 ╵▄▄██▄░████ ▄ ▒     █ ▄   ▒   ▒▄ ░  ▄                ░            
     └─▲────────────▲────────────▲────────────▲────────────▲──────────▲─
      Nov 25       Nov 12       Oct 29       Oct 16       Oct 03     Sep
      Stack: [█] stem-curricul (22%)  [▓] mail-triage-u (11%)  [▒] home-
────────────────────────────────────────────────────────────────────────
MODEL       [QUOTA ┼ TARGET] SHARE    CALLS     TOK    EST.$  DLT  STAT
Carbon 4    [██▓┼░░░░░░░░░░] 15.6%  20,106    4.9B  $1,286   -4% OK  
Neon 4      [░┼░░░░░░░░░░░░]  0.1%     103   30.2M   $9.59  -10% OK  
Argon 4     [███┼██▓░░░░░░░] 44.5%  57,526    8.5B  $2,214  +20% WARN
Hydrogen 4  [░░┼░░░░░░░░░░░]  0.0%      34    2.2M   $1.13  -15% WARN
Flash 3.8   [███┼██░░░░░░░░] 39.8%  51,479    1.1B  $159.0  +20% WARN
Opus 5.5    [▏░░░░░░░░░░░░░]  0.0%       0       0   $0.00   -3% OK  
Sonnet 5.5  [░┼░░░░░░░░░░░░]  0.0%       0       0   $0.00   -5% OK  
GPT-OSS 120 [▏░░░░░░░░░░░░░]  0.0%       0       0   $0.00   -2% OK  
BILLING    Hist:$3,669 API | NextRate:$7,328 (+100%) | 20x:6.0x
────────────────────────────────────────────────────────────────────────
WORKSPACES (17)  CHATS  STEPS    TOK   TOK/D   TOK/WK   EST.$  SHARE
1. stem-curricul  74c 64,593    3.8B  71.0M  496.8M  $972.8  22.2%
2. mail-triage-u  32c 33,022    2.2B  40.6M  284.0M  $461.5  11.3%
3. home-telemetr   4c 32,146    2.0B  37.4M  261.9M  $493.6  11.0%
4. quiet-ui-skil  42c 31,497    2.0B  36.4M  254.6M  $538.0  10.8%
5. agy-nexus-mcp  35c 26,776    1.8B  32.7M  229.0M  $463.7   9.2%
6. task-queue-en   1c 25,933  346.9M  6.42M   45.0M   $96.3   8.9%
7. net-topology-   6c 20,803  955.2M  17.7M  123.8M  $219.2   7.1%
8. cloud-gitops-   4c 15,070   52.7M   976k   6.83M   $11.9   5.2%
9. edge-iot-cont   6c 12,250    9.5M   175k   1.23M   $1.51   4.2%
10. agent-harnes   9c 10,028  514.9M  9.53M   66.7M  $132.2   3.4%
11. scratch-prot   8c  7,797  350.8M  6.50M   45.5M  $110.1   2.7%
12. container-gi   4c  4,995  247.0M  4.57M   32.0M   $69.3   1.7%
13. telemetry-in   4c  2,295  141.9M  2.63M   18.4M   $47.1   0.8%
14. edge-proxy-r   2c  2,069  150.5M  2.79M   19.5M   $46.0   0.7%
15. astro-sky-ma   1c  1,126    294k   5.4k     38k   $0.02   0.4%
16. rf-dsp-modem   0c    609   34.6M   641k   4.48M   $4.37   0.2%
17. civic-map-en   1c    177    6.9M   128k    898k   $1.74   0.1%
────────────────────────────────────────────────────────────────────────
SUBAGENTS (22)    RUNS  STEPS    TOK   TOK/D   TOK/WK   EST.$  SHARE
1. argon-sentine 157r 28,472    1.4B  25.7M  179.8M  $501.8  28.3%
2. flash-surgeon 159r 26,331  372.9M  6.91M   48.3M   $51.6  26.2%
3. flash-auditor 211r 16,144  430.3M  7.97M   55.8M   $66.5  16.0%
4. research       94r 11,091  494.5M  9.16M   64.1M  $182.9  11.0%
5. argon-surgeon  14r  8,282  527.2M  9.76M   68.3M  $122.9   8.2%
6. flash-scout    70r  6,292  159.9M  2.96M   20.7M   $24.9   6.3%
7. claude-sentin  29r  2,555  126.4M  2.34M   16.4M   $51.2   2.5%
8. sprint19-sent   4r    370   10.2M   189k   1.32M   $5.08   0.4%
9. neon-surgeon    1r    245   30.3M   561k   3.93M   $9.59   0.2%
10. v960-argon-s   1r    160    5.1M    95k    667k   $2.27   0.2%
11. argon-archit   2r    132    3.8M    71k    499k   $1.79   0.1%
12. hydrogen-sur   2r    105    2.2M    40k    283k   $1.13   0.1%
13. wave1-argon-   1r    103    3.7M    69k    480k   $1.81   0.1%
14. security-sen   1r     87    3.4M    64k    447k   $1.56   0.1%
15. carbon-senti   1r     60    3.0M    55k    387k   $1.35   0.1%
16. diff-auditor   1r     51    2.3M    42k    292k   $1.02   0.1%
17. flash-doc-su   1r     38    251k   4.6k     33k   $0.12   0.0%
18. claude-speci   1r     31   11.8k    218    1.5k   $0.00   0.0%
19. wave4-audito   1r     26    216k   4.0k     28k   $0.14   0.0%
20. SCL-flash-au   1r     18    341k   6.3k     44k   $0.10   0.0%
21. self           1r     12    148k   2.7k     19k   $0.11   0.0%
22. hygiene-audi   1r      4   18.1k    336    2.4k   $0.04   0.0%
════════════════════════════════════════════════════════════════════════
```

### 2. `style="quick"` (40-Column Mobile Layout)

```text
════════════════════════════════════════
AGY-NEXUS v4.0.9 // 91d (Nov 25 ◄── Aug 
════════════════════════════════════════
G-20x: 100% [████████┼█] OK | 0x 429s
P-1x : 100% [░┼░░░░░░░░] OK | 57% WkLft
Steps:291.2k | Tools:156.0k | Act:54d
Burn:14.6B | $3,669 | 270.1M/d
Health: Poly 3048s | 92/94 <=500L | up_t
────────────────────────────────────────
HEATMAP (NOW ──► 13w Ago)  │ PEAK & VOL
Mo ██▒▒▓░░·░····           │ Pk: 11/22
Tu ██▓▒▒░░··░···           │ 20,915 stp
We ▓█▓▓▒·░·░░···           │ Avg:5,392/d
Th ·█▒▒▒░░··▒···           │ Cost: $3,66
Fr ·█▓▓▒▓░·▒▓···           │ Subs : 754r
Sa ·████▓░·▓▒···           │ Tok/d:270.1
Su ·███▓▒▒·▓····           │ Tok/w:1.89B
────────────────────────────────────────
8H PACE & STACK (NOW──►OLD) Pk:1.3k
1.3k╷ █  █                           
 634┤ █  █▄                          
 397┼─█──███────▄█────────────▄──────
   0╵░█  █▓▓▄▄██░▒  ▄  ▄      ░      
────────────────────────────────────────
MODEL   [PIN]    PCT   TOK  EST.$   DLT
Carbon4 [█┼░░░░░░] 16%  4.9B $1,286  -4
Neon 4  [░┼░░░░░░]  0% 30.2M  $9.59 -10
Argon 4 [██┼█░░░░] 44%  8.5B $2,214 +20
Hydro 4 [░┼░░░░░░]  0%  2.2M  $1.13 -15
Flash38 [█┼█▓░░░░] 40%  1.1B $159.0 +20
Opus5.5 [▏░░░░░░░]  0%     0  $0.00  -3
Sonn5.5 [▏░░░░░░░]  0%     0  $0.00  -5
GPT-120 [▏░░░░░░░]  0%     0  $0.00  -2
────────────────────────────────────────
WORKSPACES & SUBS  TOK   EST.$  TOK/WK
stem-curriculum  3.8B  $972.8  496.8M
mail-triage-ui   2.2B  $461.5  284.0M
home-telemetry-  2.0B  $493.6  261.9M
quiet-ui-skills  2.0B  $538.0  254.6M
agy-nexus-mcp    1.8B  $463.7  229.0M
task-queue-engi 346.9M   $96.3   45.0M
*argon-sentinel  1.4B  $501.8  179.8M
*flash-surgeon  372.9M   $51.6   48.3M
*flash-auditor  430.3M   $66.5   55.8M
════════════════════════════════════════
```

### 3. `style="rich"` (76-Column Widescreen Layout)

```text
╔══════════════════════════════════════════════════════════════════════════╗
║ ▄▀█ █▀▀ █▄█ ▄▄ █▄░█ █▀▀ ▀▄▀ █░█ █▀   v4.0.9 // RICH TELEMETRY RIG        ║
║ █▀█ █▄█ ░█░ ░░ █░▀█ ██▄ █░█ █▄█ ▄█   WINDOW: 91d (Nov 25 ◄── Aug 27)     ║
╠════════════════════════════════════╦═════════════════════════════════════╣
║ QUOTA PACING & POOL SPLIT          │ STEP & TOOL VELOCITY                ║
║ G 5h: 26/c75[██░░┼░] 1h14 OK       │ Total : 291,186 steps | 155,966 too ║
║ G Wk: 50/c26[█┼█▓░░] 5d4h HOT      │ Active: 5,392 s/act-d (54d active)  ║
║ Split:100/0 T90/10 P:Stby 429:0    │ Calend: 3,199 s/cal-d (233c, 754r)  ║
╠════════════════════════════════════╬═════════════════════════════════════╣
║ TOKEN BURN & API COST LEDGER       │ MCP WIRE & CLIENT SURFACES          ║
║ Total : ~14.6B | $3,669.38         │ Wire  : 95% <20KB (avg 10.9/43.5KB) ║
║ Daily : 270.1M/d ($67.95/d)        │ Calls : 140 MCP reqs (417k tok)     ║
║ NextRt: $7,328.04 API Forecast     │ Client: Web 55% · Prx 45% · Mob 0%  ║
╠════════════════════════════════════╦═════════════════════════════════════╣
║ VERSION & RELEASE STATUS           │ POLYGLOT & MODULAR CODE HEALTH      ║
║ Installed: v4.0.9 (up_to_date)     │ Poly: 3048s | 92/94 <=500L 0>650L   ║
║ Remote   : v4.0.9                  │ IDE MCP  : agy-praxis-mcp + Serena  ║
╠════════════════════════════════════╩═════════════════════════════════════╣
║ DAILY ACTIVITY MATRIX (NOW: W01 ──► W13)     [·· 0  ░░ <1k  ▒▒ <4k  ██]  ║
║ Wk   W01 W02 W03 W04 W05 W06 W07 W08 W09 W10 W11 W12 W13  ┌─ PEAK DAY ─┐ ║
║ Mon  ███ ███ ▒▒▒ ▒▒▒ ▓▓▓ ░░░ ░░░ ··· ░░░ ··· ··· ··· ···  │ Nov 22     │ ║
║ Tue  ███ ███ ▓▓▓ ▒▒▒ ▒▒▒ ░░░ ░░░ ··· ··· ░░░ ··· ··· ···  │ 20,915 stp │ ║
║ Wed  ▓▓▓ ███ ▓▓▓ ▓▓▓ ▒▒▒ ··· ░░░ ··· ░░░ ░░░ ··· ··· ···  ├────────────┤ ║
║ Thu  ··· ███ ▒▒▒ ▒▒▒ ▒▒▒ ░░░ ░░░ ··· ··· ▒▒▒ ··· ··· ···  │ Act: 54d   │ ║
║ Fri  ··· ███ ▓▓▓ ▓▓▓ ▒▒▒ ▓▓▓ ░░░ ··· ▒▒▒ ▓▓▓ ··· ··· ···  │ Avg:  5.4k │ ║
║ Sat  ··· ███ ███ ███ ███ ▓▓▓ ░░░ ··· ▓▓▓ ▒▒▒ ··· ··· ···  │ Sub: 754r  │ ║
║ Sun  ··· ███ ███ ███ ▓▓▓ ▒▒▒ ▒▒▒ ··· ▓▓▓ ··· ··· ··· ···  └────────────┘ ║
║ Vol  ▃▃▃ ███ ▄▄▄ ▃▃▃ ▃▃▃ ▂▂▂ ▁▁▁ ─── ▁▁▁ ▁▁▁ ─── ─── ───  PeakWk:83.6k   ║
║ Steps 33k 84k 53k 35k 31k 19k  7k  ·  16k 12k  ·   ·   ·                 ║
╠══════════════════════════════════════════════════════════════════════════╣
║ 8H SUB-DAILY HORIZON CURVE & PROJECT STACK (NOW ──► SEP 21)              ║
║ 1.9k ╷   █                                                               ║
║ 1.5k ┤   █                                                               ║
║ 1.0k ┤   █                                                               ║
║  373 ┼   █                    █                                          ║
║  336 ┤──██─██───▄─────▄█──────█──────▄▄─────────────────▄─────────────   ║
║    0 ╵░███ ██   ▓     ▓▓▄ ▒  ░▒     ▄░░░   ▄            ░░      ░▄       ║
║      └─▲───────────▲───────────▲───────────▲───────────▲───────────▲───  ║
║       Nov 25      Nov 11      Oct 29      Oct 15      Oct 02      Sep 21 ║
║       Stack: [█]stem-curricu(22%)  [▓]mail-triage-(11%)  [▒]home-telemet ║
╠══════════════════════════════════════════════════════════════════════════╣
║ MODEL       [QUOTA ┼ TARGET] SHARE    CALLS     TOK    EST.$  DLT  STAT  ║
║ Carbon 4    [██▓┼░░░░░░░░░░] 15.6%  20,106    4.9B  $1,286   -4% OK      ║
║ Neon 4      [░┼░░░░░░░░░░░░]  0.1%     103   30.2M   $9.59  -10% OK      ║
║ Argon 4     [███┼██▓░░░░░░░] 44.5%  57,526    8.5B  $2,214  +20% WRN     ║
║ Hydrogen 4  [░░┼░░░░░░░░░░░]  0.0%      34    2.2M   $1.13  -15% WRN     ║
║ Flash 3.8   [███┼██░░░░░░░░] 39.8%  51,479    1.1B  $159.0  +20% WRN     ║
║ Opus 5.5    [▏░░░░░░░░░░░░░]  0.0%       0       0   $0.00   -3% OK      ║
║ Sonnet 5.5  [░┼░░░░░░░░░░░░]  0.0%       0       0   $0.00   -5% OK      ║
║ GPT-OSS 120 [▏░░░░░░░░░░░░░]  0.0%       0       0   $0.00   -2% OK      ║
║ BILLING CMP: Hist $3,669 | NextRate $7,328 (+100%) | 20x 6.0x            ║
╠══════════════════════════════════════════════════════════════════════════╣
║ WORKSPACES (17)  CHATS   STEPS     TOK   TOK/D   EST.$ SHARE GAUGE       ║
║ 1. stem-curricul  74c  64,593    3.8B  71.0M  $972.8 █▍░░░░ 22.2%        ║
║ 2. mail-triage-u  32c  33,022    2.2B  40.6M  $461.5 ▍░░░░░ 11.3%        ║
║ 3. home-telemetr   4c  32,146    2.0B  37.4M  $493.6 ▍░░░░░ 11.0%        ║
║ 4. quiet-ui-skil  42c  31,497    2.0B  36.4M  $538.0 ▍░░░░░ 10.8%        ║
║ 5. agy-nexus-mcp  35c  26,776    1.8B  32.7M  $463.7 ▍░░░░░  9.2%        ║
║ 6. task-queue-en   1c  25,933  346.9M  6.42M   $96.3 ▍░░░░░  8.9%        ║
║ 7. net-topology-   6c  20,803  955.2M  17.7M  $219.2 ▍░░░░░  7.1%        ║
║ 8. cloud-gitops-   4c  15,070   52.7M   976k   $11.9 ▍░░░░░  5.2%        ║
║ 9. edge-iot-cont   6c  12,250    9.5M   175k   $1.51 ▍░░░░░  4.2%        ║
║ 10. agent-harnes   9c  10,028  514.9M  9.53M  $132.2 ░░░░░░  3.4%        ║
║ 11. scratch-prot   8c   7,797  350.8M  6.50M  $110.1 ░░░░░░  2.7%        ║
║ 12. container-gi   4c   4,995  247.0M  4.57M   $69.3 ░░░░░░  1.7%        ║
║ 13. telemetry-in   4c   2,295  141.9M  2.63M   $47.1 ░░░░░░  0.8%        ║
║ 14. edge-proxy-r   2c   2,069  150.5M  2.79M   $46.0 ░░░░░░  0.7%        ║
║ 15. astro-sky-ma   1c   1,126    294k   5.4k   $0.02 ░░░░░░  0.4%        ║
║ 16. rf-dsp-modem   0c     609   34.6M   641k   $4.37 ░░░░░░  0.2%        ║
║ 17. civic-map-en   1c     177    6.9M   128k   $1.74 ░░░░░░  0.1%        ║
╟──────────────────────────────────────────────────────────────────────────╢
║ SUBAGENTS (22)    RUNS   STEPS     TOK   TOK/D   EST.$ SHARE GAUGE       ║
║ 1. argon-sentine 157r  28,472    1.4B  25.7M  $501.8 █▍░░░░ 28.3%        ║
║ 2. flash-surgeon 159r  26,331  372.9M  6.91M   $51.6 █▍░░░░ 26.2%        ║
║ 3. flash-auditor 211r  16,144  430.3M  7.97M   $66.5 ▍░░░░░ 16.0%        ║
║ 4. research       94r  11,091  494.5M  9.16M  $182.9 ▍░░░░░ 11.0%        ║
║ 5. argon-surgeon  14r   8,282  527.2M  9.76M  $122.9 ▍░░░░░  8.2%        ║
║ 6. flash-scout    70r   6,292  159.9M  2.96M   $24.9 ▍░░░░░  6.3%        ║
║ 7. claude-sentin  29r   2,555  126.4M  2.34M   $51.2 ░░░░░░  2.5%        ║
║ 8. sprint19-sent   4r     370   10.2M   189k   $5.08 ░░░░░░  0.4%        ║
║ 9. neon-surgeon    1r     245   30.3M   561k   $9.59 ░░░░░░  0.2%        ║
║ 10. v960-argon-s   1r     160    5.1M    95k   $2.27 ░░░░░░  0.2%        ║
║ 11. argon-archit   2r     132    3.8M    71k   $1.79 ░░░░░░  0.1%        ║
║ 12. hydrogen-sur   2r     105    2.2M    40k   $1.13 ░░░░░░  0.1%        ║
║ 13. wave1-argon-   1r     103    3.7M    69k   $1.81 ░░░░░░  0.1%        ║
║ 14. security-sen   1r      87    3.4M    64k   $1.56 ░░░░░░  0.1%        ║
║ 15. carbon-senti   1r      60    3.0M    55k   $1.35 ░░░░░░  0.1%        ║
║ 16. diff-auditor   1r      51    2.3M    42k   $1.02 ░░░░░░  0.1%        ║
║ 17. flash-doc-su   1r      38    251k   4.6k   $0.12 ░░░░░░  0.0%        ║
║ 18. claude-speci   1r      31   11.8k    218   $0.00 ░░░░░░  0.0%        ║
║ 19. wave4-audito   1r      26    216k   4.0k   $0.14 ░░░░░░  0.0%        ║
║ 20. SCL-flash-au   1r      18    341k   6.3k   $0.10 ░░░░░░  0.0%        ║
║ 21. self           1r      12    148k   2.7k   $0.11 ░░░░░░  0.0%        ║
║ 22. hygiene-audi   1r       4   18.1k    336   $0.04 ░░░░░░  0.0%        ║
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

| Feature | Typical Community Bridges (`agy-bridge`, `meridian`, `ag-local-bridge`) | `agy-nexus-mcp` (`v4.0.9`) |
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
`agy-nexus-mcp` ships with the synced Dual-Pool subagent roster in [`agents/`](agents/) (`swarm-orchestrator`, `flash-scout`, `argon-architect`, `flash-surgeon`, `hydrogen-surgeon`, `neon-surgeon`, `argon-surgeon`, `flash-auditor`, `argon-sentinel`, `claude-specialist`, `claude-sentinel`, `pool-failover`) synced via `python3 scripts/sync_agents.py --apply` (check via `--check`). Subagent runs, `$ Est. Cost`, and `Avg Tok/Run` appear in `/web` and ASCII reports. See [`AGENTS.md`](AGENTS.md) and [`agents/README.md`](agents/README.md).

## Repository Layout (`v4.0.9`)
*(See [`AGENTS.md`](AGENTS.md) for the complete modular architecture reference.)*

```text
agy-nexus-mcp/
├── src/agy_nexus/        # Modular backend/MCP modules (<=500L target, 650L ceiling): ls_quota_probe, model_pricing, cost_ledger,
│                         #   catalog_{sync,report,validator}, project_stats, ascii_{default,rich,models}, config, hygiene, polyglot_*,
│                         #   handoff_*, tools_praxis, stats*, media*, bucket_*, web_routes, uploads, sessions, server
├── ag_bridge.py & server.json  # Backward-compatible 75-line root entrypoint shim & 2025-12-11 MCP Registry manifest (with Dockerfile)
├── web/                  # Quiet UI v9.3.0 Studio PWA (primary /web + /web/v9 + offline vendored ECharts, v9/*, demo_snapshot.js)
├── host_bridge/          # Loopback-only authenticated Host Companion (:8098), CreateProject & HMAC security
├── agents/ & skills/     # Synced 12-Agent Dual-Pool Roster & agy-nexus-stats SKILL.md
├── docs/ & scripts/      # DEPLOYMENT, WORKFLOWS, PRICING_HISTORY, assets/; setup, sync_agents, sync_host_quota, showcase scripts
├── systemd/ & .github/   # 60s agy-quota-sync.timer, 01:45 AM drift watchdog, ci.yml, catalog-sync.yml & OIDC publish-mcp.yml
├── tests/                # Pytest regression suites + conftest STATE_FILE isolation (v2.6 – v4.0.9)
└── README.md, AGENTS.md, CHANGELOG.md, SECURITY.md, CONTRIBUTING.md, ACCESSIBILITY.md, LICENSE, NOTICE
```

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
