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
- **8-Model Registry, Effective-Dated Cost Ledger & `01:45 AM` Drift Watchdog**: Tracks all 8 live models (`Gemini 4 Carbon`, `Neon`, `Argon`, `Hydrogen`, `Gemini 3.8 Flash`, `Claude Opus 5.5`, `Claude Sonnet 5.5`, `GPT-OSS 120B`) with immutable micro-USD epochs (`CACHE_VERSION = 9`, `cost_ledger.json`), deadbolt-safe `76`-col `models` ASCII status, `13`-agent `sync_agents.py`, and read-only `01:45 AM` `agy-model-drift-check.timer`.
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
║ 3-2-1 BACKUP: a007634 (SYNCED ✓ · 22297.3 KB · 4h ago)                   ║
╚══════════════════════════════════════════════════════════════════════════╝

[PROJECT 1] Quiet UI Skills [SHARED REPO] [▶ 2 IN-WORK]
  project_id : 696506de-5df1-41da-9b5c-03c2e1b9128c
  workspaces : /home/dev/agentic_workspace/projects/quiet-ui-skills
  ├─ [HANDOFF quiet-ui-skills-65] Quiet UI v9.7.0 Wave 3.5 — 3-Layer Governing Rules & CDP Auditor Gates
  │   pass_off   : [▶ IN-WORK] · plan/feature_update · 27m ago
  │   session_id : ad751d6d-e756-44df-a6b1-f60659240674
  ├─ [HANDOFF quiet-ui-skills-60] User Goal & Why
  │   pass_off   : [▶ IN-WORK] · fast/release_closeout · 10h ago
  │   session_id : bb01e6db-7615-4259-8a98-f96aa9b4025d
  ├─ (+16 older completed)
  ├─ [#1] Quiet UI v9.7.0 Wave 3 — Wave 2 Polish & Full 26-View Stratified Mega-Audit
  │   session_id : ad751d6d-e756-44df-a6b1-f60659240674
  │   workspace  : /home/dev/agentic_workspace/projects/quiet-ui-skills
  │   status     : [● RUNNING] · MAIN WRITER · 508 steps · 3s ago
  ├─ [#5] Quiet UI v9.7.0 Wave 2 — New Studio Archetypes (v23–v26) & Specimens 51–53
  │   session_id : b4e294fc-0641-435f-b9a9-5d5d5485b775
  │   workspace  : /home/dev/agentic_workspace/projects/quiet-ui-skills
  │   status     : [○ COMPLETED] · SHARED (READ-ONLY) · 600 steps · 3h ago
  └─ [#9] Quiet UI v9.7.0 Wave 1.5 — Integrated Card-Bound Alarm Trace & Visual Polish
      session_id : 2827d6f8-0e09-4dc9-b258-878044db081b
      workspace  : /home/dev/agentic_workspace/projects/quiet-ui-skills
      status     : [○ COMPLETED] · SHARED (READ-ONLY) · 446 steps · 5h ago

[PROJECT 2] AGY Nexus MCP [SHARED REPO] [▶ 1 IN-WORK]
  project_id : f1378431-5b09-4545-a48c-ac5c67c04fd3
  workspaces : /home/dev/agentic_workspace/projects/agy-nexus-mcp
  ├─ [HANDOFF agy-nexus-mcp-64] AGY-Nexus MCP v4.1.0 Wave 1 (develop) — Quota & Resets (% Left), 13-Agent Sync, Surgeon Handoffs & Table/Chart Fixes
  │   pass_off   : [▶ IN-WORK] · plan/feature_update · 32m ago
  │   session_id : 9e68bd89-80c8-44d8-9ed5-ebd2090223b9
  ├─ [HANDOFF agy-nexus-mcp-63] AGY-Nexus MCP v4.0.9 Release Closeout — Protected-main PR, Ruleset, GHCR & MCP Registry Publish
  │   pass_off   : [✓ COMPLETED] · fast/release_closeout · 4h ago
  │   session_id : e208f978-714f-4c4a-97d0-f567d3bb8b97
  ├─ (+18 older completed)
  ├─ [#2] AGY-Nexus MCP v4.1.0 Wave 1 (develop) — Quota & Resets (% Left), 13-Agent Sync, Surgeon Handoffs & Table/Chart Fixes
  │   session_id : 9e68bd89-80c8-44d8-9ed5-ebd2090223b9
  │   workspace  : /home/dev/agentic_workspace/projects/agy-nexus-mcp
  │   status     : [● RUNNING] · MAIN WRITER · 321 steps · 11s ago
  ├─ [#7] AGY-Nexus MCP v4.0.9 Release Closeout — Protected-main PR, Ruleset, GHCR & MCP Registry Publish
  │   session_id : e208f978-714f-4c4a-97d0-f567d3bb8b97
  │   workspace  : /home/dev/agentic_workspace/projects/agy-nexus-mcp
  │   status     : [○ COMPLETED] · SHARED (READ-ONLY) · 335 steps · 4h ago
  └─ [#8] AGY-Nexus MCP v4.0.9 Wave 5.1 (develop) — 3px Heatmap Gutters, Larger Cells & 1px Zigzag Divider
      session_id : c99ae480-06d7-45ec-9589-81141d8b6641
      workspace  : /home/dev/agentic_workspace/projects/agy-nexus-mcp
      status     : [○ COMPLETED] · SHARED (READ-ONLY) · 610 steps · 4h ago

[PROJECT 3] Telemetry Ingestor [SHARED REPO]
  project_id : 63524eb2-fb6e-4f0a-bbc8-9305ee26956a
  workspaces : /home/dev/agentic_workspace/projects/telemetry-ingestor
  ├─ [HANDOFF telemetry-ingestor-12] Phase 1.2 — Worker Buffering, Retry Backoff & Verification
  │   pass_off   : [✓ COMPLETED] · plan/feature_update · 1h ago
  │   session_id : f203b6c5-69b1-45f2-b23a-f3d391872ad0
  ├─ [HANDOFF telemetry-ingestor-11] Phase 1.0 — Core Pipeline Architecture & Modular Hygiene
  │   pass_off   : [✓ COMPLETED] · plan/feature_update · 3h ago
  │   session_id : f203b6c5-69b1-45f2-b23a-f3d391872ad0
  ├─ (+9 older completed)
  ├─ [#3] Phase 1.0 — Core Pipeline Architecture & Modular Hygiene
  │   session_id : f203b6c5-69b1-45f2-b23a-f3d391872ad0
  │   workspace  : /home/dev/agentic_workspace/projects/telemetry-ingestor
  │   status     : [◉ PINNED · IDLE] · PINNED (READ-ONLY) · 739 steps · 1h ago
  ├─ [#11] Phase 1.2 — Worker Buffering, Retry Backoff & Verification
  │   session_id : b7d7ad04-058a-4920-a69b-78c8ba242a03
  │   workspace  : /home/dev/agentic_workspace/projects/telemetry-ingestor
  │   status     : [○ COMPLETED] · MAIN TREE · 384 steps · 6h ago
  └─ [#14] Phase 1.0 — Core Pipeline Architecture & Modular Hygiene
      session_id : 16c2d90d-dfb4-4a0a-815e-ad99eff9c2ea
      workspace  : /home/dev/agentic_workspace/projects/telemetry-ingestor
      status     : [○ COMPLETED] · MAIN TREE · 725 steps · 8h ago
```

## Three-Tier ASCII Usage Reports in Chat

Ask Gemini for your usage stats (`get_session_tree(include_stats=True, period="last_90d", style=...)` or `manage_background_run(action="stats", ...)`) to render live Dual-Pool Quota & Resets, `Mon–Sun` calendar heatmaps, sub-daily curves, and workspace/subagent token breakdowns in **three plain-text layouts**:

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
GOOGLE 20x : 100.1% [████████┼█] HEALTHY┆ 0x 429s | Ultra-20x (T:>=90%) 
PARTNER 1x : 100.0% [░┼░░░░░░░░] OK     ┆ 100.0% Wk Left | Lim <=14.3%/d
STEPS/TOOLS: 296,757s | 159,749t | 239c ┆ 5,495 s/act-d | 3,261 s/cal-d 
TOKEN BURN : ~14.9B | $3,780.20         ┆ 276.8M/d | $70.00/d (797r)    
MCP WIRE   : 97% <20KB (avg 11.2/35.5KB)┆ 139 req (433k tok) | Web+Praxi
CODE HEALTH: Poly 3100 syms | 94/94 <=50┆ 0 >650L | Praxis+Serena       
────────────────────────────────────────┴───────────────────────────────
DAILY HEATMAP (NOW: W01 ──► 22w AGO)   Peak: 11/22 (20,915s) | Act: 54d
Wk    01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22
Mon   ██ ██ ▒▒ ▒▒ ▓▓ ░░ ░░ ·· ░░ ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ··
Tue   ██ ██ ▓▓ ▒▒ ▒▒ ░░ ░░ ·· ·· ░░ ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ··
Wed   ██ ██ ▓▓ ▓▓ ▒▒ ·· ░░ ·· ░░ ░░ ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ··
Thu   ·· ██ ▒▒ ▒▒ ▒▒ ░░ ░░ ·· ·· ▒▒ ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ··
Fri   ·· ██ ▓▓ ▓▓ ▒▒ ▓▓ ░░ ·· ▒▒ ▓▓ ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ··
Sat   ·· ██ ██ ██ ██ ▓▓ ░░ ·· ▓▓ ▒▒ ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ··
Sun   ·· ██ ██ ▓▓ ▓▓ ▒▒ ▒▒ ·· ▓▓ ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ··
Vol   ▃▃ ██ ▄▄ ▃▃ ▃▃ ▂▂ ▁▁ ── ▁▁ ▁▁ ── ── ── ── ── ── ── ── ── ── ── ──
────────────────────────────────────────────────────────────────────────
8H SUB-DAILY PACE (NOW ──► SEP 21)   [Avg: 362/8h | Peak: 1.4k | ░▒▓█]
1.4k ╷       █                                                         
 731 ┤ ▄ █   █   █        ▄                                            
 362 ┼─███──██──▄█────────█────────────────────────────────────────────
   0 ╵▄▓█▒█ █▒ ▄█▒ ▄▄ ░ █▄█          ▄░    ▄▄▄ ▄         ░░▄   ░ ▄     
     └─▲────────────▲────────────▲────────────▲────────────▲──────────▲─
      Nov 25       Nov 12       Oct 30       Oct 16       Oct 03     Sep
      Stack: [█] stem-curricul (22%)  [▓] quiet-ui-skil (11%)  [▒] mail-
────────────────────────────────────────────────────────────────────────
MODEL       [QUOTA ┼ TARGET] SHARE    CALLS     TOK    EST.$  DLT  STAT
Carbon 4    [██▓┼░░░░░░░░░░] 16.2%  21,144    5.2B  $1,370   -4% OK  
Neon 4      [░┼░░░░░░░░░░░░]  0.2%     212   38.6M   $15.8  -10% OK  
Argon 4     [███┼██▓░░░░░░░] 44.1%  57,714    8.6B  $2,230  +19% WARN
Hydrogen 4  [░░┼░░░░░░░░░░░]  0.1%     114    5.2M   $2.60  -15% WARN
Flash 3.8   [███┼██░░░░░░░░] 39.5%  51,642    1.1B  $161.4  +20% WARN
Opus 5.5    [▏░░░░░░░░░░░░░]  0.0%       0       0   $0.00   -3% OK  
Sonnet 5.5  [░┼░░░░░░░░░░░░]  0.0%       0       0   $0.00   -5% OK  
GPT-OSS 120 [▏░░░░░░░░░░░░░]  0.0%       9    264k   $0.00   -2% OK  
BILLING    Hist:$3,780 API | NextRate:$7,542 (+100%) | 20x:6.2x
────────────────────────────────────────────────────────────────────────
WORKSPACES (17)  CHATS  STEPS    TOK   TOK/D   TOK/WK   EST.$  SHARE
1. stem-curricul  74c 64,593    3.8B  71.0M  496.8M  $972.8  21.8%
2. quiet-ui-skil  44c 33,247    2.1B  38.8M  271.9M  $579.0  11.2%
3. mail-triage-u  32c 33,022    2.2B  40.6M  284.0M  $461.5  11.1%
4. home-telemetr   4c 32,348    2.0B  37.7M  263.6M  $496.5  10.9%
5. agy-nexus-mcp  37c 28,822    1.9B  34.9M  244.4M  $496.0   9.7%
6. task-queue-en   1c 25,933  346.9M  6.42M   45.0M   $96.3   8.7%
7. net-topology-   6c 20,803  955.2M  17.7M  123.8M  $219.2   7.0%
8. cloud-gitops-   4c 15,070   52.7M   976k   6.83M   $11.9   5.1%
9. edge-iot-cont   6c 12,250    9.5M   175k   1.23M   $1.51   4.1%
10. agent-harnes  10c 10,643  550.4M  10.2M   71.4M  $144.1   3.6%
11. scratch-prot   8c  7,797  350.8M  6.50M   45.5M  $110.1   2.6%
12. container-gi   4c  4,995  247.0M  4.57M   32.0M   $69.3   1.7%
13. telemetry-in   5c  3,253  201.4M  3.73M   26.1M   $69.8   1.1%
14. edge-proxy-r   2c  2,069  150.5M  2.79M   19.5M   $46.0   0.7%
15. astro-sky-ma   1c  1,126    294k   5.4k     38k   $0.02   0.4%
16. rf-dsp-modem   0c    609   34.6M   641k   4.48M   $4.37   0.2%
17. civic-map-en   1c    177    6.9M   128k    898k   $1.74   0.1%
────────────────────────────────────────────────────────────────────────
SUBAGENTS (24)    RUNS  STEPS    TOK   TOK/D   TOK/WK   EST.$  SHARE
1. argon-sentine 161r 29,031    1.4B  26.4M  184.6M  $513.9  28.2%
2. flash-surgeon 170r 26,573  378.5M  7.01M   49.1M   $52.7  25.8%
3. flash-auditor 213r 16,220  432.7M  8.01M   56.1M   $66.9  15.8%
4. research       96r 11,268  503.8M  9.33M   65.3M  $187.5  10.9%
5. argon-surgeon  14r  8,282  527.2M  9.76M   68.3M  $122.9   8.0%
6. flash-scout    75r  6,514  164.9M  3.05M   21.4M   $25.7   6.3%
7. claude-sentin  31r  2,867  152.0M  2.81M   19.7M   $61.2   2.8%
8. neon-surgeon    6r    534   38.8M   719k   5.03M   $15.8   0.5%
9. sprint19-sent   4r    370   10.2M   189k   1.32M   $5.08   0.4%
10. hydrogen-sur  10r    314    5.3M    98k    686k   $2.60   0.3%
11. carbon-senti   2r    180    7.8M   144k   1.01M   $2.85   0.2%
12. v960-argon-s   1r    160    5.1M    95k    667k   $2.27   0.2%
13. argon-archit   2r    132    3.8M    71k    499k   $1.79   0.1%
14. v3-argon-sen   1r    110    5.3M    98k    684k   $3.50   0.1%
15. wave1-argon-   1r    103    3.7M    69k    480k   $1.81   0.1%
16. security-sen   1r     87    3.4M    64k    447k   $1.56   0.1%
17. diff-auditor   1r     51    2.3M    42k    292k   $1.02   0.0%
18. flash-doc-su   1r     38    251k   4.6k     33k   $0.12   0.0%
19. claude-speci   1r     31   11.8k    218    1.5k   $0.00   0.0%
20. wave4-audito   1r     26    216k   4.0k     28k   $0.14   0.0%
21. pool-failove   2r     24    266k   4.9k     34k   $0.00   0.0%
22. SCL-flash-au   1r     18    341k   6.3k     44k   $0.10   0.0%
23. self           1r     12    148k   2.7k     19k   $0.11   0.0%
24. hygiene-audi   1r      4   18.1k    336    2.4k   $0.04   0.0%
════════════════════════════════════════════════════════════════════════
```

### 2. `style="quick"` (40-Column Mobile Layout)

```text
════════════════════════════════════════
AGY-NEXUS v4.0.9 // 91d (Nov 25 ◄── Aug 
════════════════════════════════════════
G-20x: 100% [████████┼█] OK | 0x 429s
P-1x : 100% [░┼░░░░░░░░] OK | 100% WkLft
Steps:296.8k | Tools:159.7k | Act:54d
Burn:14.9B | $3,780 | 276.8M/d
Health: Poly 3100s | 94/94 <=500L | up_t
────────────────────────────────────────
HEATMAP (NOW ──► 13w Ago)  │ PEAK & VOL
Mo ██▒▒▓░░·░····           │ Pk: 11/22
Tu ██▓▒▒░░··░···           │ 20,915 stp
We ██▓▓▒·░·░░···           │ Avg:5,495/d
Th ·█▒▒▒░░··▒···           │ Cost: $3,78
Fr ·█▓▓▒▓░·▒▓···           │ Subs : 797r
Sa ·████▓░·▓▒···           │ Tok/d:276.8
Su ·██▓▓▒▒·▓····           │ Tok/w:1.94B
────────────────────────────────────────
8H PACE & STACK (NOW──►OLD) Pk:1.0k
1.0k╷     █      ▄            ▄      
 522┤ ▄  ██ █ ▄  █            █      
 418┼─█▄─██─█─█──█────────────█──────
   0╵▄█▓▄██ █▒█▄ ▒▄ ░ ▄▄ ▄▄   ░      
────────────────────────────────────────
MODEL   [PIN]    PCT   TOK  EST.$   DLT
Carbon4 [█┼░░░░░░] 16%  5.2B $1,370  -4
Neon 4  [░┼░░░░░░]  0% 38.6M  $15.8 -10
Argon 4 [██┼█░░░░] 44%  8.6B $2,230 +19
Hydro 4 [░┼░░░░░░]  0%  5.2M  $2.60 -15
Flash38 [█┼█▓░░░░] 40%  1.1B $161.4 +20
Opus5.5 [▏░░░░░░░]  0%     0  $0.00  -3
Sonn5.5 [▏░░░░░░░]  0%     0  $0.00  -5
GPT-120 [▏░░░░░░░]  0%  264k  $0.00  -2
────────────────────────────────────────
WORKSPACES & SUBS  TOK   EST.$  TOK/WK
stem-curriculum  3.8B  $972.8  496.8M
quiet-ui-skills  2.1B  $579.0  271.9M
mail-triage-ui   2.2B  $461.5  284.0M
home-telemetry-  2.0B  $496.5  263.6M
agy-nexus-mcp    1.9B  $496.0  244.4M
task-queue-engi 346.9M   $96.3   45.0M
*argon-sentinel  1.4B  $513.9  184.6M
*flash-surgeon  378.5M   $52.7   49.1M
*flash-auditor  432.7M   $66.9   56.1M
════════════════════════════════════════
```

### 3. `style="rich"` (76-Column Widescreen Layout)

```text
╔══════════════════════════════════════════════════════════════════════════╗
║ ▄▀█ █▀▀ █▄█ ▄▄ █▄░█ █▀▀ ▀▄▀ █░█ █▀   v4.0.9 // RICH TELEMETRY RIG        ║
║ █▀█ █▄█ ░█░ ░░ █░▀█ ██▄ █░█ █▄█ ▄█   WINDOW: 91d (Nov 25 ◄── Aug 27)     ║
╠════════════════════════════════════╦═════════════════════════════════════╣
║ QUOTA & RESETS & POOL SPLIT        │ STEP & TOOL VELOCITY                ║
║ G 5h: 73% lft [████··] 2h52  OK    │ Total : 296,757 steps | 159,749 too ║
║ G Wk: 39% lft [██····] 4d3h  OK    │ Active: 5,495 s/act-d (54d active)  ║
║ Split:100/0 T90/10 P:Stby 429:0    │ Calend: 3,261 s/cal-d (239c, 797r)  ║
╠════════════════════════════════════╬═════════════════════════════════════╣
║ TOKEN BURN & API COST LEDGER       │ MCP WIRE & CLIENT SURFACES          ║
║ Total : ~14.9B | $3,780.20         │ Wire  : 97% <20KB (avg 11.2/35.5KB) ║
║ Daily : 276.8M/d ($70.00/d)        │ Calls : 139 MCP reqs (433k tok)     ║
║ NextRt: $7,541.97 API Forecast     │ Client: Web 51% · Prx 49% · Mob 0%  ║
╠════════════════════════════════════╦═════════════════════════════════════╣
║ VERSION & RELEASE STATUS           │ POLYGLOT & MODULAR CODE HEALTH      ║
║ Installed: v4.0.9 (up_to_date)     │ Poly: 3100s | 94/94 <=500L 0>650L   ║
║ Remote   : v4.0.9                  │ IDE MCP  : agy-praxis-mcp + Serena  ║
╠════════════════════════════════════╩═════════════════════════════════════╣
║ DAILY ACTIVITY MATRIX (NOW: W01 ──► W13)     [·· 0  ░░ <1k  ▒▒ <4k  ██]  ║
║ Wk   W01 W02 W03 W04 W05 W06 W07 W08 W09 W10 W11 W12 W13  ┌─ PEAK DAY ─┐ ║
║ Mon  ███ ███ ▒▒▒ ▒▒▒ ▓▓▓ ░░░ ░░░ ··· ░░░ ··· ··· ··· ···  │ Nov 22     │ ║
║ Tue  ███ ███ ▓▓▓ ▒▒▒ ▒▒▒ ░░░ ░░░ ··· ··· ░░░ ··· ··· ···  │ 20,915 stp │ ║
║ Wed  ███ ███ ▓▓▓ ▓▓▓ ▒▒▒ ··· ░░░ ··· ░░░ ░░░ ··· ··· ···  ├────────────┤ ║
║ Thu  ··· ███ ▒▒▒ ▒▒▒ ▒▒▒ ░░░ ░░░ ··· ··· ▒▒▒ ··· ··· ···  │ Act: 54d   │ ║
║ Fri  ··· ███ ▓▓▓ ▓▓▓ ▒▒▒ ▓▓▓ ░░░ ··· ▒▒▒ ▓▓▓ ··· ··· ···  │ Avg:  5.5k │ ║
║ Sat  ··· ███ ███ ███ ███ ▓▓▓ ░░░ ··· ▓▓▓ ▒▒▒ ··· ··· ···  │ Sub: 797r  │ ║
║ Sun  ··· ███ ███ ▓▓▓ ▓▓▓ ▒▒▒ ▒▒▒ ··· ▓▓▓ ··· ··· ··· ···  └────────────┘ ║
║ Vol  ▃▃▃ ███ ▄▄▄ ▃▃▃ ▃▃▃ ▂▂▂ ▁▁▁ ─── ▁▁▁ ▁▁▁ ─── ─── ───  PeakWk:83.6k   ║
║ Steps 39k 84k 53k 35k 31k 19k  7k  ·  16k 12k  ·   ·   ·                 ║
╠══════════════════════════════════════════════════════════════════════════╣
║ 8H SUB-DAILY HORIZON CURVE & PROJECT STACK (NOW ──► SEP 21)              ║
║ 2.3k ╷   █                                                               ║
║ 1.8k ┤   █                                                               ║
║ 1.2k ┤   █                                                               ║
║  377 ┼   █    ▄        ▄      ▄      █                                   ║
║  408 ┤──██────█─█───▄──█──────█──────█──────────────────▄─────────────   ║
║    0 ╵▄▓█▒▄   ██▒▒  ░ ▄▒ ▄▄ ▄░░      ░   ▄      ▄       ░▄▄     ▄▄▄      ║
║      └─▲───────────▲───────────▲───────────▲───────────▲───────────▲───  ║
║       Nov 25      Nov 12      Oct 29      Oct 16      Oct 02      Sep 21 ║
║       Stack: [█]stem-curricu(22%)  [▓]quiet-ui-ski(11%)  [▒]mail-triage- ║
╠══════════════════════════════════════════════════════════════════════════╣
║ MODEL       [QUOTA ┼ TARGET] SHARE    CALLS     TOK    EST.$  DLT  STAT  ║
║ Carbon 4    [██▓┼░░░░░░░░░░] 16.2%  21,144    5.2B  $1,370   -4% OK      ║
║ Neon 4      [░┼░░░░░░░░░░░░]  0.2%     212   38.6M   $15.8  -10% OK      ║
║ Argon 4     [███┼██▓░░░░░░░] 44.1%  57,714    8.6B  $2,230  +19% WRN     ║
║ Hydrogen 4  [░░┼░░░░░░░░░░░]  0.1%     114    5.2M   $2.60  -15% WRN     ║
║ Flash 3.8   [███┼██░░░░░░░░] 39.5%  51,642    1.1B  $161.4  +20% WRN     ║
║ Opus 5.5    [▏░░░░░░░░░░░░░]  0.0%       0       0   $0.00   -3% OK      ║
║ Sonnet 5.5  [░┼░░░░░░░░░░░░]  0.0%       0       0   $0.00   -5% OK      ║
║ GPT-OSS 120 [▏░░░░░░░░░░░░░]  0.0%       9    264k   $0.00   -2% OK      ║
║ BILLING CMP: Hist $3,780 | NextRate $7,542 (+100%) | 20x 6.2x            ║
╠══════════════════════════════════════════════════════════════════════════╣
║ WORKSPACES (17)  CHATS   STEPS     TOK   TOK/D   EST.$ SHARE GAUGE       ║
║ 1. stem-curricul  74c  64,593    3.8B  71.0M  $972.8 █▍░░░░ 21.8%        ║
║ 2. quiet-ui-skil  44c  33,247    2.1B  38.8M  $579.0 ▍░░░░░ 11.2%        ║
║ 3. mail-triage-u  32c  33,022    2.2B  40.6M  $461.5 ▍░░░░░ 11.1%        ║
║ 4. home-telemetr   4c  32,348    2.0B  37.7M  $496.5 ▍░░░░░ 10.9%        ║
║ 5. agy-nexus-mcp  37c  28,822    1.9B  34.9M  $496.0 ▍░░░░░  9.7%        ║
║ 6. task-queue-en   1c  25,933  346.9M  6.42M   $96.3 ▍░░░░░  8.7%        ║
║ 7. net-topology-   6c  20,803  955.2M  17.7M  $219.2 ▍░░░░░  7.0%        ║
║ 8. cloud-gitops-   4c  15,070   52.7M   976k   $11.9 ▍░░░░░  5.1%        ║
║ 9. edge-iot-cont   6c  12,250    9.5M   175k   $1.51 ░░░░░░  4.1%        ║
║ 10. agent-harnes  10c  10,643  550.4M  10.2M  $144.1 ░░░░░░  3.6%        ║
║ 11. scratch-prot   8c   7,797  350.8M  6.50M  $110.1 ░░░░░░  2.6%        ║
║ 12. container-gi   4c   4,995  247.0M  4.57M   $69.3 ░░░░░░  1.7%        ║
║ 13. telemetry-in   5c   3,253  201.4M  3.73M   $69.8 ░░░░░░  1.1%        ║
║ 14. edge-proxy-r   2c   2,069  150.5M  2.79M   $46.0 ░░░░░░  0.7%        ║
║ 15. astro-sky-ma   1c   1,126    294k   5.4k   $0.02 ░░░░░░  0.4%        ║
║ 16. rf-dsp-modem   0c     609   34.6M   641k   $4.37 ░░░░░░  0.2%        ║
║ 17. civic-map-en   1c     177    6.9M   128k   $1.74 ░░░░░░  0.1%        ║
╟──────────────────────────────────────────────────────────────────────────╢
║ SUBAGENTS (24)    RUNS   STEPS     TOK   TOK/D   EST.$ SHARE GAUGE       ║
║ 1. argon-sentine 161r  29,031    1.4B  26.4M  $513.9 █▍░░░░ 28.2%        ║
║ 2. flash-surgeon 170r  26,573  378.5M  7.01M   $52.7 █▍░░░░ 25.8%        ║
║ 3. flash-auditor 213r  16,220  432.7M  8.01M   $66.9 ▍░░░░░ 15.8%        ║
║ 4. research       96r  11,268  503.8M  9.33M  $187.5 ▍░░░░░ 10.9%        ║
║ 5. argon-surgeon  14r   8,282  527.2M  9.76M  $122.9 ▍░░░░░  8.0%        ║
║ 6. flash-scout    75r   6,514  164.9M  3.05M   $25.7 ▍░░░░░  6.3%        ║
║ 7. claude-sentin  31r   2,867  152.0M  2.81M   $61.2 ░░░░░░  2.8%        ║
║ 8. neon-surgeon    6r     534   38.8M   719k   $15.8 ░░░░░░  0.5%        ║
║ 9. sprint19-sent   4r     370   10.2M   189k   $5.08 ░░░░░░  0.4%        ║
║ 10. hydrogen-sur  10r     314    5.3M    98k   $2.60 ░░░░░░  0.3%        ║
║ 11. carbon-senti   2r     180    7.8M   144k   $2.85 ░░░░░░  0.2%        ║
║ 12. v960-argon-s   1r     160    5.1M    95k   $2.27 ░░░░░░  0.2%        ║
║ 13. argon-archit   2r     132    3.8M    71k   $1.79 ░░░░░░  0.1%        ║
║ 14. v3-argon-sen   1r     110    5.3M    98k   $3.50 ░░░░░░  0.1%        ║
║ 15. wave1-argon-   1r     103    3.7M    69k   $1.81 ░░░░░░  0.1%        ║
║ 16. security-sen   1r      87    3.4M    64k   $1.56 ░░░░░░  0.1%        ║
║ 17. diff-auditor   1r      51    2.3M    42k   $1.02 ░░░░░░  0.0%        ║
║ 18. flash-doc-su   1r      38    251k   4.6k   $0.12 ░░░░░░  0.0%        ║
║ 19. claude-speci   1r      31   11.8k    218   $0.00 ░░░░░░  0.0%        ║
║ 20. wave4-audito   1r      26    216k   4.0k   $0.14 ░░░░░░  0.0%        ║
║ 21. pool-failove   2r      24    266k   4.9k   $0.00 ░░░░░░  0.0%        ║
║ 22. SCL-flash-au   1r      18    341k   6.3k   $0.10 ░░░░░░  0.0%        ║
║ 23. self           1r      12    148k   2.7k   $0.11 ░░░░░░  0.0%        ║
║ 24. hygiene-audi   1r       4   18.1k    336   $0.04 ░░░░░░  0.0%        ║
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
## Bundled 13-Agent Orthogonal Roster (`agents/`)
`agy-nexus-mcp` ships with the synced Dual-Pool subagent roster in [`agents/`](agents/) (`swarm-orchestrator`, `flash-scout`, `argon-architect`, `flash-surgeon`, `hydrogen-surgeon`, `neon-surgeon`, `argon-surgeon`, `flash-auditor`, `argon-sentinel`, `carbon-sentinel`, `claude-specialist`, `claude-sentinel`, `pool-failover`) synced via `python3 scripts/sync_agents.py --apply` (check via `--check`). Subagent runs, `$ Est. Cost`, and `Avg Tok/Run` appear in `/web` and ASCII reports. See [`AGENTS.md`](AGENTS.md) and [`agents/README.md`](agents/README.md).

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
├── agents/ & skills/     # Synced 13-Agent Dual-Pool Roster & agy-nexus-stats SKILL.md
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
