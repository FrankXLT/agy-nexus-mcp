# AGY-Nexus `v4.0.2` (`/web` Cutover) — Quiet UI `v9.3.0` Production Field Report

## 1. Executive Summary & Production Cutover

Originally evaluated at `/web/v9`, the **Quiet UI Skills v9.3.0** Studio (`quiet-ui`, `quiet-evidence`, `quiet-bridge`) is now the primary live **`/web`** interface in **`v4.0.2`** (while retaining `/web/v9` route compatibility), grounded strictly in `/web/api/*` 8-model cost ledgers, hourly active-day whiskers, and session artifact contracts without external CDNs, Playwright, or `!important` CSS overrides.

After iterative polish rounds spanning folded phone (`390×844`), Pixel Fold (`820×1080`), desktop (`1440×900`), and widescreen (`2560×1440`), `/web` delivers **Quiet Cockpit** single-row toolbar simplicity, 1-column aligned daily timelines, active-day hourly whisker distributions, responsive wrapped mobile document tabs + `[Captures (N)]` modal, and verified compliance with `audit_quiet_html.py`, `verify_visual_contract.py`, and the public static GitHub Pages showcase (`scripts/build_github_showcase.py`).

---

## 2. Pre-Edit Output Contract & Visual Grammar

- **Mediums**:
  - Primary Shell, Telemetry Overwatch & Workspace Workbench: **`M3` (`data-medium="m3"`)** with compact 4-theme tokens (`white`, `paper`, `dark-paper`, `dark`) and user-selectable density stops (`d2`–`d3`).
  - Session Markdown Reader inside Workspace: **`M2` prose cadence** (`max-inline-size: 72ch`, `.booktabs` tables, GFM task-lists with un-bulleted checkboxes, `Rendered | Raw | Print`) transitioning cleanly to crisp light archival ink under `@media print`.
- **Navigation Grammar, Shared Rail & Invariance (`0px` Horizontal Shift)**:
  - Sticky topbar keeping `Analytics | Workspace <N>` accessible across every viewport (`390px`–`2560px`), collapsing `AGY-NEXUS` text cleanly to an `18×18px` brand icon below `460px`. Zero conditional controls live inside `.v9-topbar-left`.
  - `#v9NavRail` (`Ctrl+B` / `[◧]`) opens cleanly as an opaque drawer over `#v9WsBackdrop`, linking `5`-session capped project trees and unclaimed `STAGED` handoffs directly to `?project=<id>#analytics` and `#workspace`.
  - Analytics centers inside a `1480px` stage cap with `[ ‹ | Period · Date Span ▾ | › ]` and `[Steps | Tokens | $ Cost]`.
  - Workspace mounts `.v9-ws-context`, full-row `< 760px` `.md` tabs (`task.md`, `plan.md`, `walkthrough.md`, `handoff.md`), `[Raw]` + print, responsive `100%` / `64%/36%` / `60%/40%` panes, `[Captures (N)]` mobile modal, and `[All] [Compare] [PNGs] [More ▾]` gallery toolbar.
- **Concentric Corner Radii & Zero Pictographic Emojis**:
  - Cards (`--radius-card`) -> inner panels/thumbs (`--radius-inner`) -> segmented buttons/badges (`--radius-sm` / `--radius-xs`). Zero UI chrome emojis; crisp inline `<svg stroke="currentColor">` icons (`12–14px`) only.

---

## 3. Data-to-Widget Binding Map (`v4.0.2`)

| Panel / Widget | Source Endpoints & Fields | Rendering & Honesty Contract |
| :--- | :--- | :--- |
| **Compound Period Stepper & 6-Preset Menu** | `stats.{period}`, `DEMO_SNAPSHOT.bundles` | `[ ‹ | Period · Date Span ▾ | › ]` + all 6 presets (`MTD`, `QTD`, `YTD`, `30d`, `90d`, `52w`) + `Last Month` enabled in both live & `?demo=1`/static showcase (`V9.DemoAdapter.isPresetAvailable`). |
| **KPI Cards (Throughput, Tokens & $, Pools)** | `kpis`, `quota_and_pools`, `model_usage_vs_target`, `partner_weekly_pacing` | Trackless Step/Token/$ KPIs; Google `20x` call share vs Partner weekly pacing (`14.28%/d` ceiling). |
| **Activity Heatmap** | `heatmap_series[]` | Trailing `52w`/`53w` (`26w` mobile) full-width grid, uniform `P25/P50/P75` quartiles (`Steps`/`Tokens`/`$ Cost`), desaturated `.is-out`, `1st`-of-month headers. |
| **Daily Spine 1–3 (`Steps / Tokens / $ Cost`)** | `model_series`, `subagent_series`, `project_hierarchy`, `cost_ledger` | Full 8-model classification + `Est. $` & `Avg Tok/Run` `.booktabs` tables (`0px` overflow `< 640px`). |
| **Secondary Pair Left: Activity by Hour of Day** | `hourly_whiskers.{hours,min,avg,max,last_24h}` | Active-day `Min / Avg / Max` whisker plot + `Last 24h` dot across `Steps`, `Tokens`, & `$ Cost`. |
| **Secondary Pair Right: Subscription Break-Even** | `billing_comparison.{historical_usd,forecast_usd,tiers}`, `model_drift_status` | API retail equivalent vs Dec Rate Forecast, cache split, `Plus / Pro / Ultra 5x / Ultra 20x` value multipliers, and quiet `01:45 AM` drift badge. |
| **MCP Wire & Code Health** | `wire_telemetry`, `code_health.{version,modular_hygiene,polyglot_health}` | Scatter vs `20 KB cap` + collapsed `<= 500L` watchlist (covering `src/`, `host_bridge/`, `web/`, and `web/v9/`). |
| **Workspace Workbench** | `/web/api/workspace/*` & `DEMO_SNAPSHOT.demo_sessions` | Responsive panes, bundled showcase docs with safe `./` relative asset resolution, and `"Read-only interactive showcase"` upload guard. |

---

## 4. Offline Vendoring & Public GitHub Pages Showcase (`gh-pages`)

- Zero external CDNs: all styles, ECharts `v5.6.0`, and Quiet UI `v9.3.0` adapters load from `/web/v9/vendor/` (cached in `web/sw.js` `CACHE_NAME = "agy-nexus-v4.0.2"`) or relative `./v9/vendor/` in the static GitHub Pages showcase (`build/gh-pages/` via `scripts/build_github_showcase.py`).
- All showcase outputs pass PNG chunk metadata scrubbing (`tEXt`/`iTXt`/`zTXt`/`eXIf`/`tIME` removed) and automated fail-closed `scan_showcase_privacy()` (`0` private slugs/domains/LAN IPs/UUIDs).

---

## 5. Verification Summary

- `pytest` regression suite (`test_v300`..`test_v327` + `test_v400_cutover_and_showcase.py`) + `ag_bridge.py --self-test` + `agy_nexus.tools_praxis --self-test` + `sync_agents.py --check`.
- Quiet UI `v9.3.0` auditor (`audit_quiet_html.py` static + `--cdp` across live `/web?demo=1` and static `build/gh-pages/`) and `verify_visual_contract.py` (`390×844`, `820×1080`, `1440×900`, `paired_1904x971`): **`0` errors**.
