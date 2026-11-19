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
   - The tool returns the session's current task state (`task.md`), recent walkthrough highlights (`walkthrough.md`), git working tree status, project workflow baselines (`workflow:baseline`), and recent `visual_artifacts` with **7-day HMAC-signed `/web/media/` HTTPS links** (`604,800` seconds — completely separate from the 30-minute passphrase deadbolt window).
   - `get_session_tree`, `list_saved_sessions`, and the Workspace Explorer tree strictly order **both projects and sessions most-recently-active first** (`last_updated_ts` computed from `max(SQLite last_modified_time, transcript.jsonl mtime, task.md mtime, brain/<cid> mtime)` — preventing brand-new `"0001-01-01..."` chats from dropping and preventing older pinned/running chats or high cumulative-step projects from floating above newer work).
   - `get_session_tree` renders a copy-ready 76-column ASCII hierarchy displaying active sessions and handoff tickets across all four distinct lifecycle states: `[◈ STAGED · UNCLAIMED]`, `[▶ IN-WORK]`, `[✓ COMPLETED]`, and `[⊘ SUPERSEDED -> <id>]`.
   - To keep active sessions prominent and keep every response strictly **under the `20 KB` wire limit** (capping `get_session_tree` inner JSON at `17.5 KB` and Praxis `polyglot_map` at `17.5 KB` with a `directory_summary` and drilldown hint), historical closed (`COMPLETED` and `SUPERSEDED`) tickets attached to each project's tree are bounded at a recent window (latest 4 closed tickets per project, with a `(+N older completed)` note when truncated), while keeping 100% of active `STAGED` and `IN_WORK` tickets visible.
   - Stale synthetic test context slots are automatically pruned from `session_state.json`, Praxis IDE calls (`/praxis/`) classify separately as `Antigravity IDE (Praxis MCP)`, and stateless MCP handshakes (`tools/list`, `initialize`) are separated into `protocol_handshakes` so wire averages reflect real tool calls.
   - Remote version comparison queries both GitHub `/releases/latest` and `/tags`, comparing the installed version against the highest valid semantic version tag so tag-pushed releases compare accurately without false `Staged Locally` warnings.
3. **Concise Mobile Summary**:
   - Gemini delivers a clean, plain-English summary to the user: current task progress, active background jobs, and a 1-tap suggested next step (e.g., *"Check in on the build?"*).

---

## Workflow 2: Plain-Language Stage-Specific Handoffs

### User Goal
The user wants to delegate a specific task to Antigravity without manually micro-managing file names or line numbers. They provide the user goal, the user story, and the target behavior in plain English.

### Why It Matters
Historical audit data shows that over-compressed, line-number-focused handoffs produced a **42.6% rework rate** because agents missed coupled architectural touchpoints. Plain-language handoffs grounded in user goals and end-to-end workflows allow Antigravity to discover and update all coupled files cleanly on the first pass—while matching execution ceremony to task size keeps small 2–3 file fixes fast instead of wrapping them in heavyweight subagent loops.

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
   - Each ticket tracks full lifecycle states (`STAGED`, `IN_WORK`, `COMPLETED`, `SUPERSEDED`).
   - `get_session_tree` and the `/web` Overwatch Dashboard render each state distinctly (`[◈ STAGED · UNCLAIMED]`, `[▶ IN-WORK]`, `[✓ COMPLETED]`, and `[⊘ SUPERSEDED]`), maintaining 100% visibility for active tickets while bounding historical closed tickets.
   - If `resume_headless=True`, Antigravity is woken up immediately; otherwise, the ticket is staged for IDE pickup via `agy-praxis-mcp`.
3. **Proportional Two-Tier Execution Lifecycle (`execution_mode="auto"`)**:
   - **Tier 1 — Surgical Fast-Path (`fast`)**: When `execution_mode="auto"` receives a `release_closeout` or a compact (`< 6,500` chars) `bug_or_visual_fix` that does **not** touch security, auth, deadbolt, middleware, or crypto files, Antigravity inspects target spans directly in Main Chat (`Gemini 4 Carbon`), edits within `<= 500` lines/file, runs `pytest` + `--self-test` directly (skipping multi-subagent `flash-scout` / `flash-surgeon` / 2-sentinel loops unless `4+` modules change), restarts `ag-bridge-mcp`, and captures a quick browser check if UI changed.
   - **Tier 2 — Full 4-Step Multi-Agent + Dual-Review (`plan`)**: Used for `new_project`, `feature_update`, large specifications (`>= 6,500` chars), or **any** security/auth/deadbolt change (`middleware.py`, `bridge_security.py`, `PASS_HASH`, `PATH_SECRET`, `PRAXIS_MCP_TOKEN`, `hmac`, `verify_passphrase`). Antigravity runs full `flash-scout` discovery, targeted Main-Chat/`argon-surgeon`/`flash-surgeon` implementation, `flash-auditor` + adversarial Dual-Review, visual verification, and halts at local staging when `allow_chained_publish=False`.

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
4. **Desktop & Widescreen Postures (`1440px` and `1920px–2560px+` Viewports)**:
   - Analytics expands smoothly up to `1960px` (`min(1960px, calc(100% - 32px))`) so 4-up KPI cards keep footers (including `Gemini Web / Cloud MCP`) crisp on one row, `2026 · 53 WEEKS` displays all 12 calendar month headers (`Jan`..`Dec` without skipping `Jan`), and **Year (`Current` & `Rolling`)** renders `24h daily` base bins across the full active/calendar window aligned identically across all three stacked bar charts.
   - `Pure White` mode pairs `#f8fafc` canvas with crisp `#ffffff` cards, `#f1f5f9` elevated surfaces, and a subtle card shadow (`0 1px 2px rgba(15, 23, 42, 0.04)`) for clear surface separation.

---

## Workflow 4: 2-Pane Workspace Explorer & Visual Artifact Inspection

### User Goal
The user wants to review screenshots generated by each coding session without repo logo clutter, select multiple captures smoothly on phone/foldable/desktop/widescreen monitors, and export crisp, high-resolution batch sheets or archives back into Gemini.

### Why It Matters
Developers need fast visual verification across mobile (`390px`), foldable (`900px`), desktop (`1440px`), and widescreen (`1920px–2560px+`) viewports without floating sidebars, cramped 12-char session titles, tiny checkboxes, cropped thumbnails, or multi-image downscaling mush inside Gemini's vision limit.

### End-to-End Journey
1. **Session-Only Captures vs. Shared Repo Assets (`/web#workspace`)**:
   - Workspace docks edge-to-edge (`max-width: none`) beneath the `42px` topbar so the left navigation tree and `38px` collapsed slim rail stay anchored under `◧` (`#sidebarToggleBtn`) on widescreen displays, and direct `/web#workspace` visits hydrate `#versionLabel` / `#versionDot` immediately from `/web/api/workspace/tree` without stale HTML Service Worker caching.
   - The left tree defaults to `256px–320px` by density (`D4–D1`), supports **drag-to-resize (`220px–480px`, persisted in `localStorage.nexus_tree_width`, double-click to reset)** with a subtle thin scrollbar, renders readable **2-line session titles** alongside `.tree-age-pill` and `🖼 N` capture badges, and keeps session documents/uploads/captures cleanly in the main stage without a redundant inline tree sub-list.
   - Each session resolves its own repository path from `SESSION_STATE` or SQLite (`conversation_summaries.workspace_uris`) rather than borrowing another session's `selected_workspace`.
   - Both **Projects** and **Sessions** in the left tree are strictly sorted **most-recently-active first** (`last_updated_ts`), with compact age pills (`5m`, `4h`, `1d`) shown beside each session title and the newest session (`projects[0].sessions[0]`) auto-selected whenever no explicit `?session=` deep-link or fresher selection is active.
   - The main **Session Captures (`N`)** grid displays only images belonging to that chat: captures inside `brain/<conv_id>/` (up to depth 3) plus uncommitted repository captures owned by the active session or created inside its active timestamp window, sizing cards responsively (`248px` on desktop `>=1100px`, `210px` on tablets, `145px` on phones) with clean `overflow-wrap: anywhere` labels.
   - Committed static repository images (`docs/assets/*`, logos, older non-session assets) stay tucked inside a collapsed **`▸ Shared Repo Assets (M)`** drawer below so they never clutter old chat galleries or inflate `Select All`.
   - All thumbnails use uncropped full-frame `aspect-ratio: 16/10` (`object-fit: contain`) boxes showing natural `WxH` dimensions and 2-line tail-preserving filenames, while the left tree hides empty `Uploads (0)` blocks and shows a subtle `🖼 N` capture badge.
   - When opening `walkthrough.md` or other Markdown artifacts, local `file://` and relative repository/brain image references automatically rewrite into **7-day (`604,800s`) HMAC-signed `/web/media/` links**.
2. **Press-and-Glide Selection & Numbered Badges (`1`, `2`, `3`...)**:
   - Each card has a generous **`40×40px`** corner tap badge (`44×44px` on touch screens) showing a clean empty ring when unselected and its **1-based selection order (`1`, `2`, `3`...)** when selected, plus a subtle top-right zoom button (`⤢`, hover/focus-revealed on fine pointers and translucent on touch) to inspect full-size at any time.
   - On touch devices (phones/foldables), pressing and holding a card for ~260ms triggers haptic feedback and enters sweep mode so gliding a finger across cards checks/unchecks them in-place without scrolling glitches or redraw flicker; on desktop, click-drag marquee or `Shift+Click` works seamlessly. Once at least 1 card is selected, tapping anywhere on a card toggles it, and a persistent sticky toolbar prevents any layout jump (muting `✦ Share Sheets` while disabled at `0` selected).
3. **2 / 4 / 8 High-Resolution Batch Sheets (`3072×3072`) & Exports**:
   - Choose **`Per Sheet`** **`2`**, **`4`** (default), or **`8`** images per stitched sheet directly in the sticky gallery toolbar (saved in `localStorage`).
   - Selecting e.g. 20 captures with `4/sheet` shows `20 selected → 5 sheets (4/sheet)` and builds **5 lossless PNG batch sheets**, each picking the best orientation (`(1×2)` vs `(2×1)`, `(2×2)`, `(2×4)` vs `(4×2)`) to maximize pixel sharpness inside Gemini's **`3072×3072`** vision ceiling without ever upscaling above `1.0×`.
   - Tap **`✦ Share Sheets (K)`** to send sheets via Android's OS Share Sheet directly into Gemini (automatically handling Gemini's 10-file prompt limit with clear batch buttons if `K > 10`, or copying Sheet 1 & opening a preview modal on desktop with individual sheet downloads and an optional `⬇ Sheets ZIP`), **`⬇ Sheets (K)`** to download all `K` individual stitched sheet `.png` files directly into Downloads, **`⬇ PNGs (N)`** to download all `N` selected individual original `.png` captures directly, or **`⬇ ZIP (N)`** when you want an archive of the selected originals.
4. **Full-Screen Lightbox & Collapsible Upload / Zen Mode**:
   - Opening any capture shows `[idx / total]`, `‹ Prev` / `Next ›` buttons, `ArrowLeft`/`ArrowRight` keyboard navigation, horizontal swipe on touch, and an in-modal **`✓ Select`** button synced with the gallery.
   - A compact **`+ Upload / Paste`** button in the session header toggles the drag-and-drop strip open on demand (auto-opening when dragging files onto the pane), and the left navigation collapses (`300px -> 38px -> 0px` Zen Mode) for focused reading.

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
