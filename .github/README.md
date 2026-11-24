# `.github/` Workflows, Templates & Branch Governance

This directory contains the GitHub Actions workflows, issue forms, and Pull Request checklist that keep `main` protected, validate Price Book updates, and automate tagged releases for **AGY-Nexus MCP** (`agy-nexus-mcp`).

For full setup and contribution rules, see [`CONTRIBUTING.md`](../CONTRIBUTING.md), [`AGENTS.md`](../AGENTS.md), and [`src/agy_nexus/data/README.md`](../src/agy_nexus/data/README.md).

---

## 1. Branching Model (`develop -> PR -> main`)

- **`develop`**: Active staging branch for feature waves, UI updates, and security hardening.
- **`main`**: Ruleset-protected production branch. Direct pushes are blocked; changes enter `main` through reviewed Pull Requests once the **`verify`** status check passes.

---

## 2. GitHub Actions Workflows (`workflows/`)

| Workflow | File | Triggers | What It Does |
| :--- | :--- | :--- | :--- |
| **CI Verification** (`verify`) | [`workflows/ci.yml`](workflows/ci.yml) | Push to `develop`; PRs to `main` or `develop` | Installs package + `pytest` + `jsonschema`, runs `pytest`, `ag_bridge.py --self-test`, `agy_nexus.tools_praxis --self-test`, `scripts/sync_agents.py --check`, `scripts/catalog_sync.py --validate-strict --require-jsonschema`, `scripts/catalog_sync.py --render-docs --check`, `scripts/build_github_showcase.py` (`0` leaks), and builds + smoke-tests the Docker `--stdio` JSON-RPC container. |
| **Automated Price Book Sync** | [`workflows/catalog-sync.yml`](workflows/catalog-sync.yml) | Weekly Monday `06:15 UTC` (`15 6 * * 1`) or `workflow_dispatch` | Checks out `main`, runs fail-closed numeric rate sync (`scripts/catalog_sync.py --sync-ci`) without touching locked `antigravity_ide` fields, validates `--validate-strict --require-jsonschema` and `--render-docs --check`, aborts if `git diff --name-only` or untracked files touch anything outside the 3 Price Book files, runs `pytest`, and updates one reusable `bot/catalog-sync` PR targeting `main`. |
| **GHCR OCI & MCP Registry** | [`workflows/publish-mcp.yml`](workflows/publish-mcp.yml) | Git tags `v*` or `workflow_dispatch` (`release_tag`) | Runs `pytest`, `--self-test` runners, and `--stdio` container smoke test; pushes multi-arch `ghcr.io/frankxlt/agy-nexus-mcp:<version>` + `:latest` (`linux/amd64`, `linux/arm64`); verifies `mcp-publisher` (`v1.8.1`) via Sigstore `cosign`; syncs `server.json`; and publishes to `registry.modelcontextprotocol.io` via GitHub OIDC (`id-token: write`). |

### Price Book Bot Guardrails (`catalog-sync.yml`)

Automated runs on `bot/catalog-sync` cannot modify Python/JS code, workflows, or locked IDE fields (`antigravity_ide`). Before committing or opening a PR, the workflow enforces:
1. `python3 scripts/catalog_sync.py --validate-strict --require-jsonschema` (formal Draft 2020-12 schema + anti-XSS/SSRF/bidi validation).
2. `python3 scripts/catalog_sync.py --render-docs --check` (deterministic `docs/PRICING_HISTORY.md` parity).
3. Explicit path allowlist check on `git diff --name-only HEAD`, untracked files, and `git diff --cached --name-only`: only `src/agy_nexus/data/model_catalog.json`, `src/agy_nexus/data/cost_ledger.json`, and `docs/PRICING_HISTORY.md` may change.

---

## 3. Templates & Security Reporting

- **Pull Requests**: [`PULL_REQUEST_TEMPLATE.md`](PULL_REQUEST_TEMPLATE.md) — summarizes workflow impact (`docs/WORKFLOWS.md`), `<= 500L` modular hygiene, `PWA_ASSETS` / `web/sw.js` parity, Price Book `--validate-strict` verification, zero-leak depersonalization, and AGPLv3 + Section 7 licensing.
- **Issues**: [`ISSUE_TEMPLATE/bug_report.yml`](ISSUE_TEMPLATE/bug_report.yml), [`ISSUE_TEMPLATE/feature_request.yml`](ISSUE_TEMPLATE/feature_request.yml), and [`ISSUE_TEMPLATE/config.yml`](ISSUE_TEMPLATE/config.yml) (redirects vulnerability disclosures to private GitHub Security Advisories — never post secrets, tokens, or LAN hostnames in public issues).
