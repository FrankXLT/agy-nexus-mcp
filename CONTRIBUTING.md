# Contributing to AGY-Nexus MCP

Thank you for contributing to **AGY-Nexus MCP** (`agy-nexus-mcp`)!

This project is licensed under **GNU AGPLv3 + Section 7 Attribution & Security-Integrity Terms** ([`LICENSE`](LICENSE) and [`NOTICE`](NOTICE)) to ensure that all improvements and network-deployed modifications remain open and shared back with the community.

---

## 1. Branching, PR CI Gate & Release Flow

To keep `main` protected with GitHub Repository Rulesets and required status checks:

1. **Stage Bundled Work on `develop`**:
   - Cut feature branches or wave commits against `develop` (never commit directly to protected `main`).
   - Every push to `develop` and every Pull Request targeting `main` or `develop` triggers `.github/workflows/ci.yml` (required status check job: **`verify`**), which runs:
     - `pytest`
     - `python3 ag_bridge.py --self-test`
     - `python3 -m agy_nexus.tools_praxis --self-test`
     - `python3 scripts/sync_agents.py --check`
     - `python3 scripts/build_github_showcase.py` (`0` privacy leaks)
     - Local `docker build` + `--stdio` JSON-RPC container smoke check (`initialize`, `tools/list`, `list_models_and_agents`, and fail-closed `list_saved_sessions`)
2. **Merge & Tagged Release (`v*`)**:
   - Once the **`verify`** check passes and review is approved, merge the Pull Request into `main`.
   - Pushing a release tag (`v*`) triggers `.github/workflows/publish-mcp.yml` to build multi-arch GHCR OCI images (`linux/amd64`, `linux/arm64`) and publish `server.json` to the Official MCP Registry via GitHub OIDC.

---

## 2. Repository Layout & Modular Rules

Before submitting a Pull Request, please review [`AGENTS.md`](AGENTS.md) and adhere to these structural standards:

1. **Keep Modules Cohesive (`<= 500 Lines` Target, `650 Lines` Hard Ceiling, Functions `<= 100 Lines`)**:
   - Place backend code inside `src/agy_nexus/` in cohesive domain modules without artificial micro-file sprawl.
   - Keep frontend code split cleanly inside `web/` and `web/v9/` (`web/index.html` and `web/v9/index.html` must remain byte-identical, and every asset under `web/v9/` must be registered in `PWA_ASSETS` in `src/agy_nexus/web_routes.py` and `SHELL_NAMES` in `web/sw.js` with `0 !important` and `0` disallowed Unicode pictographs).
   - Do not add loose Python helper files to the repository root (`ag_bridge.py` is the only root Python file, acting as a thin compatibility shim).
2. **Preserve the Multi-Layer Security Gate**:
   - Never bypass, weaken, or disable `PATH_SECRET`, `is_unlocked()`, `try_inline_unlock()`, `/praxis/` and `/polyglot/` LAN-only `403` guards, `is_sensitive_filename()`, or `.is_relative_to()` path-traversal checks.
3. **Zero Personal Data or Lockfile Churn**:
   - Do not include personal hostnames, emails, private LAN IPs, real domain names, or local user paths in code, docs, or screenshots (capture screenshots strictly via `/web?demo=1`).
   - Do not commit `uv.lock`, `.venv/`, or `secrets.env`.

---

## 3. Running the Test & Self-Test Suites

Run the local verification suite before opening a Pull Request:

```bash
uv run --with pytest --with pytest-asyncio pytest
python3 ag_bridge.py --self-test
python3 -m agy_nexus.tools_praxis --self-test
python3 scripts/sync_agents.py --check
python3 scripts/build_github_showcase.py
```

All verification checks (Deadbolt normalization, TTL/inline unlock transitions, SQLite session indexing, Sequential Read-Only Governance, 52-week heatmap grayscale/dividers/selection & adaptive slot series, `/web` + `/web/v9` + `/praxis/` + `/polyglot/` route mounting + `PWA_ASSETS` parity + `405` Streamable HTTP compliance + JS syntax checks, repo-prefixed `<slug>-NN` handoff queue, fail-closed `target_resolver`, 2-Pane Workspace bucket & `.zip` traversal guards, in-place session retirement, 7-day `/web/media/` HMAC signing, session-isolated visual discovery, `2 / 4 / 8`-per-sheet direct PNG exports, strict most-recent-first project/session recency sorting, incremental SHA-256 Polyglot indexing, and `--stdio` JSON-RPC container startup) must pass.

---

## 4. Licensing of Contributions

By submitting a Pull Request or patch to this repository, you agree that your contributions are licensed under the **GNU Affero General Public License v3.0 (`AGPL-3.0-or-later`)** alongside the Section 7 Additional Terms in [`NOTICE`](NOTICE).
