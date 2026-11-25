# Price Book Data Directory (`src/agy_nexus/data/`)

This directory holds the ground-truth two-file **Price Book** and strict validation schemas used by **AGY-Nexus MCP** (`model_pricing.py`, `catalog_sync.py`, `catalog_validator.py`) and `/web` Analytics.

---

## 1. Files in This Directory

| Path | Purpose | Who Updates It |
| :--- | :--- | :--- |
| [`model_catalog.json`](model_catalog.json) | Canonical 8-model specs, `subscription_tiers`, `fallback_token_split`, monotonic `catalog_revision`, `updated_at`, `public_api`, and locked `antigravity_ide` allocations | Humans via PR (`antigravity_ide`) or `bot/catalog-sync` (`public_api` caps only) |
| [`cost_ledger.json`](cost_ledger.json) | Effective-dated integer micro-USD `rate_epochs` (`1 USD = 1,000,000` micros) with `effective_from`, `effective_to`, `source_url`, `verified_at`, and `note` | Humans via PR or `bot/catalog-sync` |
| [`schemas/model_catalog.schema.json`](schemas/model_catalog.schema.json) | Draft 2020-12 JSON Schema for `model_catalog.json` (`additionalProperties: false` at every object level) | Maintainers via PR |
| [`schemas/cost_ledger.schema.json`](schemas/cost_ledger.schema.json) | Draft 2020-12 JSON Schema for `cost_ledger.json` (`0 <= rate <= 500_000_000` integer bounds) | Maintainers via PR |

From these two JSON files, `python3 scripts/catalog_sync.py --render-docs` deterministically generates [`docs/PRICING_HISTORY.md`](../../../docs/PRICING_HISTORY.md) (never edit that Markdown table by hand).

---

## 2. `public_api` vs. Locked `antigravity_ide` Fields

Every entry inside `model_catalog.json` separates public vendor specs from local IDE configuration:
- **`public_api`** *(bot-updatable)*: `api_context_window`, `api_max_output_tokens`, `source_url`, and `verified_at`.
- **`antigravity_ide`** *(locked from automated bot changes)*: `pool_key`, `pool_label`, `quota_group`, IDE `context_window` / `max_output_tokens`, `reasoning_tiers`, `placeholders` (`MODEL_PLACEHOLDER_M*` / `MODEL_OPENAI_*`), `tier_placeholders`, and `target_pct`.

`scripts/catalog_sync.py --sync-ci` and `.github/workflows/catalog-sync.yml` call `assert_antigravity_ide_untouched()` and refuse any automated PR that alters `antigravity_ide` or touches files outside `model_catalog.json`, `cost_ledger.json`, and `docs/PRICING_HISTORY.md`.

---

## 3. Revision Monotonicity & Safe Local Overrides (`catalog_override.json`)

- Both files share an integer `catalog_revision >= 1` (`updated_at` in `YYYY-MM-DD`).
- Running instances resolve their upstream GitHub branch strictly within `{"main", "develop"}` via `AGY_CATALOG_BRANCH` (auto-detecting local `develop` Git checkouts and failing closed to `"main"` in standalone containers/wheels) and check `raw.githubusercontent.com/FrankXLT/agy-nexus-mcp/{branch}/src/agy_nexus/data/` at most once every 24 hours (`${AGY_BG_DIR}/catalog_sync_cache.json`, auto-invalidating whenever `upstream_branch` changes and failing open offline).
- `scripts/catalog_sync.py --sync-ci` streams up to `16 MiB` from `models.dev` in memory while keeping stored `model_catalog.json`, `cost_ledger.json`, and `catalog_override.json` strictly `<= 256 KB` (`262,144` bytes), and never downgrades higher curated `public_api` context/output token limits when external feeds lag behind.
- When unlocked in `/web`, users can preview diffs in `<dialog id="v9CatalogDiffDialog">` and accept an update via `POST /web/api/catalog/accept`, writing `${AGY_DATA_DIR}/catalog_override.json` atomically (`chmod 0600`) without modifying git-tracked files.
- `load_active_override_pair()` and `load_model_catalog()` re-validate every override before use, automatically fall back to the repo-bundled pair if an override is tampered with or corrupt, and auto-retire overrides once the bundled `catalog_revision` catches up.

---

## 4. Schema & Anti-Injection Security Gate (`catalog_validator.py`)

Both [`src/agy_nexus/catalog_validator.py`](../catalog_validator.py) (zero external runtime dependency) and the JSON Schemas in `schemas/` fail closed on:
- **Unexpected properties** (`additionalProperties: false` at every nested object level) or missing required keys,
- **Payload size or JSON traps**: `> 256 KB` (`262,144` bytes), NUL/BOM bytes, `NaN`/`Infinity`/`-Infinity`, or duplicate object keys,
- **Integer/numeric bounds**: negative or `> 500_000_000` micro-USD rates, boolean-for-int confusion, invalid calendar dates, or `fallback_token_split` ratios not summing to `~1.0`,
- **HTML/XSS, control & Markdown spoofing**: `<`, `>`, ASCII/C1 control characters (`\r`, `\n`, `\t`), Unicode bidi/zero-width spoofing (`\u202a`–`\u202e`, `\u2066`–`\u2069`, `\u200b`–`\u200f`), `javascript:`/`vbscript:`/`data:` schemes, event handlers (`onerror=`), and Markdown breaks (`[`, `]`, `|`, backticks, `\`),
- **URL allowlist & SSRF blocks**: all `source_url` fields must be pure-ASCII `https://` URLs with zero userinfo (`@`), explicit `:port`, IP literals, `localhost`/`.lan`/`.local`, and must resolve to `ALLOWED_SOURCE_HOSTS` (`ai.google.dev`, `cloud.google.com`, `one.google.com`, `blog.google`, `deepmind.google`, `docs.anthropic.com`, `www.anthropic.com`, `claude.com`, `openai.com`, `platform.openai.com`, `github.com`, `models.dev`).

---

## 5. Adding or Validating a New `MODEL_PLACEHOLDER_M*` or Rate Epoch

1. Add the barcode or epoch locally (or stage a proposal via `scripts/catalog_sync.py`):
   ```bash
   python3 scripts/catalog_sync.py --propose-local-pr --model-code MODEL_PLACEHOLDER_M610 --model-key hydrogen
   ```
2. Regenerate [`docs/PRICING_HISTORY.md`](../../../docs/PRICING_HISTORY.md) and run strict validation + tests:
   ```bash
   python3 scripts/catalog_sync.py --render-docs
   python3 scripts/catalog_sync.py --validate-strict
   python3 scripts/catalog_sync.py --render-docs --check
   uv run --with pytest --with pytest-asyncio --with jsonschema pytest
   ```
3. Commit your branch against `develop` (or open a Pull Request targeting `main` so `ci.yml` `verify` runs `--validate-strict --require-jsonschema`).
