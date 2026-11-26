# `agy-nexus-mcp` — Steer Your Coding Workstation from Gemini (`v4.2.0`)

<!-- mcp-name: io.github.FrankXLT/agy-nexus-mcp -->

`agy-nexus-mcp` connects **Google Gemini** (on your phone, tablet, or browser) to your local **Antigravity IDE** coding workstation—giving you a calm, locked-down remote control and an offline-capable usage studio without leaving your terminal open to the internet.

Whether you are away from your desk or managing multiple repositories at once, `agy-nexus-mcp` delivers **three everyday payoffs**:

1. **Steer your coding workstation from Gemini on phone or web** — Check active coding chats, read diffs and walkthrough screenshots, and send your next feature or bugfix straight to your workstation.
2. **Check Gemini & Claude Quota & Resets Percentage Left** — Track live 5-hour and weekly remaining capacity and reset countdowns across every account, alongside estimated API value compared to `Plus`, `Pro`, and `Ultra` plans.
3. **Keep routine scouting and edits on faster helper models with Model Routing Checks** — Confirm that everyday file scans, mechanical edits, and test runs stayed on fast helper models instead of silently falling back to heavy, expensive defaults.

### Explore the Open Agentic Workbench Project Site

- **[Project Overview](https://projects.oaworkbench.org/agy-nexus-mcp/)** — Plain-language tour, feature highlights, and architecture summary
- **[Live Interactive Demo](https://projects.oaworkbench.org/agy-nexus-mcp/demo/)** — Try the Analytics ledger and 2-Pane Workspace Explorer right in your browser (zero backend required)
- **[Searchable Plain-Language Docs](https://projects.oaworkbench.org/agy-nexus-mcp/docs/)** — Setup walkthroughs, everyday prompts, and troubleshooting

---

## Live `/web` Studio (`Analytics` + 2-Pane `Workspace`)

### 1. `Analytics` — Quota & Resets, 8-Model Cost Ledger & Activity Matrix
![AGY-NEXUS v4.2.0 Analytics Surface — Quiet UI Studio with Quota & Resets (% Left), 8-Model Cost Ledger, Activity Heatmap & Code Health](docs/assets/dashboard-desktop.png)

### 2. `Workspace` — 2-Pane Session Explorer, Editorial Reader & Capture Gallery
![AGY-NEXUS v4.2.0 2-Pane Workspace Explorer — Recency Project Rail, Editorial Markdown Tabs & Direct PNG / Sheet Gallery](docs/assets/workspace-desktop.png)

<details>
<summary><strong>Mobile Layouts (<code>390px</code> Portrait — Analytics &amp; Workspace Explorer)</strong></summary>

![AGY-NEXUS v4.2.0 Mobile Analytics View](docs/assets/dashboard-mobile.png)
![AGY-NEXUS v4.2.0 Mobile Workspace View](docs/assets/workspace-mobile.png)

</details>

---

## Quickstart (`4.2.0`)

Run the public OCI container over `--stdio` with no local Python setup (optional `PASS_HASH` unlocks private workspace tools):

```bash
docker run -i --rm ghcr.io/frankxlt/agy-nexus-mcp:4.2.0 --stdio
```

Or run and self-test directly from a cloned repository:

```bash
python3 ag_bridge.py --self-test
python3 -m agy_nexus.tools_praxis --self-test
python3 ag_bridge.py
```

### Connect Your Clients

- **Local IDEs & MCP Registry (`--stdio`)**: Install `io.github.FrankXLT/agy-nexus-mcp` using `ghcr.io/frankxlt/agy-nexus-mcp:4.2.0 --stdio` (in VS Code, Claude Code, Copilot CLI, or MCP Inspector):
  ```json
  {
    "mcpServers": {
      "agy-nexus-mcp": {
        "command": "docker",
        "args": ["run", "-i", "--rm", "ghcr.io/frankxlt/agy-nexus-mcp:4.2.0", "--stdio"]
      }
    }
  }
  ```
- **Gemini Web, Mobile & Tasks**: Add your HTTPS endpoint `https://<your-domain>/{PATH_SECRET}/mcp` and unlock on demand with your voice or text passphrase.
- **Antigravity IDE (`agy-praxis-mcp`)**: Point `~/.gemini/config/mcp_config.json` to your LAN-only doorway `http://<host>.lan:8765/praxis/<PRAXIS_MCP_TOKEN>/mcp` for codebase indexing and `<repo-slug>-NN` handoff claims.
- **Studio Web App (`/web`)**: Open `https://<your-domain>/web` (or add `?demo=1` for a depersonalized preview) to browse usage charts, sessions, and screenshots.

**Try asking Gemini:** *"Unlock Antigravity with [phrase] and show my session tree"* · *"Show my Quota & Resets Percentage Left"* · *"Inspect git diff on `agy-nexus-mcp`"* · *"Stage this visual fix (`allow_chained_publish=False`)"*

---

## Core Concepts in Plain Language

- **Two-Doorway Setup**: `agy-nexus-mcp` (`11` tools) is your authenticated remote bridge for Gemini Web, Mobile, and Tasks, while `agy-praxis-mcp` (`6` tools) is a strict LAN-only doorway inside your Antigravity IDE for fast SHA-256 codebase indexing (`polyglot_map`, `polyglot_search`, `polyglot_outline`) and claiming `<repo-slug>-NN` tickets.
- **Thirty-Minute Passphrase Lock**: A sliding-TTL voice/text deadbolt (`PASS_HASH`) keeps source code, file paths, and chat transcripts fail-closed until you speak or type your phrase—automatically re-locking after idle timeout. You can optionally enable `AG_BRIDGE_ALLOW_LOCKED_STATS=true` (privacy-safe quota summaries) or `AG_BRIDGE_ALLOW_LOCKED_STAGING=true` (quarantined task staging) while locked.
- **Quota & Resets Percentage Left**: Live 5-hour and weekly `% left` gauges with `"resets in ..."` countdowns across Google (`Gemini 4 Carbon`, `Neon`, `Argon`, `Hydrogen`, `3.8 Flash`) and Partner (`Claude Opus 5.5`, `Sonnet 5.5`, `GPT-OSS 120B`) pools, plus estimated API value alongside `Plus`, `Pro`, and `Ultra` plans.
- **Model Routing Check**: Compares each subagent's intended `targetModel` against actual transcript runs so accidental `model: inherit` fallbacks and unregistered ad-hoc roles are flagged cleanly in `/web` and ASCII reports.
- **Portfolio Header Switcher**: The unified Studio top bar lets you switch smoothly between `Analytics` (costs, quota, heatmaps, and code health) and `Workspace` (2-pane session reader, markdown tabs, and `Per Sheet 2/4/8` capture gallery), alongside quick links to the Open Agentic Workbench site and docs.

### Proportional Handoff Modes (`send_handoff_and_resume`)

| Mode | When to Use It | How Antigravity Executes It |
| :--- | :--- | :--- |
| **`feature_update`** *(Default)* | Add capabilities or refine workflows. | Full 4-Step flow (`flash-scout` → `surgeon` → `flash-auditor` → Dual-Review / Visual Gate). |
| **`new_project`** | Create a greenfield repo (`create_new_project=True`). | Blueprinted by `argon-architect` in `plan` mode with `<= 500L` modules and tests. |
| **`bug_or_visual_fix`** | Fix a targeted bug or `390px`/`900px`/`1440px` UI issue. | Fast surgical path for compact non-security diffs, or Dual-Review on auth/UI boundaries. |
| **`release_closeout`** | Verify tests, commit, tag, push, and retire a finished chat. | Marks `<slug>-NN` tickets `COMPLETED` and writes `RETIRED.json` after push succeeds. |

### `17` MCP Tools Across Both Doorways

- **`agy-nexus-mcp` Remote Bridge (`11` tools)**: `unlock_sessions`, `lock_bridge`, `list_saved_sessions`, `load_session_into_gemini`, `get_session_tree`, `ask_workspace_readonly`, `inspect_git_diff`, `inspect_visual_artifacts`, `send_handoff_and_resume`, `manage_background_run`, and `list_models_and_agents`.
- **`agy-praxis-mcp` Local IDE Doorway (`6` tools)**: `polyglot_map`, `polyglot_search`, `polyglot_outline`, `praxis_handoff_inbox`, `praxis_claim_handoff`, and `praxis_update_handoff`.

---

## Documentation & Guides

- **[Plain-Language User Guide](docs/GUIDE.md)** — Everyday workflows, passphrase lock tips, and Studio walkthrough
- **[How It Is Built](docs/HOW_IT_IS_BUILT.md)** — Modular `src/agy_nexus/` layout, 5-layer security model, and Dual-Doorway data flow
- **[Deployment Guide](docs/DEPLOYMENT.md)** — Docker Compose, reverse proxy, GHCR `--stdio`, and `systemd` timers
- **[Workflow Recipes](docs/WORKFLOWS.md)** — Gemini Notebook research handoffs, multi-repo drift audits, and `export_notebook`
- **[Changelog (`v4.2.0`)](CHANGELOG.md)** — Full release notes and version history
- **[Agents & Architecture (`AGENTS.md`)](AGENTS.md)** · **[13-Agent Roster (`agents/`)](agents/README.md)** · **[Security Policy](SECURITY.md)** · **[Accessibility](ACCESSIBILITY.md)**

---

<details>
<summary>Live Terminal & ASCII Telemetry Views (`v4.2.0`)</summary>

All four blocks below stay under `< 20 KB` wire budgets and are automatically refreshed with depersonalized workstation telemetry by `scripts/export_depersonalized_showcase.py`.

### 1. Copy-Ready 76-Column Session Hierarchy (`get_session_tree`)

```text
╔══════════════════════════════════════════════════════════════════════════╗
║ AGY-NEXUS v4.2.0 // PROJECT -> CHAT -> SESSION ID HIERARCHY (COPY-READY) ║
╠══════════════════════════════════════════════════════════════════════════╣
║ SLOTS: 3 | STAGED: 1 | IN-WORK: 3 | PINNED: 24 | TTL: 119.5m             ║
║ 3-2-1 BACKUP: a007634 (SYNCED ✓ · 22297.3 KB · 5h ago)                   ║
╚══════════════════════════════════════════════════════════════════════════╝

[PROJECT 1] AGY Nexus MCP [SHARED REPO] [▶ 1 IN-WORK]
  project_id : f1378431-5b09-4545-a48c-ac5c67c04fd3
  workspaces : /home/dev/agentic_workspace/projects/agy-nexus-mcp
  ├─ [HANDOFF agy-nexus-mcp-65] AGY-Nexus MCP v4.2.0 Release Closeout — Version Bump, Protected-main PR, GHCR & MCP Registry Publish
  │   pass_off   : [▶ IN-WORK] · fast/release_closeout · 14m ago
  │   session_id : 51f1ac45-1a8a-4f4f-b881-45150b725d11
  ├─ [HANDOFF agy-nexus-mcp-64] AGY-Nexus MCP v4.2.0 Wave 1 (develop) — Quota & Resets (% Left), 13-Agent Sync, Surgeon Handoffs & Table/Chart Fixes
  │   pass_off   : [✓ COMPLETED] · plan/feature_update · 22m ago
  │   session_id : 9e68bd89-80c8-44d8-9ed5-ebd2090223b9
  ├─ (+17 older completed)
  ├─ [#1] AGY-Nexus MCP v4.2.0 Release Closeout — Version Bump, Protected-main PR, GHCR & MCP Registry Publish
  │   session_id : 51f1ac45-1a8a-4f4f-b881-45150b725d11
  │   workspace  : /home/dev/agentic_workspace/projects/agy-nexus-mcp
  │   status     : [● RUNNING] · MAIN WRITER · 0 steps · 8s ago
  ├─ [#3] AGY-Nexus MCP v4.2.0 Wave 1 (develop) — Quota & Resets (% Left), 13-Agent Sync, Surgeon Handoffs & Table/Chart Fixes
  │   session_id : 9e68bd89-80c8-44d8-9ed5-ebd2090223b9
  │   workspace  : /home/dev/agentic_workspace/projects/agy-nexus-mcp
  │   status     : [◉ PINNED · IDLE] · SHARED (READ-ONLY) · 455 steps · 6m ago
  └─ [#10] AGY-Nexus MCP v4.0.9 Release Closeout — Protected-main PR, Ruleset, GHCR & MCP Registry Publish
      session_id : e208f978-714f-4c4a-97d0-f567d3bb8b97
      workspace  : /home/dev/agentic_workspace/projects/agy-nexus-mcp
      status     : [○ COMPLETED] · SHARED (READ-ONLY) · 335 steps · 5h ago

[PROJECT 2] Stem Curriculum Lab [SHARED REPO] [◈ 1 STAGED] [▶ 1 IN-WORK]
  project_id : 8d13c66f-569c-42e0-a57e-dd4b111ab5f2
  workspaces : /home/dev/agentic_workspace/projects/stem-curriculum-lab
  ├─ [HANDOFF stem-curriculum-lab-60] [SCL-Core] Stepped & Hex Domain Mosaics + Skill Trees
  │   pass_off   : [◈ STAGED · UNCLAIMED] · plan/feature_update · 6d ago
  │   session_id : (unclaimed · new chat)
  ├─ [HANDOFF stem-curriculum-lab-104] [SCL-Arch] Sprints 1–14 — Curriculum Engine & Edge CI
  │   pass_off   : [▶ IN-WORK] · plan/feature_update · 14m ago
  │   session_id : 0061a108-5cd9-4bcd-9c01-7a9c1e47011f
  ├─ (+17 older completed)
  ├─ [#2] [SCL-Portal] Landing Page, Control-Plane & OIDC Auth
  │   session_id : 0061a108-5cd9-4bcd-9c01-7a9c1e47011f
  │   workspace  : /home/dev/agentic_workspace/projects/stem-curriculum-lab
  │   status     : [◉ PINNED · IDLE] · MAIN WRITER · 125 steps · 5m ago
  ├─ [#16] [SCL-RF] Ch. I–VIII Interactive Signal Modules Overhaul
  │   session_id : ca2a7431-4f7c-4509-8b8b-2acd1086e407
  │   workspace  : /home/dev/agentic_workspace/projects/stem-curriculum-lab
  │   status     : [◉ PINNED · IDLE] · PINNED (VISION) · 789 steps · 9h ago
  └─ [#22] [SCL-Core] Stepped & Hex Domain Mosaics + Skill Trees
      session_id : 1a685fce-9e1f-41e3-98a0-e5d0b276ddce
      workspace  : /home/dev/agentic_workspace/projects/stem-curriculum-lab
      status     : [○ COMPLETED] · MAIN TREE · 881 steps · 20h ago

[PROJECT 3] Quiet UI Skills [SHARED REPO] [▶ 1 IN-WORK]
  project_id : 696506de-5df1-41da-9b5c-03c2e1b9128c
  workspaces : /home/dev/agentic_workspace/projects/quiet-ui-skills
  ├─ [HANDOFF quiet-ui-skills-60] User Goal & Why
  │   pass_off   : [▶ IN-WORK] · fast/release_closeout · 11h ago
  │   session_id : bb01e6db-7615-4259-8a98-f96aa9b4025d
  ├─ [HANDOFF quiet-ui-skills-65] Quiet UI v9.7.0 Wave 3.5 — 3-Layer Governing Rules & CDP Auditor Gates
  │   pass_off   : [✓ COMPLETED] · plan/feature_update · 6m ago
  │   session_id : ad751d6d-e756-44df-a6b1-f60659240674
  ├─ (+15 older completed)
  ├─ [#4] Quiet UI v9.7.0 Wave 3 — Wave 2 Polish & Full 26-View Stratified Mega-Audit
  │   session_id : ad751d6d-e756-44df-a6b1-f60659240674
  │   workspace  : /home/dev/agentic_workspace/projects/quiet-ui-skills
  │   status     : [◉ PINNED · IDLE] · SHARED (READ-ONLY) · 1,032 steps · 10m ago
  ├─ [#8] Quiet UI v9.7.0 Wave 2 — New Studio Archetypes (v23–v26) & Specimens 51–53
  │   session_id : b4e294fc-0641-435f-b9a9-5d5d5485b775
  │   workspace  : /home/dev/agentic_workspace/projects/quiet-ui-skills
  │   status     : [○ COMPLETED] · SHARED (READ-ONLY) · 600 steps · 4h ago
  └─ [#12] Quiet UI v9.7.0 Wave 1.5 — Integrated Card-Bound Alarm Trace & Visual Polish
      session_id : 2827d6f8-0e09-4dc9-b258-878044db081b
      workspace  : /home/dev/agentic_workspace/projects/quiet-ui-skills
      status     : [○ COMPLETED] · SHARED (READ-ONLY) · 446 steps · 6h ago
```

### 2. `style="default"` (72-Column Standard Layout)

```text
════════════════════════════════════════╤═══════════════════════════════
AGY-NEXUS v4.2.0 // 91d (Nov 25 ◄── Aug ┆ Up to Date (v4.2.0)           
════════════════════════════════════════╪═══════════════════════════════
GOOGLE 20x :  99.9% [████████┼█] HEALTHY┆ 0x 429s | Ultra-20x (T:>=90%) 
PARTNER 1x :  99.9% [░┼░░░░░░░░] OK     ┆ 100.0% Wk Left | Lim <=14.3%/d
STEPS/TOOLS: 298,746s | 161,110t | 242c ┆ 5,532 s/act-d | 3,282 s/cal-d 
TOKEN BURN : ~15.1B | $3,810.06         ┆ 278.9M/d | $70.56/d (811r)    
MCP WIRE   : 98% <20KB (avg 10.8/33.8KB)┆ 127 req (386k tok) | Web+Praxi
CODE HEALTH: Poly 3105 syms | 94/94 <=50┆ 0 >650L | Praxis+Serena       
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
8H SUB-DAILY PACE (NOW ──► SEP 21)   [Avg: 382/8h | Peak: 1.7k | ░▒▓█]
1.7k ╷   █                                                             
 871 ┤   █ ▄     ▄                                                     
 382 ┼▄─▄███▄────█─────────▄───────────────────────────────────────────
   0 ╵█▓█▒██▓█▄█ ▒   ▄ ▒ ▄ ░         ▄     ▄▄  ▄         ░░░   ▄       
     └─▲────────────▲────────────▲────────────▲────────────▲──────────▲─
      Nov 25       Nov 12       Oct 30       Oct 16       Oct 03     Sep
      Stack: [█] stem-curricul (22%)  [▓] quiet-ui-skil (11%)  [▒] mail-
────────────────────────────────────────────────────────────────────────
MODEL       [QUOTA ┼ TARGET] SHARE    CALLS     TOK    EST.$  DLT  STAT
Carbon 4    [██▓┼░░░░░░░░░░] 16.3%  21,474    5.2B  $1,391   -4% OK  
Neon 4      [░┼░░░░░░░░░░░░]  0.2%     309   43.7M   $18.8  -10% OK  
Argon 4     [███┼██▓░░░░░░░] 44.0%  57,776    8.6B  $2,235  +19% WARN
Hydrogen 4  [░░┼░░░░░░░░░░░]  0.1%     125    5.4M   $2.73  -15% WARN
Flash 3.8   [███┼██░░░░░░░░] 39.3%  51,704    1.1B  $162.5  +19% WARN
Opus 5.5    [▏░░░░░░░░░░░░░]  0.0%       0       0   $0.00   -3% OK  
Sonnet 5.5  [░┼░░░░░░░░░░░░]  0.0%       0       0   $0.00   -5% OK  
GPT-OSS 120 [▏░░░░░░░░░░░░░]  0.0%       9    264k   $0.00   -2% OK  
BILLING    Hist:$3,810 API | NextRate:$7,599 (+99%) | 20x:6.3x
────────────────────────────────────────────────────────────────────────
WORKSPACES (17)  CHATS  STEPS    TOK   TOK/D   TOK/WK   EST.$  SHARE
1. stem-curricul  75c 64,829    3.8B  71.2M  498.1M  $975.4  21.7%
2. quiet-ui-skil  44c 33,922    2.1B  39.8M  278.7M  $592.2  11.4%
3. mail-triage-u  32c 33,022    2.2B  40.6M  284.0M  $461.5  11.1%
4. home-telemetr   4c 32,348    2.0B  37.7M  263.6M  $496.5  10.8%
5. agy-nexus-mcp  38c 29,751    1.9B  35.8M  250.7M  $508.4  10.0%
6. task-queue-en   1c 25,933  346.9M  6.42M   45.0M   $96.3   8.7%
7. net-topology-   6c 20,803  955.2M  17.7M  123.8M  $219.2   7.0%
8. cloud-gitops-   4c 15,070   52.7M   976k   6.83M   $11.9   5.0%
9. edge-iot-cont   6c 12,250    9.5M   175k   1.23M   $1.51   4.1%
10. agent-harnes  10c 10,643  550.4M  10.2M   71.4M  $144.1   3.6%
11. scratch-prot   8c  7,797  350.8M  6.50M   45.5M  $110.1   2.6%
12. container-gi   4c  4,995  247.0M  4.57M   32.0M   $69.3   1.7%
13. telemetry-in   6c  3,402  206.2M  3.82M   26.7M   $71.4   1.1%
14. edge-proxy-r   2c  2,069  150.5M  2.79M   19.5M   $46.0   0.7%
15. astro-sky-ma   1c  1,126    294k   5.4k     38k   $0.02   0.4%
16. rf-dsp-modem   0c    609   34.6M   641k   4.48M   $4.37   0.2%
17. civic-map-en   1c    177    6.9M   128k    898k   $1.74   0.1%
────────────────────────────────────────────────────────────────────────
SUBAGENTS (24)    RUNS  STEPS    TOK   TOK/D   TOK/WK   EST.$  SHARE
1. argon-sentine 163r 29,283    1.4B  26.7M  186.6M  $518.8  28.2%
2. flash-surgeon 171r 26,606  379.9M  7.04M   49.2M   $52.9  25.6%
3. flash-auditor 214r 16,263  433.2M  8.02M   56.2M   $67.0  15.6%
4. research       96r 11,268  503.8M  9.33M   65.3M  $187.5  10.8%
5. argon-surgeon  14r  8,282  527.2M  9.76M   68.3M  $122.9   8.0%
6. flash-scout    79r  6,680  168.8M  3.13M   21.9M   $26.6   6.4%
7. claude-sentin  31r  2,867  152.0M  2.81M   19.7M   $61.2   2.8%
8. neon-surgeon    9r    755   43.9M   814k   5.69M   $18.8   0.7%
9. carbon-sentin   4r    458   25.4M   471k   3.30M   $7.08   0.4%
10. sprint19-sen   4r    370   10.2M   189k   1.32M   $5.08   0.4%
11. hydrogen-sur  11r    340    5.5M   103k    719k   $2.73   0.3%
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

### 3. `style="quick"` (40-Column Mobile Layout)

```text
════════════════════════════════════════
AGY-NEXUS v4.2.0 // 91d (Nov 25 ◄── Aug 
════════════════════════════════════════
G-20x: 100% [████████┼█] OK | 0x 429s
P-1x : 100% [░┼░░░░░░░░] OK | 100% WkLft
Steps:298.7k | Tools:161.1k | Act:54d
Burn:15.1B | $3,810 | 278.9M/d
Health: Poly 3105s | 94/94 <=500L | up_t
────────────────────────────────────────
HEATMAP (NOW ──► 13w Ago)  │ PEAK & VOL
Mo ██▒▒▓░░·░····           │ Pk: 11/22
Tu ██▓▒▒░░··░···           │ 20,915 stp
We ██▓▓▒·░·░░···           │ Avg:5,532/d
Th ·█▒▒▒░░··▒···           │ Cost: $3,81
Fr ·█▓▓▒▓░·▒▓···           │ Subs : 811r
Sa ·████▓░·▓▒···           │ Tok/d:278.9
Su ·██▓▓▒▒·▓····           │ Tok/w:1.95B
────────────────────────────────────────
8H PACE & STACK (NOW──►OLD) Pk:1.0k
1.0k╷   ██                    ▄      
 511┤▄█ ██  █ ▄               █      
 450┼██─██──█▄█───────█───────█──────
   0╵██▓██  █▒█▄ ▄▄ ░ ░░ ▄▄   ░      
────────────────────────────────────────
MODEL   [PIN]    PCT   TOK  EST.$   DLT
Carbon4 [█┼░░░░░░] 16%  5.2B $1,391  -4
Neon 4  [░┼░░░░░░]  0% 43.7M  $18.8 -10
Argon 4 [██┼█░░░░] 44%  8.6B $2,235 +19
Hydro 4 [░┼░░░░░░]  0%  5.4M  $2.73 -15
Flash38 [█┼█▓░░░░] 39%  1.1B $162.5 +19
Opus5.5 [▏░░░░░░░]  0%     0  $0.00  -3
Sonn5.5 [▏░░░░░░░]  0%     0  $0.00  -5
GPT-120 [▏░░░░░░░]  0%  264k  $0.00  -2
────────────────────────────────────────
WORKSPACES & SUBS  TOK   EST.$  TOK/WK
stem-curriculum  3.8B  $975.4  498.1M
quiet-ui-skills  2.1B  $592.2  278.7M
mail-triage-ui   2.2B  $461.5  284.0M
home-telemetry-  2.0B  $496.5  263.6M
agy-nexus-mcp    1.9B  $508.4  250.7M
task-queue-engi 346.9M   $96.3   45.0M
*argon-sentinel  1.4B  $518.8  186.6M
*flash-surgeon  379.9M   $52.9   49.2M
*flash-auditor  433.2M   $67.0   56.2M
════════════════════════════════════════
```

### 4. `style="rich"` (76-Column Widescreen Layout)

```text
╔══════════════════════════════════════════════════════════════════════════╗
║ ▄▀█ █▀▀ █▄█ ▄▄ █▄░█ █▀▀ ▀▄▀ █░█ █▀   v4.2.0 // RICH TELEMETRY RIG        ║
║ █▀█ █▄█ ░█░ ░░ █░▀█ ██▄ █░█ █▄█ ▄█   WINDOW: 91d (Nov 25 ◄── Aug 27)     ║
╠════════════════════════════════════╦═════════════════════════════════════╣
║ QUOTA & RESETS & POOL SPLIT        │ STEP & TOOL VELOCITY                ║
║ G 5h: 92% lft [██████] 2h52  OK    │ Total : 298,746 steps | 161,110 too ║
║ G Wk: 37% lft [██····] 4d3h  OK    │ Active: 5,532 s/act-d (54d active)  ║
║ Split:100/0 T90/10 P:Stby 429:0    │ Calend: 3,282 s/cal-d (242c, 811r)  ║
╠════════════════════════════════════╬═════════════════════════════════════╣
║ TOKEN BURN & API COST LEDGER       │ MCP WIRE & CLIENT SURFACES          ║
║ Total : ~15.1B | $3,810.06         │ Wire  : 98% <20KB (avg 10.8/33.8KB) ║
║ Daily : 278.9M/d ($70.56/d)        │ Calls : 127 MCP reqs (386k tok)     ║
║ NextRt: $7,598.59 API Forecast     │ Client: Web 58% · Prx 42% · Mob 0%  ║
╠════════════════════════════════════╦═════════════════════════════════════╣
║ VERSION & RELEASE STATUS           │ POLYGLOT & MODULAR CODE HEALTH      ║
║ Installed: v4.2.0 (up_to_date)     │ Poly: 3105s | 94/94 <=500L 0>650L   ║
║ Remote   : v4.2.0                  │ IDE MCP  : agy-praxis-mcp + Serena  ║
╠════════════════════════════════════╩═════════════════════════════════════╣
║ DAILY ACTIVITY MATRIX (NOW: W01 ──► W13)     [·· 0  ░░ <1k  ▒▒ <4k  ██]  ║
║ Wk   W01 W02 W03 W04 W05 W06 W07 W08 W09 W10 W11 W12 W13  ┌─ PEAK DAY ─┐ ║
║ Mon  ███ ███ ▒▒▒ ▒▒▒ ▓▓▓ ░░░ ░░░ ··· ░░░ ··· ··· ··· ···  │ Nov 22     │ ║
║ Tue  ███ ███ ▓▓▓ ▒▒▒ ▒▒▒ ░░░ ░░░ ··· ··· ░░░ ··· ··· ···  │ 20,915 stp │ ║
║ Wed  ███ ███ ▓▓▓ ▓▓▓ ▒▒▒ ··· ░░░ ··· ░░░ ░░░ ··· ··· ···  ├────────────┤ ║
║ Thu  ··· ███ ▒▒▒ ▒▒▒ ▒▒▒ ░░░ ░░░ ··· ··· ▒▒▒ ··· ··· ···  │ Act: 54d   │ ║
║ Fri  ··· ███ ▓▓▓ ▓▓▓ ▒▒▒ ▓▓▓ ░░░ ··· ▒▒▒ ▓▓▓ ··· ··· ···  │ Avg:  5.5k │ ║
║ Sat  ··· ███ ███ ███ ███ ▓▓▓ ░░░ ··· ▓▓▓ ▒▒▒ ··· ··· ···  │ Sub: 811r  │ ║
║ Sun  ··· ███ ███ ▓▓▓ ▓▓▓ ▒▒▒ ▒▒▒ ··· ▓▓▓ ··· ··· ··· ···  └────────────┘ ║
║ Vol  ▃▃▃ ███ ▄▄▄ ▃▃▃ ▃▃▃ ▂▂▂ ▁▁▁ ─── ▁▁▁ ▁▁▁ ─── ─── ───  PeakWk:83.6k   ║
║ Steps 41k 84k 53k 35k 31k 19k  7k  ·  16k 12k  ·   ·   ·                 ║
╠══════════════════════════════════════════════════════════════════════════╣
║ 8H SUB-DAILY HORIZON CURVE & PROJECT STACK (NOW ──► SEP 21)              ║
║ 2.3k ╷   █                                                               ║
║ 1.8k ┤   █                                                               ║
║ 1.3k ┤   █                                                               ║
║  424 ┼   █      █                                                        ║
║  413 ┤▄███▄───▄─██─█───▄─────────▄─█────────────────────▄─────────────   ║
║    0 ╵█▓██▓▄  ███▒▄░   ▒  ▄▄▄▄▄▄ ░ ░ ░   ▄      ▄       ░▄▄     ▄▄▄      ║
║      └─▲───────────▲───────────▲───────────▲───────────▲───────────▲───  ║
║       Nov 25      Nov 12      Oct 29      Oct 16      Oct 02      Sep 21 ║
║       Stack: [█]stem-curricu(22%)  [▓]quiet-ui-ski(11%)  [▒]mail-triage- ║
╠══════════════════════════════════════════════════════════════════════════╣
║ MODEL       [QUOTA ┼ TARGET] SHARE    CALLS     TOK    EST.$  DLT  STAT  ║
║ Carbon 4    [██▓┼░░░░░░░░░░] 16.3%  21,474    5.2B  $1,391   -4% OK      ║
║ Neon 4      [░┼░░░░░░░░░░░░]  0.2%     309   43.7M   $18.8  -10% OK      ║
║ Argon 4     [███┼██▓░░░░░░░] 44.0%  57,776    8.6B  $2,235  +19% WRN     ║
║ Hydrogen 4  [░░┼░░░░░░░░░░░]  0.1%     125    5.4M   $2.73  -15% WRN     ║
║ Flash 3.8   [███┼██░░░░░░░░] 39.3%  51,704    1.1B  $162.5  +19% WRN     ║
║ Opus 5.5    [▏░░░░░░░░░░░░░]  0.0%       0       0   $0.00   -3% OK      ║
║ Sonnet 5.5  [░┼░░░░░░░░░░░░]  0.0%       0       0   $0.00   -5% OK      ║
║ GPT-OSS 120 [▏░░░░░░░░░░░░░]  0.0%       9    264k   $0.00   -2% OK      ║
║ BILLING CMP: Hist $3,810 | NextRate $7,599 (+99%) | 20x 6.3x             ║
╠══════════════════════════════════════════════════════════════════════════╣
║ WORKSPACES (17)  CHATS   STEPS     TOK   TOK/D   EST.$ SHARE GAUGE       ║
║ 1. stem-curricul  75c  64,829    3.8B  71.2M  $975.4 █▍░░░░ 21.7%        ║
║ 2. quiet-ui-skil  44c  33,922    2.1B  39.8M  $592.2 ▍░░░░░ 11.4%        ║
║ 3. mail-triage-u  32c  33,022    2.2B  40.6M  $461.5 ▍░░░░░ 11.1%        ║
║ 4. home-telemetr   4c  32,348    2.0B  37.7M  $496.5 ▍░░░░░ 10.8%        ║
║ 5. agy-nexus-mcp  38c  29,751    1.9B  35.8M  $508.4 ▍░░░░░ 10.0%        ║
║ 6. task-queue-en   1c  25,933  346.9M  6.42M   $96.3 ▍░░░░░  8.7%        ║
║ 7. net-topology-   6c  20,803  955.2M  17.7M  $219.2 ▍░░░░░  7.0%        ║
║ 8. cloud-gitops-   4c  15,070   52.7M   976k   $11.9 ▍░░░░░  5.0%        ║
║ 9. edge-iot-cont   6c  12,250    9.5M   175k   $1.51 ░░░░░░  4.1%        ║
║ 10. agent-harnes  10c  10,643  550.4M  10.2M  $144.1 ░░░░░░  3.6%        ║
║ 11. scratch-prot   8c   7,797  350.8M  6.50M  $110.1 ░░░░░░  2.6%        ║
║ 12. container-gi   4c   4,995  247.0M  4.57M   $69.3 ░░░░░░  1.7%        ║
║ 13. telemetry-in   6c   3,402  206.2M  3.82M   $71.4 ░░░░░░  1.1%        ║
║ 14. edge-proxy-r   2c   2,069  150.5M  2.79M   $46.0 ░░░░░░  0.7%        ║
║ 15. astro-sky-ma   1c   1,126    294k   5.4k   $0.02 ░░░░░░  0.4%        ║
║ 16. rf-dsp-modem   0c     609   34.6M   641k   $4.37 ░░░░░░  0.2%        ║
║ 17. civic-map-en   1c     177    6.9M   128k   $1.74 ░░░░░░  0.1%        ║
╟──────────────────────────────────────────────────────────────────────────╢
║ SUBAGENTS (24)    RUNS   STEPS     TOK   TOK/D   EST.$ SHARE GAUGE       ║
║ 1. argon-sentine 163r  29,283    1.4B  26.7M  $518.8 █▍░░░░ 28.2%        ║
║ 2. flash-surgeon 171r  26,606  379.9M  7.04M   $52.9 █▍░░░░ 25.6%        ║
║ 3. flash-auditor 214r  16,263  433.2M  8.02M   $67.0 ▍░░░░░ 15.6%        ║
║ 4. research       96r  11,268  503.8M  9.33M  $187.5 ▍░░░░░ 10.8%        ║
║ 5. argon-surgeon  14r   8,282  527.2M  9.76M  $122.9 ▍░░░░░  8.0%        ║
║ 6. flash-scout    79r   6,680  168.8M  3.13M   $26.6 ▍░░░░░  6.4%        ║
║ 7. claude-sentin  31r   2,867  152.0M  2.81M   $61.2 ░░░░░░  2.8%        ║
║ 8. neon-surgeon    9r     755   43.9M   814k   $18.8 ░░░░░░  0.7%        ║
║ 9. carbon-sentin   4r     458   25.4M   471k   $7.08 ░░░░░░  0.4%        ║
║ 10. sprint19-sen   4r     370   10.2M   189k   $5.08 ░░░░░░  0.4%        ║
║ 11. hydrogen-sur  11r     340    5.5M   103k   $2.73 ░░░░░░  0.3%        ║
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

</details>

---

## License, Attribution & Security Integrity (`GNU AGPLv3`)

`agy-nexus-mcp` is free and open-source software licensed under the **GNU Affero General Public License v3.0 or later (`AGPL-3.0-or-later`)** — see [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).

- **Always Open & Share-Alike (AGPLv3 §13)**: Anyone running a modified version as a network-accessible MCP or `/web` server must publish the complete corresponding source code under `AGPLv3`.
- **Attribution & Brand Protection (AGPLv3 §7(b), §7(c), §7(e))**: Forks and derivative works must preserve upstream attribution in [`NOTICE`](NOTICE), `/web`, and ASCII outputs, and must clearly mark modifications.
- **Security-Integrity Disclosure (AGPLv3 §7(c), §5(a))**: Any fork that weakens or bypasses `PASS_HASH`, `PATH_SECRET`, LAN-only `agy-praxis-mcp` isolation, path sandboxing, or read-only SQLite isolation must prominently disclose the change.
