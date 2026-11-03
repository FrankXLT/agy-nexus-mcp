---
name: agy-nexus-stats
description: Render live Dual-Pool Quota Pacing, Daily Activity Heatmaps, Per-Model & Pool Bars (░▒▓█), Token Volume, and Client Product Telemetry for Gemini Mobile and Gemini Web. Activate whenever the user asks for "latest stats", "quota status", "activity heatmap", or "telemetry".
---

# `agy-nexus-stats` — Three-Tier Telemetry & Mobile/Desktop ASCII Skill

Whenever the user asks for their **latest stats**, **quota pacing**, **daily activity heatmap**, **model usage**, or **token telemetry**:

## 1. Single-Call Execution, Default Period & Three-Tier `style` Selection
1. **Default Timeframe (`period="last_90d"`)**: Never pause to ask the user which timeframe they want unless they explicitly specify one (`"current_month"`, `"last_month"`, `"last_90d"`, `"last_year"`). Always default immediately to `period="last_90d"`.
2. **Three-Tier `style` Selection**:
   - `style="default"` (**72-column boxed dashboard**): The standard report when the user asks for *"latest stats"*, *"telemetry"*, or *"status"*. Renders a complete 72-column Unicode box (`╔═══...═══╗`) with Executive Summary, 28-Day 7×4 Activity Calendar Grid (`░▒▓█`), Pool & Model Actual vs Target Quota with `│` target markers, and Top Projects.
   - `style="quick"` (**`<= 40`-column borderless mobile summary**): Use when the user asks for *"quick stats"*, *"mobile summary"*, or is on a narrow phone screen without horizontal scroll. Uses `═`/`─` horizontal dividers with zero side borders (`<= 40` columns).
   - `style="rich"` (**76-column dual-column widescreen cockpit**): Use when the user asks for *"rich stats"*, *"detailed telemetry"*, *"deep dive"*, or *"full report"*. Renders a 76-column side-by-side layout pairing the 28-Day 7×4 Calendar + 14-Day Velocity Sparkline (`▂▃▄▅▆▇█`) on the left with Pool & Model Quota Pacing on the right, plus Project Velocity + Agent Orchestration Matrix at the bottom.
3. **Zero Redundant Calls**:
   - If `unlock_sessions` or `manage_background_run(action="status")` was already called in this turn and `style="default"` fits the request, its response **already contains** `ascii_mobile_report` and `quota_and_pools`. **Do NOT make a second tool call**—render `ascii_mobile_report` immediately.
   - Otherwise, call `manage_background_run` **once**:
     - `action="stats"`
     - `period="last_90d"` (or `"current_month"`, `"last_month"`, `"last_year"`)
     - `style="default"` (or `"quick"` / `"rich"`)
     - `client_product="Gemini Mobile"` (if on mobile/voice) or `"Gemini Web"` (if on web)
     - `spoken_passphrase="<passphrase if locked>"`

## 2. Output Format (Always Render `ascii_mobile_report` Verbatim in ```` ```text ````)
Place the exact `ascii_mobile_report` string returned by the tool inside a fenced ```` ```text ```` block at the very top of your response, followed by 3 concise bullets (Pool Quota Pacing, Active Days & Token Volume, and Top Projects) and a pointer to `/web` for the interactive 4-hour sub-daily stacked area charts.
