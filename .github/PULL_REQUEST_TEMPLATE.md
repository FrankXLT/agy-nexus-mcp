## Plain-English Summary of User Workflow Impact

Describe what changed from the user's perspective (e.g., which MCP tool, `/web` view, Praxis IDE handoff step, or operational workflow improved and why).

## Pre-Merge Checklist

- [ ] **Documentation & Changelog**: `docs/WORKFLOWS.md` and `CHANGELOG.md` updated (if user-facing behavior or workflows changed).
- [ ] **Modular Hygiene**: All touched Python (`src/agy_nexus/`, `host_bridge/`) and frontend (`web/`) modules stay within the `<= 500` line target (`650` line hard ceiling) with functions `<= 100` lines, and no loose Python modules were added to the repository root.
- [ ] **Web Asset Parity** *(if `web/` changed)*: Every asset in `web/` is registered in `PWA_ASSETS` (`src/agy_nexus/web_routes.py`) and `SHELL_ASSETS` / `SHELL_NAMES` (`web/sw.js`).
- [ ] **Strict Depersonalization**: Zero private LAN IPs, real domain names, personal emails, local user paths, or secrets (`secrets.env`, `PATH_SECRET`, tokens) appear in code, tests, docs, or commit diffs. Any `/web` screenshots were captured strictly using `?demo=1`.

## Verification Results

Paste the observed output summary for all verification checks run after your final edit:

- [ ] `uv run --with pytest --with pytest-asyncio pytest` — result: `...`
- [ ] `python3 ag_bridge.py --self-test` — result: `...`
- [ ] `python3 -m agy_nexus.tools_praxis --self-test` — result: `...`

## Contributor License Agreement

- [ ] By submitting this Pull Request, I agree that my contributions are licensed under the **GNU Affero General Public License v3.0 (`AGPL-3.0-or-later`)** and the **Section 7 Additional Terms** in [`NOTICE`](NOTICE).
