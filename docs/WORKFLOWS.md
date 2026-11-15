# AGY-Nexus MCP — User Workflows & Operational Baseline

This document defines the primary user journeys, workflows, and operational ergonomics for **AGY-Nexus MCP** (`agy-nexus-mcp`). It provides a plain-language baseline so that AI coding assistants (Gemini Web/Mobile, Antigravity, and subagents) understand **who the user is, what goals they are pursuing, why specific operational safeguards exist, and how end-to-end multi-agent orchestration flows across devices**.

---

## The User & Orchestration Model

- **The User**: A lead developer and systems architect managing multiple software projects across local and network-hosted environments. The user frequently monitors progress, reviews visual changes, and directs agent swarms from a mobile device (e.g. Google Pixel Fold in both folded ~390px phone and unfolded ~900px tablet postures) or desktop Chrome.
- **The Orchestrator (Google Gemini)**: Receives user voice dictation, chat messages, or visual critiques, inspects live project and session states via read-only MCP tools, and stages or executes structured handoffs.
- **The Execution Engine (Google Antigravity)**: Headless or interactive multi-agent developer environment running locally. Executes scoped tasks using an 8-agent orthogonal roster (Carbon 4 Main-Chat, Argon 4 Architects/Surgeons, Flash Scouts/Auditors, and Claude specialists) following strict verification gates and modular architecture invariants.

---

## Workflow 1: Voice & Mobile Session Check-Ins & Read-Only Inspection

### User Goal
The user is away from the keyboard or multi-tasking on mobile. They speak or type a brief query to Gemini (e.g., *"How is the Chem Sprint build doing?"* or *"What did Antigravity do in the last session?"*) and want an immediate, accurate status summary without accidental code changes or long waits.

### Why It Matters
Directing agents from mobile requires zero-risk read operations. If Gemini were to automatically trigger edits or restart builds during a routine status query, it could interrupt ongoing compiles or overwrite uncommitted work.

### End-to-End Journey
1. **Passphrase & Deadbolt Gate**:
   - For secure environments, the bridge requires an inline voice passphrase or active session unlock.
   - When unlocked, a 30-minute sliding-TTL deadbolt remains active while the user interacts.
2. **Read-Only Inspection**:
   - Gemini calls `load_session_into_gemini(conv_id=...)` or `get_session_tree(include_stats=True)`.
   - The tool returns the session's current task state (`task.md`), recent walkthrough highlights (`walkthrough.md`), git working tree status, and project workflow baselines (`workflow:baseline`).
3. **Concise Mobile Summary**:
   - Gemini delivers a clean, plain-English summary to the user: current task progress, active background jobs, and a 1-tap suggested next step (e.g., *"Check in on the build?"*).

---

## Workflow 2: Plain-Language Stage-Specific Handoffs

### User Goal
The user wants to delegate a specific task to Antigravity without manually micro-managing file names or line numbers. They provide the user goal, the user story, and the target behavior in plain English.

### Why It Matters
Historical audit data shows that over-compressed, line-number-focused handoffs produced a **42.6% rework rate** because agents missed coupled architectural touchpoints. Plain-language handoffs grounded in user goals and end-to-end workflows allow Antigravity to discover and update all coupled files cleanly on the first pass.

### Handoff Modes & When to Use Them
AGY-Nexus MCP provides four primary handoff modes:

| Mode | Purpose | Recommended Tone & Content |
| :--- | :--- | :--- |
| `feature_update` *(Default)* | Adding capabilities or refining behavior | State the user goal, workflow impact, key components, and expected outcome. |
| `new_project` | Standing up a new repository or package | State the project mission, target directory, architecture guidelines, and first milestone. |
| `bug_or_visual_fix` | Fixing runtime defects or UI styling regressions | State what broke, how the user observed it (e.g., folded viewport, broken click), the desired behavior, and verification steps. |
| `release_closeout` | Finalizing a sprint, tagging, and retiring a session | State clean tree requirement, test suite passes, changelog updates, and version tags. |

### End-to-End Journey
1. **Gemini Composes Handoff**:
   - Gemini structures the handoff with clear sections: `# User Goal`, `# Workflow & Why It Matters`, and `# Architectural Guidance`.
   - Tool `send_handoff_and_resume` checks handoff quality (`evaluate_handoff_quality`), providing non-blocking advisories if user goals are missing.
2. **Ticket Staging & Claiming**:
   - A sequential ticket is registered in the queue (`<repo-slug>-01`, `<repo-slug>-02`...).
   - If `resume_headless=True`, Antigravity is woken up immediately; otherwise, the ticket is staged for IDE pickup via `agy-praxis-mcp`.
3. **Execution Lifecycle**:
   - Antigravity scouts semantic outlines with Polyglot/Praxis, implements changes within file size budgets (`<= 500 lines`), audits with `flash-auditor` or dual-review, and halts at local staging (`allow_chained_publish=False`) for review.

---

## Workflow 3: Overwatch Analytics Across Form Factors

### User Goal
The user navigates to the Overwatch Web Dashboard (`/web`) to monitor quota consumption, subagent velocity, daily activity patterns, and project health across diverse screen sizes.

### Why It Matters
The dashboard must provide responsive, ergonomic visibility whether the user opens it on a narrow smartphone, a square foldable tablet, or an ultra-wide desktop monitor.

### End-to-End Form Factor Postures
1. **Pre-Unlock State**:
   - When the bridge deadbolt is locked, `/web` displays a clean, distraction-free passphrase challenge without broken UI controls, partial graphs, or layout shifts.
2. **Folded Phone Posture (~390px Viewport)**:
   - `#workspace` stays on an invariant single `41px` topbar row while `#analytics` uses a clean 2-row header (with time-span and metric controls on the second row).
   - KPIs adapt to a readable 2×2 grid.
   - The activity heatmap automatically switches to a Monday-aligned **26-week** view so cells remain comfortably tappable without horizontal scrollbars.
3. **Unfolded Tablet Posture (~900px Foldable)**:
   - KPIs spread to a 4-across grid.
   - The full 53-week Mon–Sun activity heatmap uses the unified 5-level single-hue `#2563eb` blue scale across all four themes (`Pure White`, `Warm Paper`, `Dark Paper`, `Obsidian`) with zero horizontal scrollbars.
4. **Desktop Posture (1440px+ Viewport)**:
   - Full wide-screen layout with side-by-side time series charts, project session hierarchies, and real-time code health watchlists.

---

## Workflow 4: 2-Pane Workspace Explorer & Visual Artifact Inspection

### User Goal
The user wants to review visual artifacts (screenshots, diagrams, exported reports) generated by Antigravity during a build, compare visual diffs, and export contact sheets or bundles to Gemini.

### Why It Matters
Developers need immediate verification that UI changes look correct before approving releases. Antigravity's visual contract requires desktop and mobile verification screenshots for all frontend changes.

### End-to-End Journey
1. **Browsing Sessions & Artifacts**:
   - The user opens `/web#workspace` to access the 2-Pane Workspace Explorer.
   - All frontend assets are served with full offline PWA parity (`PWA_ASSETS` and Service Worker caching).
2. **Multi-Select & Contact Sheets**:
   - The user selects multiple screenshots using Shift+Click or marquee drag.
   - They can instantly generate a client-side `<canvas>` Contact Sheet, download a streaming `.zip` archive, or trigger the Web Share API (`shareToGemini`) to send images directly back into the chat session.
3. **Zen Focus Mode**:
   - On compact screens or during focused reviews, the left file navigation collapses (`240px -> 38px -> 0px`), maximizing screen space for markdown rendering and image lightbox comparisons.

---

## Workflow 5: In-Place Release Closeout, Worktree Cleanup & Ticket Retirement

### User Goal
A feature sprint or bugfix is verified and complete. The user instructs Gemini to close out the session, run final audits, commit clean changes, and retire the session.

### Why It Matters
Unclosed sessions leave stale Git worktrees, lingering temporary files, and tickets stuck in `IN_WORK` status, which clutters the handoff queue and confuses subsequent session handoffs.

### End-to-End Journey
1. **Verification & Audit**:
   - The test suite passes (`pytest`, smoke tests), and code health conforms to modular standards (`<= 500 lines` target, `650` ceiling, functions `<= 100` lines).
2. **Closeout Handoff (`release_closeout`)**:
   - Gemini sends a `release_closeout` handoff or passes `retire_session=True`.
3. **In-Place Retirement & Auto-Reconciliation**:
   - Antigravity prunes stale Git worktrees (`git worktree prune`) and writes `brain/<conv_id>/RETIRED.json` recording the final commit SHA and timestamp.
   - `reconcile_completed_tickets` detects `RETIRED.json` and automatically transitions any associated `IN_WORK` or `STAGED` tickets to `COMPLETED`.
4. **Next Session Continuity**:
   - When a new session rolls over, `extract_prior_session_baton` extracts the prior user goal, task highlights, and Git status, ensuring seamless cross-session memory.
