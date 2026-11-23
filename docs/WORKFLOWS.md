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
   - To keep active sessions prominent and keep every response strictly **under the `20 KB` wire limit** (`<= 18.5 KB` inner UTF-8 / `<= 19.8 KB` JSON-escaped outer wire budget across `ask_workspace_readonly`, `inspect_git_diff`, `load_session_into_gemini`, and `list_models_and_agents`, capping `get_session_tree` inner JSON at `17.5 KB` and Praxis `polyglot_map` at `17.5 KB` with a `directory_summary` and drilldown hint, and compacting `tools/list` to `<= 8.6 KB`), historical closed (`COMPLETED` and `SUPERSEDED`) tickets attached to each project's tree are bounded at a recent window (latest 4 closed tickets per project, with a `(+N older completed)` note when truncated), while keeping 100% of active `STAGED` and `IN_WORK` tickets visible.
   - **Cloud MCP Header-Only Visual Fast Path (`inspect_visual_artifacts`)**: When `inspect_visual_artifacts` is called from Cloud MCP / Gemini Mobile (`region="full"`, `include_thumbnails=False`), the server skips WebP pixel encoding and reads PNG/JPEG/WebP/GIF headers in `<2ms` (`read_image_dimensions_fast`), returning `<4 KB` JSON (`cloud_fast_path=True`, `returned_images=0`, `original_px`, and **7-day** signed `/web/media/` URLs) since cloud adapters strip binary `ImageContent` blocks on ingress. Local callers, region crops (`region="top"|"middle"|"bottom"|"x,y,w,h"`), and `include_thumbnails=True` still receive budgeted WebP `ImageContent` thumbnails.
   - Stale synthetic test context slots are automatically pruned from `session_state.json`, Praxis IDE calls (`/praxis/`) classify separately as `Antigravity IDE (Praxis MCP)`, and stateless MCP handshakes (`tools/list`, `initialize`) are separated into `protocol_handshakes` so wire averages reflect real tool calls.
   - Remote version comparison queries both GitHub `/releases/latest` and `/tags`, comparing the installed version against the highest valid semantic version tag so tag-pushed releases compare accurately without false `Staged Locally` warnings.
    - **Deadbolt-Safe Nightly Model & Pricing Status (`style="ascii"`)**: Scheduled status pulls can invoke `list_models_and_agents(style="ascii", include_skills=False, include_rules=False)` or `manage_background_run(action="models", style="ascii")` without unlocking the Deadbolt to receive a fixed `76`-column ASCII status report covering all 8 canonical models (`Carbon 4`, `Neon 4`, `Argon 4`, `Hydrogen 4`, `Flash 3.8`, `Opus 5.5`, `Sonnet 5.5`, `GPT-OSS 120B`), effective-dated micro-USD rates, subagent mappings, and automated `01:45 AM` Language Server + API pricing drift status (`scripts/check_model_drift.py` -> `model_drift_status.json`), while `include_skills=True`, `include_rules=True`, and `style="json"` stay behind the Deadbolt gate. Bundled agent frontmatter (`agents/*.md`) stays synced via `scripts/sync_agents.py --check`.
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
3. **Proportional Two-Tier Execution Lifecycle & `plan` Coercion (`execution_mode="auto"`)**:
   - **Tier 1 — Surgical Fast-Path (`fast`)**: When `execution_mode="auto"` receives a `release_closeout`, a compact (`< 6,500` chars) `bug_or_visual_fix` that does **not** touch security, auth, deadbolt, middleware, or crypto files, or a compact (`<= 2,200` chars, `< 3` deliverables) `allow_chained_publish=True, resume_headless=True` non-security run, Antigravity inspects target spans directly in Main Chat (`Gemini 4 Carbon`), edits within `<= 500` lines/file, runs `pytest` + `--self-test` directly (skipping multi-subagent `flash-scout` / `flash-surgeon` / 2-sentinel loops unless `4+` modules change), restarts `ag-bridge-mcp`, and captures a quick browser check if UI changed.
   - **Tier 2 — Full 4-Step Multi-Agent + Dual-Review (`plan`)**: Used for `new_project`, multi-deliverable/complex `feature_update` (`>= 3` deliverables or `> 2,200` chars), large specifications (`>= 6,500` chars), or **any** security/auth/deadbolt change (`middleware.py`, `bridge_security.py`, `PASS_HASH`, `PATH_SECRET`, `PRAXIS_MCP_TOKEN`, `hmac`, `verify_passphrase`). Even if `execution_mode="fast"` is passed explicitly on `new_project` or a heavy/multi-deliverable `feature_update`, `resolve_execution_mode_with_reason()` automatically coerces it back to `"plan"` (`coerced_from_fast=True`) so complex architectures never bypass discovery, `argon-surgeon`/`flash-surgeon`, `flash-auditor`, and adversarial Dual-Review. Antigravity halts at local staging when `allow_chained_publish=False`.

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
   - When `handoff_mode="release_closeout"`, `resume_headless=True`, and `retire_session=True` are combined, `retire_after_closeout=True` **defers** writing `RETIRED.json` so the active session is not prematurely locked mid-run; the closeout instructions direct Antigravity to call `record_session_retirement(..., final_commit_sha=<HEAD_SHA>)` only after `git commit` and `git push` succeed. Non-headless `retire_session=True` calls continue writing `RETIRED.json` immediately.
3. **In-Place Retirement & Auto-Reconciliation**:
   - Antigravity prunes stale Git worktrees (`git worktree prune`) and writes `brain/<conv_id>/RETIRED.json` recording the final commit SHA and timestamp.
   - `reconcile_completed_tickets` detects `RETIRED.json` and automatically transitions any associated `IN_WORK` or `STAGED` tickets to `COMPLETED`.
4. **Next Session Continuity**:
   - When a new session rolls over, `extract_prior_session_baton` extracts the prior user goal, task highlights, and Git status, ensuring seamless cross-session memory.

---

## Workflow 6: Quiet UI `v9.3.0` Live `/web` Studio & Interactive GitHub Pages Showcase (`v4.0.4`)

### User Goal
Serve **Quiet UI Skills v9.3.0** directly as the primary live `/web` dashboard (preserving `/web/v9` compatibility) backed by live workstation 8-model telemetry, effective-dated micro-USD ledgers, accurate 4-tier subscription break-even comparisons, multi-column sortable tables, optional desktop sidebar pinning, and a zero-leak **GitHub Pages Interactive Showcase** (`gh-pages`).

### Architectural Invariants
1. **Primary Live `/web` Cutover, Navbar Invariance & PWA Cache Integrity**:
   - `/web`, `/web/index.html`, `/web/v9`, and `/web/v9/index.html` serve Quiet UI `v9.3.0` HTML directly with `Cache-Control: no-store, no-cache, must-revalidate` in `src/agy_nexus/web_routes.py`.
   - Every active asset (`web/v9/*.{css,js}`, `web/v9/vendor/*`, `demo_snapshot.js`, `gallery_select.js`, `sheet_builder.js`, `manifest.webmanifest`, `icon*`, and `demo_thumb_*.png`) is registered in `PWA_ASSETS` and `web/sw.js` (`CACHE_NAME = "agy-nexus-v4.0.4"`), matching both `/web/` and `/{PATH_SECRET}/web/`.
   - Sticky topbar brand/tab X-coordinates remain identical (`0px` shift) between `#analytics` and `#workspace` (`50px` single row `>= 680px`; compact `<= 64px` 2-row sticky header `< 680px`), keeping `#v9MenuBtn`, `AGY-NEXUS`, `Analytics | Workspace <N>`, active scope chip, compound period picker, and `[Steps | Tokens | $ Cost]` (or Workspace layout switches + `Upload`, hiding `Split`/`Captures` `< 760px`) pinned on scroll.
   - **Desktop Rail Pinning & Dynamic Menu Affordance (`localStorage.nexus_v9_rail_pinned`)**: On desktop/widescreen (`>= 1100px`), `#v9RailPinBtn` inside `.v9-rail-hdr` pins `#v9NavRail` inline inside a `280px minmax(0, 1fr)` grid (`#v9AppShell.is-rail-pinned`) so switching across `All Projects`, project `Analytics`, and `Workspace` sessions keeps the rail open while realigning ECharts (`V9.Charts.scheduleRealign`). When unpinned or `< 1100px` mobile/tablet, `#v9NavRail` acts as a modal overlay drawer (`role="dialog"`) over `#v9WsBackdrop` and auto-closes on selection; `#v9MenuBtn` displays a **`☰` hamburger** icon when unpinned / `< 1100px` and switches to **`◧` docked-panel** when pinned on desktop.
2. **Multi-Column Sortable Analytics Tables, Activity Heatmap & Full-Width 52w Strip**:
   - **Multi-Column Table Sorting (`web/v9/v9_table_sort.js`)**: `Top Projects`, `Project Sessions`, `Model Workload`, and `Subagent Workload` expose accessible `<th scope="col">` sort `<button>` controls driving `aria-sort="ascending|descending"` on the active `<th>` only (via CSS-driven SVG indicators) and preserving ECharts series color indices (`origIdx` / `color_slot`). `Top Projects` and `Project Sessions` include a dedicated **`Age`** column (`last_updated_ts` with relative-age parser fallback, sorting newest-first on first click), and `Top Projects` sorts all active projects before slicing the top `14`.
   - **Hybrid Range Whiskers & Target/Seam Caret Bars (`web/v9/v9_spark_bars.js`)**: All four Analytics tables replace flat `0–100%` stubs with metric-reactive (`[Steps | Tokens | $ Cost]`), keyboard/screen-reader-labeled (`role="img"` + `aria-label` + forced-colors support) comparative graphics:
     - **`Top Projects (Daily)` — Active-Day Range Whisker**: Renders `Min..Peak Day` range stem scaled to table max peak, `│` vertical crossbar at `Active-Day Avg`, and `●` dot at `Last 24h` (hollow muted ring at `0` when idle in active windows; omitted on closed historical windows) with compact `avg/d` readout and Peak-day sorting.
     - **`Subagent Workload` — Per-Run Outlier Whisker + Cap Alerts**: Renders `Min/run..Max/run`, `│` at `Avg/run`, and `●` at `Latest Run` (fallback `Last 24h`) scaled to highest role `Max/run`; surfaces fault `>120` badge whenever `max_steps_per_run > 120` or `over_120_runs > 0`, and amber `2.5x` badge for `> 2.5x` fleet-mean burn outliers.
     - **`Model Workload` — Target Guide `│` + `Last 24h ▾` Caret Bar**: Switches `Actual %` and `Guide / Delta` across `Steps`, `Tokens`, and `$ Cost`, preserving the vertical `│` Target Guide pin and adding a top `▾` caret at `Last 24h %` share (`Window % · 24h % · Guide %` tooltip).
     - **`Project Sessions (Daily)` — `320│ / 700▾` Seam & Burn Caret Bar**: In `Steps`, renders session context `step_count` (plus active window overlay) scaled to `max(750, maxSessionSteps)` with `│` seam tick at `320` steps and `▾` rollover caret at `700` steps (`500+` warning / `700+` alert on unretired sessions vs. muted `RET` when `RETIRED.json` / `is_retired`); in `Tokens` / `$ Cost`, renders normalized session burn with `│` Project Avg tick and `▾` Last 24h caret.
   - **Consistent Quartile Buckets Across Metrics**: `Steps`, `Tokens`, and `$ Cost` all compute `level 1..4` using empirical non-zero quartiles (`P25 / P50 / P75`) over active in-window days (falling back to all non-future active days in the 52-week strip only when the window has `< 4` non-zero days for that metric), so a single spike day never flattens prior weeks.
   - **Clear Out-of-Window Desaturation**: Out-of-window cells (`.v9-heat-cell.is-out`) render desaturated and low-opacity in neutral gray-tint across all 4 themes (`Pure White`, `Warm Paper`, `Dark Paper`, `Obsidian`), restoring clear legibility on hover while keeping in-window days (`in_window: true`) vibrant blue.
   - **Full-Width Trailing 52-Week Strip & 1st-of-Month Headers**: Every period preset renders a full-width trailing 52/53-week strip (`26w` default on `<= 560px` mobile with `Show 53w` toggle) where `.v9-heat-months` and `.v9-heat-grid` share identical `repeat(keepCols, minmax(10px, 1fr))` column tracks across the card width, and month labels anchor on the week column containing the `1st` of each month.
3. **Single-Call Boot, 8-Model Cost Ledger, 4-Tier Subscription Break-Even, Hourly Whiskers & Dedicated Project Analytics**:
   - `#analytics` boots with a single `/web/api/stats?...&include_ascii=0&compact_sessions=1` request; `src/agy_nexus/model_pricing.py` + `src/agy_nexus/cost_ledger.py` classify all **8 live models** (`Gemini 4 Carbon`, `Neon`, `Argon`, `Hydrogen`, `Gemini 3.8 Flash`, `Claude Opus 5.5`, `Claude Sonnet 5.5`, `GPT-OSS 120B`) using effective-dated integer micro-USD rates (`cost_ledger.json`), driving `Est. $` across KPIs, the 52w heatmap, `$ Cost` stacked bars, `Model Workload` & `Subagent Workload` (`booktabs`) tables, and `#v9BillingCard` (`v9_billing.js`).
   - **Official US Subscription Tiers (`src/agy_nexus/data/model_catalog.json` & `src/agy_nexus/ascii_models.py`)**: Keep all 4 official US monthly tiers synced across `subscription_tiers`, `build_billing_comparison()`, and `render_ascii_models_status()`:
     1. **`google_ai_plus`** (`Google AI Plus`): **`$4.99/mo`** (`4,990,000` micro-USD, `400 GB`, `2x Free` Gemini limits, `Hydrogen 4`, `$0/mo` dev credits)
     2. **`google_ai_pro`** (`Google AI Pro`): **`$19.99/mo`** (`19,990,000` micro-USD, `$199.99/yr` annual, `5 TB`, `1x`, `$10/mo` dev credits)
     3. **`google_ai_ultra_5x`** (`Google AI Ultra (5x)`): **`$99.99/mo`** (`99,990,000` micro-USD, `20 TB`, `5x` Pro limits, `$40/mo` dev credits)
     4. **`google_ai_ultra_20x`** (`Google AI Ultra (20x)`): **`$199.99/mo`** (`199,990,000` micro-USD, `30 TB`, `20x` Pro limits, `$100/mo` dev credits)
   - **Activity by Hour of Day** renders active-day `Min / Avg / Max` range whiskers + a `Last 24h` dot over `00h..23h`, followed by full-width **MCP Wire Footprint vs. 20 KB Ceiling** scatter and collapsed **Code Health** drawer (`web/` + `web/v9/` modules `<= 500L`).
   - Selecting `Analytics` for a project (`?project=<id>#analytics` via `src/agy_nexus/project_stats.py` and `web/v9/v9_demo_adapter.js`) switches to Dedicated Project Analytics (`Steps | Tokens | $ Cost`, `Session Context Budget` vs `700`-step seam, Handoff Queue, `Project Sessions`, and Project Code Health).
   - Both `/web?demo=1` and the static showcase enable all 6 window presets (`MTD`, `QTD`, `YTD`, `30d`, `90d`, `52w`) + `Last Month` from real-distribution depersonalized `DEMO_SNAPSHOT` bundles (`V9.DemoAdapter.isPresetAvailable`) and serve bundled depersonalized Workspace docs (`V9.DemoDocs`).
4. **2-Bar Flat Hairline Workbench, Responsive Split, Captures Modal & Static Showcase Gate**:
   - Workspace docks cleanly beneath `.v9-ws-context`: on `< 760px` phones, Docs fills `100%` width with wrapped 2-row `.v9-doc-hdr` tabs + `[Captures (N)]` modal; on `760–1279px` foldables, Split uses `64% / 36%` with a `1`-column gallery; and on `>= 1280px` desktops, Split uses `60% / 40%` with a `2`-column gallery (`[Raw]` + print stay on the right).
   - `scripts/build_github_showcase.py` builds a relative-path `./` static bundle (`build/gh-pages/` with `.nojekyll`, `window.AGY_STATIC_SHOWCASE = true`, and PNG ancillary metadata stripping) enforced by a fail-closed **0-leak privacy gate** before `scripts/publish_to_github.py` pushes orphan `gh-pages` or configures GitHub Pages.
