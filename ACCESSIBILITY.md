# Accessibility Statement

## Commitment

**AGY-Nexus MCP** (`agy-nexus-mcp`) is committed to making its AI mission control bridge, Overwatch Studio (`/web` Analytics & `/web` Workspace), and terminal/chat telemetry accessible across mobile phones, unfolded foldables, desktop monitors, and assistive chat/terminal workflows. We treat visual ergonomics, keyboard operability, and plain-text clarity as core engineering requirements.

## Conformance & Visual Ergonomics

Our `/web` Overwatch interface and telemetry renderers are engineered around the following visual and ergonomic standards:

- **Four Contrast-Checked Surface Themes**: Users can switch between `Pure White`, `Warm Paper`, `Dark Paper`, and `Obsidian` surfaces via the Studio Settings menu (`web/styles.css` & `web/app.js`), maintaining readable foreground/background contrast ratios across ambient lighting conditions.
- **Density & Spacing Tokens (`D1–D4`)**: Shared `D1–D4` layout density and spacing tokens provide predictable visual hierarchy, breathing room, and scannable tabular alignment.
- **Responsive Multi-Viewport Layouts**: Tested across `390px` phone viewports, `900px` unfolded foldable viewports, and `1440px+` desktop screens with zero horizontal overflow.
- **Accessible Color-Blind-Safe Heatmap Scale**: The 52-week / 26-week activity heatmap uses a single-hue `#2563eb` ramp paired with numeric cell tooltips and summary counts so activity intensity never relies on hue distinction alone.
- **Touch-Friendly Gallery Targets**: Visual gallery thumbnails provide `40×40px` (`44×44px` on coarse/touch pointers) corner tap badges for reliable selection without mis-taps on mobile and tablet screens.

## Supported Environments & Assistive Features

- **Semantic Modals & Controls**: Interactive modals (Settings, Batch Upload, and Lightbox) use semantic `<dialog>` elements with native `Escape` key dismissal. Gallery action bars and chart preset selectors expose `role="toolbar"` and `aria-pressed` states for assistive technologies.
- **Keyboard Navigation**:
  - `Ctrl+B` / `Cmd+B` toggles the Workspace explorer sidebar (`240px` ↔ `38px` ↔ `0px` Zen mode).
  - `ArrowLeft`, `ArrowRight`, and `Escape` navigate and close images inside the Lightbox viewer.
  - `Shift+Click` supports contiguous range selection in the multi-select visual gallery.
- **Three-Tier Plain-Text & Unicode Telemetry**: For screen-reader, mobile chat, and narrow-terminal workflows, `get_session_tree` and telemetry renderers provide three plain-text/Unicode block (`░▒▓█`) tiers: `default` (`72`-column), `quick` (`<= 40` columns for mobile), and `rich` (`76`-column widescreen).
- **Voice-Friendly Passphrase Deadbolt (`normalize_phrase`)**: Spoken unlock passphrases strip punctuation, whitespace, and letter case (`normalize_phrase`) before SHA-256 verification so mobile voice dictation differences do not lock out speech-input users.

## Known Limitations

- **Complex SVG Stacked Bar Charts & Canvas Contact Sheet Composer**: The interactive SVG stacked bar charts (`web/charts.js`, `web/hierarchy.js`) and the `<canvas>` contact sheet generator (`web/sheet_builder.js`) are inherently visual. To keep quantitative insights accessible, every chart renders companion borderless DOM tabular legends and numeric tooltips, and the MCP server exposes equivalent structured plain-text summaries (`default` / `quick` / `rich`).

## Reporting Accessibility Barriers

If you encounter a keyboard trap, unreadable contrast in a surface theme, screen-reader labeling gap, or layout overflow:

1. Open a GitHub Issue using the templates in [`.github/ISSUE_TEMPLATE/`](.github/ISSUE_TEMPLATE/) and apply the `accessibility` label.
2. Include your **viewport width** (e.g., `390px`, `900px`, `1440px+`), active **surface theme** (`Pure White`, `Warm Paper`, `Dark Paper`, or `Obsidian`), and **assistive technology** or browser/client details.
3. **Never** paste `secrets.env`, `PATH_SECRET`, `PRAXIS_MCP_TOKEN`, passphrases, private LAN IPs, or personal URLs into issue reports—reproduce `/web` issues using `?demo=1` whenever possible.
