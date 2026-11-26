# AGY-Nexus `v4.2.0` (`/web` & Three-Route Project Site) — Quiet UI `v9.3.0` Field Report

## 1. Executive Summary & Production Parity

Originally introduced at `/web/v9`, the **Quiet UI Skills v9.3.0** Studio (`quiet-ui`, `quiet-evidence`, `quiet-bridge`) powers both the live **`/web`** dashboard in **`v4.2.0`** (retaining `/web/v9` route compatibility) and the **Three-Route Public Project Site** (`./`, `./demo/`, and `./docs/` under `build/gh-pages/`). Inside `/web` and `./demo/`, everything runs directly from `/web/api/*` 8-model cost ledgers, hourly active-day whiskers, multi-column sortable tables, desktop pinned rail navigation, and session artifact views with zero external CDNs, Playwright, or `!important` CSS overrides.

Tested across folded phone (`390×844`), Pixel Fold (`820×1080`), desktop (`1440×900`), and widescreen (`2560×1440`), `/web` and `./demo/` share single-row toolbar simplicity, 1-column aligned daily timelines, active-day hourly whisker charts, wrapped mobile document tabs + `[Captures (N)]` modal, and verified compliance with `audit_quiet_html.py`, `verify_visual_contract.py`, and `scripts/build_github_showcase.py`.

---

## 2. Pre-Edit Output Contract & Visual Grammar

- **Mediums**:
  - Primary Shell, Telemetry Overwatch & Workspace Workbench: **`M3` (`data-medium="m3"`)** with compact 4-theme tokens (`white`, `paper`, `dark-paper`, `dark`) and selectable density stops (`d2`–`d3`).
  - Session Markdown Reader inside Workspace: **`M2` prose cadence** (`max-inline-size: 72ch`, `.booktabs` tables, GFM task-lists with un-bulleted checkboxes, `Rendered | Raw | Print`) switching cleanly to crisp light archival ink under `@media print`.
- **Navigation Grammar, Shared Rail & Invariance (`0px` Horizontal Shift)**:
  - Sticky topbar keeping `Analytics | Workspace <N>` reachable across every viewport (`390px`–`2560px`), collapsing `AGY-NEXUS` text cleanly to an `18×18px` brand icon below `460px`. Zero conditional controls live inside `.v9-topbar-left`.
  - `#v9NavRail` (`Ctrl+B` / `#v9MenuBtn`) opens as an opaque modal drawer (`☰`) or pins inline (`280px` grid on `>= 1100px`, switching `#v9MenuBtn` to `◧`) via `localStorage.nexus_v9_rail_pinned`, linking `5`-session capped project trees and unclaimed `STAGED` handoffs directly to `?project=<id>#analytics` and `#workspace`.
  - Analytics centers inside a `1480px` stage cap with `[ ‹ | Period · Date Span ▾ | › ]` and `[Steps | Tokens | $ Cost]`.
  - Workspace mounts `.v9-ws-context`, full-row `< 760px` `.md` tabs (`task.md`, `plan.md`, `walkthrough.md`, `handoff.md`), `[Raw]` + print, responsive `100%` / `64%/36%` / `60%/40%` panes, `[Captures (N)]` mobile modal, and `[All] [Compare] [PNGs] [More ▾]` gallery toolbar.
- **Concentric Corner Radii & Zero Pictographic Emojis**:
  - Cards (`--radius-card`) -> inner panels/thumbs (`--radius-inner`) -> segmented buttons/badges (`--radius-sm` / `--radius-xs`). Zero UI chrome emojis; crisp inline `<svg stroke="currentColor">` icons (`12–14px`) only.

---

## 3. Data-to-Widget Binding Map (`v4.2.0`)

| Panel / Widget | Source Endpoints & Fields | Rendering & Honesty Contract |
| :--- | :--- | :--- |
| **Compound Period Stepper & 6-Preset Menu** | `stats.{period}`, `DEMO_SNAPSHOT.bundles` | `[ ‹ | Period · Date Span ▾ | › ]` + all 6 presets (`MTD`, `QTD`, `YTD`, `30d`, `90d`, `52w`) + `Last Month` enabled in live `/web`, `?demo=1`, and static `./demo/` (`V9.DemoAdapter.isPresetAvailable`). |
| **KPI Cards (Throughput, Tokens & $, Quota & Resets)** | `kpis`, `quota_and_resets`, `quota_and_pools`, `model_usage_vs_target` | Trackless Step/Token/$ KPIs alongside live `Quota & Resets (% left)` with reset countdowns and `Pool Split` across Google `20x` vs Partner `1x`. |
| **Activity Heatmap** | `heatmap_series[]` | Trailing `52w`/`53w` (`26w` mobile) full-width grid, uniform `P25/P50/P75` quartiles (`Steps`/`Tokens`/`$ Cost`), desaturated `.is-out`, `1st`-of-month headers. |
| **Daily Spine 1–3 (`Steps / Tokens / $ Cost`)** | `model_series`, `subagent_series`, `project_hierarchy`, `cost_ledger` | Full 8-model classification + sortable `Age`, `Est. $`, `Tokens`, `Steps`, `Share`, & `Avg Tok/Run` `.booktabs` tables (`0px` overflow `< 640px`, preserved ECharts swatch colors). |
| **Secondary Pair Left: Activity by Hour of Day** | `hourly_whiskers.{hours,min,avg,max,last_24h}` | Active-day `Min / Avg / Max` whisker plot + `Last 24h` dot across `Steps`, `Tokens`, & `$ Cost`. |
| **Secondary Pair Right: Subscription Break-Even** | `billing_comparison.{historical_usd,forecast_usd,tiers}`, `model_drift_status` | API retail equivalent vs Dec Rate Forecast, cache split, `Plus / Pro / Ultra 5x / Ultra 20x` value multipliers, and quiet `01:45 AM` drift badge. |
| **MCP Wire & Code Health** | `wire_telemetry`, `code_health.{version,modular_hygiene,polyglot_health}` | Scatter vs `20 KB cap` + collapsed `<= 500L` watchlist (covering `src/`, `host_bridge/`, `web/`, and `web/v9/`). |
| **Workspace Workbench** | `/web/api/workspace/*` & `DEMO_SNAPSHOT.demo_sessions` | Responsive panes, bundled showcase docs with safe `./` relative asset resolution, and `"Read-only interactive showcase"` upload guard. |

---

## 4. Offline Vendoring & Three-Route Public Project Site (`gh-pages`)

- Zero-CDN Studio runtime: all `/web` and `./demo/` styles, ECharts `v5.6.0`, Quiet UI `v9.3.0` adapters, and client scripts load strictly from `/web/v9/vendor/` (cached in `web/sw.js` `CACHE_NAME = "agy-nexus-v4.2.0"`) or relative `./v9/vendor/` inside `build/gh-pages/` via `scripts/build_github_showcase.py`; public `./` and `./docs/` pages additionally include `referrerpolicy="no-referrer"` editorial font stylesheets (`Newsreader`, `Inter`, `JetBrains Mono`) with full local system font fallbacks.
- All showcase outputs pass PNG chunk metadata scrubbing (`tEXt`/`iTXt`/`zTXt`/`eXIf`/`tIME` removed) and automated fail-closed `scan_showcase_privacy()` (`0` private slugs/domains/LAN IPs/UUIDs).

---

## 5. Verification Summary

- `pytest` regression suite + `ag_bridge.py --self-test` + `agy_nexus.tools_praxis --self-test` + `sync_agents.py --check`.
- Quiet UI `v9.3.0` auditor (`audit_quiet_html.py` static + `--cdp` across live `/web?demo=1` and static `build/gh-pages/`) and `verify_visual_contract.py` (`390×844`, `820×1080`, `1440×900`, `paired_1904x971`): **`0` errors**.
