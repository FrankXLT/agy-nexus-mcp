# Contributing to AGY-Nexus MCP

Thank you for contributing to **AGY-Nexus MCP** (`agy-nexus-mcp`)!

This project is licensed under **GNU AGPLv3 + Section 7 Attribution & Security-Integrity Terms** ([`LICENSE`](LICENSE) and [`NOTICE`](NOTICE)) to ensure that all improvements and network-deployed modifications remain open and shared back with the community.

---

## 1. Repository Layout & Modular Rules

Before submitting a Pull Request, please review [`AGENTS.md`](AGENTS.md) and adhere to these structural standards:

1. **Keep Modules Focused (`100–300 Lines`, Max `400 Lines`)**:
   - Place backend code inside `src/agy_nexus/` in focused domain modules.
   - Keep frontend code split cleanly inside `web/` (`index.html`, `styles.css`, `charts.js`, `hierarchy.js`, `app.js`).
   - Do not add loose Python helper files to the repository root (`ag_bridge.py` is the only root Python file, acting as a thin 51-line compatibility shim).
2. **Preserve the 3-Layer Security Gate**:
   - Never bypass, weaken, or disable `PATH_SECRET`, `is_unlocked()`, `try_inline_unlock()`, or `.is_relative_to()` path-traversal checks.
3. **Zero Personal Data or Lockfile Churn**:
   - Do not include personal hostnames, private LAN IPs, real domain names, or local user paths in code, docs, or screenshots.
   - Do not commit `uv.lock`, `.venv/`, or `secrets.env`.

---

## 2. Running the Self-Test Suite

Run the built-in automated self-test suite before submitting changes:

```bash
python3 ag_bridge.py --self-test
```

All 8 verification checks (Deadbolt normalization, TTL/inline unlock transitions, SQLite session indexing, telemetry & heatmap scanning, FastMCP `/web` route mounting + JS syntax check, multi-repo drift + Notebook SHA-256 deduplication, visual artifact HMAC signing, and 3-tier path resolver + 76-col session tree) must pass.

---

## 3. Licensing of Contributions

By submitting a Pull Request or patch to this repository, you agree that your contributions are licensed under the **GNU Affero General Public License v3.0 (`AGPL-3.0-or-later`)** alongside the Section 7 Additional Terms in [`NOTICE`](NOTICE).
