---
name: agy-nexus-stats
description: Render live Dual-Pool Quota Pacing, Daily Activity Heatmaps, Per-Model & Pool Bars (░▒▓█), Token Volume, and Client Product Telemetry for Gemini Mobile and Gemini Web. Activate whenever the user asks for "latest stats", "quota status", "activity heatmap", or "telemetry".
---

# `agy-nexus-stats` — Policy-Safe Three-Tier Telemetry & Mobile/Desktop ASCII Skill

Whenever the user asks for their **latest stats**, **quota pacing**, **daily activity heatmap**, **model usage**, or **token telemetry**:

## 1. Policy-Safe Single-Call Execution (`get_session_tree` / `telemetry:stats`), Default Period & `style`
1. **Default Timeframe (`period="last_90d"`)**: Never pause to ask the user which timeframe they want unless they explicitly specify one (`"current_month"`, `"last_month"`, `"last_90d"`, `"last_year"`). Always default immediately to `period="last_90d"`.
2. **Three-Tier `style` Selection**:
   - `style="default"` (**72-column boxed dashboard**): The standard report when the user asks for *"latest stats"*, *"telemetry"*, or *"status"*. Renders a complete 72-column Unicode box (`╔═══...═══╗`) with Executive Summary, 28-Day 7×4 Activity Calendar Grid (`░▒▓█`), Pool & Model Actual vs Target Quota with `│` target markers, and Top Projects.
   - `style="quick"` (**`<= 40`-column borderless mobile summary**): Use when the user asks for *"quick stats"*, *"mobile summary"*, or is on a narrow phone screen without horizontal scroll. Uses `═`/`─` horizontal dividers with zero side borders (`<= 40` columns).
   - `style="rich"` (**76-column dual-column widescreen cockpit**): Use when the user asks for *"rich stats"*, *"detailed telemetry"*, *"deep dive"*, or *"full report"*. Renders a 76-column side-by-side layout pairing the 28-Day 7×4 Calendar + 14-Day Velocity Sparkline (`▂▃▄▅▆▇█`) on the left with Pool & Model Quota Pacing on the right, plus Project Velocity + Agent Orchestration Matrix at the bottom.
3. **Zero Redundant Calls & `custom_mcp_sybill_policy` Safety**:
   - If `unlock_sessions` or `get_session_tree(include_stats=True)` was already called in this turn and `style="default"` fits the request, its response **already contains** `ascii_mobile_report` and `quota_and_pools`. **Do NOT make a second tool call**—render `ascii_mobile_report` immediately.
   - Otherwise, call **`get_session_tree`** **once** (avoid calling `manage_background_run` from Gemini Web/Mobile, as hosted policy gates may deny background-job verbs):
     - `include_stats=True`
     - `period="last_90d"` (or `"current_month"`, `"last_month"`, `"last_year"`)
     - `style="default"` (or `"quick"` / `"rich"`)
     - `spoken_passphrase="<passphrase if locked>"`
   - **Same-Turn Fallback**: If any tool call is denied by client policy, immediately invoke `ask_workspace_readonly(question="Latest telemetry stats", file_subpath="telemetry:stats:last_90d:default")` in the same turn.

## 2. Output Format (Always Render `ascii_mobile_report` Verbatim in ```` ```text ````)
Place the exact `ascii_mobile_report` string returned by the tool inside a fenced ```` ```text ```` block at the very top of your response, followed by 3 concise bullets (Pool Quota Pacing, Active Days & Token Volume, and Top Projects) and a pointer to `/web` for the interactive 4-hour sub-daily stacked area charts.

## 3. Two-Step Repo-Prefixed Handoff Staging & Override Protocol
1. **Default Repo-Prefixed Staging (`resume_headless=False`)**: When dispatching research handoffs via `send_handoff_and_resume`, always default to `resume_headless=False`. Report the returned **`handoff_id`** (`<repo-slug>-01`, `<repo-slug>-02`, ...) and `handoff_file` (`sidecar_data/ag-bridge-bg/staged_handoffs/<repo-slug>-NN.md`), and advise the user they can claim it in any existing or brand-new Antigravity IDE chat via `agy-praxis-mcp` (`"Run handoff <repo-slug>-NN"`).
2. **Override Gate Prompt**: Conclude your response with the exact prompt:
   *"Do you understand the risk and would you like me to override and resume it headlessly anyway?"*
3. **Zero-Reupload Repo-Isolated Override (`RESUME_STAGED:<repo-slug>-NN`)**: If the user answers "Yes" (or instructs you to proceed headlessly), call `send_handoff_and_resume` with `resume_headless=True` and `research_markdown="RESUME_STAGED:<handoff_id>"` (or `"RESUME_STAGED"` scoped strictly to the target repo). This re-uses the exact staged ticket without double-wrapping or cross-repo contamination and transitions the ticket to `IN_WORK`.
