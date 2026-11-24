"""tests/test_v409_wave3_catalog_security_and_docs.py — AGY-Nexus v4.0.9 Wave 3 Schema Security, Path Locks & Process READMEs."""
from __future__ import annotations

import ast
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
DATA_DIR = SRC_DIR / "agy_nexus" / "data"
SCHEMAS_DIR = DATA_DIR / "schemas"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agy_nexus import catalog_sync, catalog_validator, model_pricing


def _fresh_pair() -> tuple[dict, dict]:
    cat, led = catalog_sync.load_bundled_catalog_pair()
    return deepcopy(cat), deepcopy(led)


def test_wave3_json_schemas_and_strict_cli_parity() -> None:
    """Verify Draft 2020-12 JSON schemas, pure-Python parity, zero external runtime deps, and --validate-strict CLI."""
    cat_schema = json.loads((SCHEMAS_DIR / "model_catalog.schema.json").read_text(encoding="utf-8"))
    led_schema = json.loads((SCHEMAS_DIR / "cost_ledger.schema.json").read_text(encoding="utf-8"))
    assert cat_schema["additionalProperties"] is False and led_schema["additionalProperties"] is False
    assert cat_schema["$defs"]["subscriptionTier"]["additionalProperties"] is False
    assert cat_schema["$defs"]["modelEntry"]["additionalProperties"] is False
    assert cat_schema["$defs"]["modelEntry"]["properties"]["public_api"]["additionalProperties"] is False
    assert cat_schema["$defs"]["modelEntry"]["properties"]["antigravity_ide"]["additionalProperties"] is False
    assert led_schema["$defs"]["ledgerModel"]["additionalProperties"] is False
    assert led_schema["$defs"]["rateEpoch"]["additionalProperties"] is False
    assert led_schema["$defs"]["rateEpoch"]["properties"]["input_micros"]["maximum"] == 500_000_000

    ok, errs, info = catalog_validator.validate_catalog_files_strict(
        DATA_DIR / "model_catalog.json", DATA_DIR / "cost_ledger.json", require_jsonschema=False,
    )
    assert ok is True and errs == [] and info["model_count"] == 8

    # Cross-check with jsonschema when installed in CI / test env
    try:
        import jsonschema  # noqa: F401
        has_js = True
    except ImportError:
        has_js = False
    if has_js:
        ran, js_errs = catalog_validator.validate_with_jsonschema(*_fresh_pair(), require_installed=True)
        assert ran is True and js_errs == []

    # Verify catalog_validator imports with stdlib only (no fastmcp/pydantic needed)
    pure_check = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "catalog_sync.py"), "--validate-strict"],
        cwd=str(REPO_ROOT), capture_output=True, text=True, check=False,
    )
    assert pure_check.returncode == 0, pure_check.stdout + pure_check.stderr
    assert "--validate-strict PASS" in pure_check.stdout


@pytest.mark.parametrize(
    ("mutator", "expected_substr"),
    [
        (lambda c, _l: c.update({"unexpected_root_key": 1}), "unexpected"),
        (lambda c, _l: c["models"][0]["antigravity_ide"].update({"extra": "bad"}), "unexpected"),
        (lambda c, _l: c["models"][0].update({"label": "<script>alert(1)</script>"}), "disallowed"),
        (lambda c, _l: c["subscription_tiers"][0].update({"notes": "<img onerror=alert(1)>"}), "disallowed"),
        (lambda c, _l: c["models"][0].update({"short_label": "Bad|Pipe[Link]"}), "disallowed"),
        (lambda c, _l: c["models"][0].update({"label": "Carbon\u202eSpoof"}), "disallowed"),
        (lambda c, _l: c["models"][0].update({"label": "Carbon\u200bZero"}), "disallowed"),
        (lambda c, _l: c["models"][0].update({"label": "Line1\nLine2"}), "disallowed"),
        (lambda c, _l: c["models"][0].update({"label": "Back`tick"}), "disallowed"),
        (lambda c, _l: c["models"][0]["public_api"].update({"source_url": "javascript:alert(1)"}), "unsafe"),
        (lambda c, _l: c["models"][0]["public_api"].update({"source_url": "javascript:evil"}), "https://"),
        (lambda c, _l: c["models"][0]["public_api"].update({"source_url": "data:text/plain,hello"}), "script"),
        (lambda c, _l: c["models"][0]["public_api"].update({"source_url": "data:text/html,<script>alert(1)</script>"}), "unsafe"),
        (lambda c, _l: c["models"][0]["public_api"].update({"source_url": "http://ai.google.dev/pricing"}), "https://"),
        (lambda c, _l: c["models"][0]["public_api"].update({"source_url": "http://169.254.169.254/latest/meta-data"}), "https://"),
        (lambda c, _l: c["models"][0]["public_api"].update({"source_url": "https://127.0.0.1/pricing"}), "IP"),
        (lambda c, _l: c["models"][0]["public_api"].update({"source_url": "https://[::1]/pricing"}), "unsafe"),
        (lambda c, _l: c["models"][0]["public_api"].update({"source_url": "https://localhost/pricing"}), "local"),
        (lambda c, _l: c["models"][0]["public_api"].update({"source_url": "https://ai.google.dev@evil.com/pricing"}), "userinfo"),
        (lambda c, _l: c["models"][0]["public_api"].update({"source_url": "https://ai.google.dev:8443/pricing"}), "ports"),
        (lambda c, _l: c["models"][0]["public_api"].update({"source_url": "https://evil.example.org/pricing"}), "ALLOWED_SOURCE_HOSTS"),
        (lambda _c, l: l["models"]["carbon"]["rate_epochs"][0].update({"input_micros": -1}), "integer"),
        (lambda _c, l: l["models"]["carbon"]["rate_epochs"][0].update({"output_micros": 500_000_001}), "integer"),
        (lambda _c, l: l["models"]["carbon"]["rate_epochs"][0].update({"cache_read_micros": True}), "integer"),
        (lambda _c, l: l["models"]["carbon"]["rate_epochs"][0].update({"effective_from": "2026-02-30"}), "calendar"),
        (lambda _c, l: l["models"]["carbon"]["rate_epochs"][0].update({"source_url": "https://evil.test/pricing"}), "ALLOWED_SOURCE_HOSTS"),
        (lambda _c, l: l["models"]["carbon"]["rate_epochs"][0].update({"note": "Inject | pipe `code`"}), "disallowed"),
        (lambda c, _l: c["models"][0]["antigravity_ide"]["placeholders"].append("MODEL_BAD_NO_PREFIX"), "placeholders"),
        (lambda c, _l: c["models"][0].update({"key": "carbon\n"}), "snake_case"),
        (lambda c, _l: c["models"][0]["antigravity_ide"]["placeholders"].append("MODEL_PLACEHOLDER_M427\n"), "placeholders"),
        (lambda c, _l: c["models"][0]["model_ids"].append("gemini-4-carbon-high\n"), "model_ids"),
    ],
)
def test_wave3_blocks_malicious_payloads_and_injection(mutator, expected_substr: str) -> None:
    """Verify catalog_validator rejects XSS, SSRF, bad domains, extra keys, overflow rates, bidi, and Markdown breaks."""
    cat, led = _fresh_pair()
    mutator(cat, led)
    errs = catalog_validator.validate_catalog_pair_strict(cat, led)
    assert errs, f"Expected validation failure for {expected_substr}"
    assert any(expected_substr.lower() in e.lower() for e in errs), f"Expected '{expected_substr}' in {errs}"


def test_wave3_jsonschema_parity_rejects_structural_violations() -> None:
    """Verify Draft 2020-12 JSON schemas independently reject extra properties, bad bounds, and bad URLs."""
    pytest.importorskip("jsonschema")
    for mut in (
        lambda c, _l: c.update({"evil": 1}),
        lambda c, _l: c["models"][0]["public_api"].update({"extra": "x"}),
        lambda c, _l: c["models"][0]["public_api"].update({"source_url": "http://169.254.169.254/latest"}),
        lambda c, _l: c["models"][0].update({"key": "carbon\n"}),
        lambda c, _l: c["models"][0]["public_api"].update({"source_url": "https://ai.google.dev\n"}),
        lambda _c, l: l["models"]["carbon"]["rate_epochs"][0].update({"output_micros": 500_000_001}),
        lambda _c, l: l["models"]["carbon"]["rate_epochs"][0].update({"input_micros": -5}),
        lambda _c, l: l["models"]["carbon"]["rate_epochs"][0].update({"extra_ep": 1}),
    ):
        cat, led = _fresh_pair()
        mut(cat, led)
        ran, js_errs = catalog_validator.validate_with_jsonschema(cat, led, require_installed=True)
        assert ran is True and js_errs, "Expected jsonschema Draft 2020-12 rejection"


def test_wave3_json_bytes_guards_nan_duplicates_and_size_cap() -> None:
    """Verify pre-parse <=256 KB byte limit, NaN/Infinity/1e500 rejection, duplicate-key rejection, and BOM/NUL guard."""
    oversized = b'{"a":"' + (b"x" * (catalog_validator.MAX_CATALOG_BYTES + 64)) + b'"}'
    with pytest.raises(ValueError, match="exceeds"):
        catalog_validator.parse_catalog_json_bytes(oversized)
    for bad_raw in (b'{"x": NaN}', b'{"x": Infinity}', b'{"x": -Infinity}', b'{"x": 1e500}', b'{"x": -1e500}', b'{"k": 1, "k": 2}', b'\xef\xbb\xbf{"k":1}', b'{"k": "a\x00b"}'):
        with pytest.raises(ValueError):
            catalog_validator.parse_catalog_json_bytes(bad_raw)


def test_wave3_runtime_client_sync_and_corrupt_override_fallback(tmp_path: Path) -> None:
    """Verify accept_catalog_override, get_catalog_sync_status, and load_model_catalog fail closed on tampered/poisoned files."""
    d_dir, bg_dir = tmp_path / "data", tmp_path / "bg"
    d_dir.mkdir()
    bg_dir.mkdir()
    cat, led = _fresh_pair()

    # 1. Poisoned upstream preview rejected before caching/exposing diff
    evil_cat, evil_led = deepcopy(cat), deepcopy(led)
    evil_cat["catalog_revision"] = 99
    evil_cat["models"][0]["public_api"]["source_url"] = "http://169.254.169.254/latest/meta-data"
    st_bad = catalog_sync.get_catalog_sync_status(
        d_dir, bg_dir, allow_network=True, refresh=True,
        upstream_fetcher=lambda: (True, evil_cat, evil_led, ""),
    )
    assert st_bad["status"] == "INVALID_UPSTREAM" and st_bad["update_available"] is False and st_bad["diff"] is None

    # 1b. Poisoned/partial/non-numeric/future-TTL catalog_sync_cache.json never crashes or locks updates
    for bad_cache in (
        {"status": "OK", "fetched_epoch": "bad", "upstream_catalog": {"catalog_revision": "bad"}, "upstream_ledger": None},
        {"status": "OK", "fetched_epoch": 9e12, "upstream_catalog": evil_cat, "upstream_ledger": evil_led},
        {"status": "OK", "fetched_epoch": 1.0, "upstream_catalog": {"catalog_revision": [1]}, "upstream_ledger": None},
    ):
        (bg_dir / "catalog_sync_cache.json").write_text(json.dumps(bad_cache), encoding="utf-8")
        st_poison = catalog_sync.get_catalog_sync_status(d_dir, bg_dir, allow_network=False)
        assert st_poison["update_available"] is False and st_poison["diff"] is None

    # 2. accept_catalog_override blocks injection payloads without writing file
    evil_cat["models"][0]["public_api"]["source_url"] = "https://ai.google.dev/gemini-api/docs/pricing"
    evil_led["models"]["carbon"]["rate_epochs"][0]["note"] = "<img onerror=alert(1)>"
    acc_bad = catalog_sync.accept_catalog_override(d_dir, bg_dir, candidate_catalog=evil_cat, candidate_ledger=evil_led)
    assert acc_bad["ok"] is False and not (d_dir / "catalog_override.json").exists()

    # 3. Tampered or symlinked catalog_override.json on disk triggers safe bundled fallback
    bundled_rev = int(cat["catalog_revision"])
    for payload_bytes in (
        b'{"catalog_revision": 99, "updated_at": "2026-12-01", "accepted_at": "2026-12-01T00:00:00Z", "source": "upstream_main", "bad": NaN}',
        json.dumps({"catalog_revision": 99, "updated_at": "2026-12-01", "accepted_at": "2026-12-01T00:00:00Z", "source": "upstream_main", "extra": 1, "model_catalog": cat, "cost_ledger": led}).encode("utf-8"),
        b"{" + (b" " * (catalog_validator.MAX_CATALOG_BYTES + 10)) + b"}",
    ):
        (d_dir / "catalog_override.json").write_bytes(payload_bytes)
        model_pricing.clear_model_catalog_cache()
        loaded = model_pricing.load_model_catalog(data_dir=d_dir)
        assert loaded["override_active"] is False and loaded["effective_catalog_revision"] == bundled_rev

    (d_dir / "catalog_override.json").unlink(missing_ok=True)
    secret_t = tmp_path / "secret_target.json"
    secret_t.write_text("{}", encoding="utf-8")
    (d_dir / "catalog_override.json").symlink_to(secret_t)
    model_pricing.clear_model_catalog_cache()
    assert model_pricing.load_model_catalog(data_dir=d_dir)["override_active"] is False


def test_wave3_workflows_path_allowlist_readmes_and_budgets() -> None:
    """Verify bot path allowlist, CI/bot workflow guards, wire compaction bounds, .github + data READMEs, and <=500L budgets."""
    from agy_nexus import workflow_baseline

    assert catalog_validator.verify_catalog_bot_changed_paths([
        "src/agy_nexus/data/model_catalog.json",
        "src/agy_nexus/data/cost_ledger.json",
        "docs/PRICING_HISTORY.md",
    ]) == []
    bad_paths = catalog_validator.verify_catalog_bot_changed_paths([
        "src/agy_nexus/data/model_catalog.json",
        ".github/workflows/ci.yml",
        "src/agy_nexus/server.py",
        "docs/PRICING_HISTORY.md ",
        "  ",
    ])
    assert bad_paths == [".github/workflows/ci.yml", "src/agy_nexus/server.py", "docs/PRICING_HISTORY.md ", "  "]

    wf_info = workflow_baseline.discover_project_workflows(REPO_ROOT)
    for cap in (690, 900, 1200):
        wire = workflow_baseline.format_workflow_baseline_for_wire(wf_info, max_chars=cap)
        assert len(wire) <= cap and all(f"WF-0{n}" in wire for n in range(1, 9))

    ci_yml = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "jsonschema" in ci_yml and "scripts/catalog_sync.py --validate-strict" in ci_yml

    sync_yml = (REPO_ROOT / ".github" / "workflows" / "catalog-sync.yml").read_text(encoding="utf-8")
    for tok in ("jsonschema", "--validate-strict", "--no-renames", "--name-only", "--cached", "--raw", "verify_catalog_bot_changed_paths", "assert_antigravity_ide_untouched", "100644", "src/agy_nexus/data/model_catalog.json", "src/agy_nexus/data/cost_ledger.json", "docs/PRICING_HISTORY.md"):
        assert tok in sync_yml, f"Missing token in catalog-sync.yml: {tok}"

    gh_readme = (REPO_ROOT / ".github" / "README.md").read_text(encoding="utf-8")
    assert "develop" in gh_readme and "publish-mcp.yml" in gh_readme and "catalog-sync.yml" in gh_readme and "antigravity_ide" in gh_readme

    pr_tpl = (REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8")
    assert "--validate-strict" in pr_tpl and "antigravity_ide" in pr_tpl

    data_readme = (DATA_DIR / "README.md").read_text(encoding="utf-8")
    for tok in ("model_catalog.json", "cost_ledger.json", "public_api", "antigravity_ide", "catalog_revision", "catalog_override.json", "--validate-strict"):
        assert tok in data_readme, f"Missing token in data/README.md: {tok}"

    wf_doc = (REPO_ROOT / "docs" / "WORKFLOWS.md").read_text(encoding="utf-8")
    assert "catalog_validator.py" in wf_doc and "git diff --name-only" in wf_doc and "src/agy_nexus/data/README.md" in wf_doc
    for banned in ("diurnal", "plain-english", "posture", "surface"):
        assert banned not in wf_doc.lower(), f"Banned term '{banned}' in docs/WORKFLOWS.md"

    for p in (SRC_DIR / "agy_nexus" / "catalog_validator.py", SRC_DIR / "agy_nexus" / "catalog_sync.py", REPO_ROOT / "scripts" / "catalog_sync.py", Path(__file__)):
        lines = p.read_text(encoding="utf-8").splitlines()
        assert len(lines) <= 500, f"{p.name} > 500L ({len(lines)}L)"
        tree = ast.parse("\n".join(lines), filename=str(p))
        for fn in ast.walk(tree):
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) and fn.end_lineno:
                assert fn.end_lineno - fn.lineno + 1 <= 100, f"{p.name}:{fn.name} > 100L"
