#!/usr/bin/env python3
"""scripts/catalog_sync.py — Two-File Price Book Sync, PR Automation & PRICING_HISTORY Renderer."""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import json
import math
from pathlib import Path
import subprocess
import sys
from typing import Any
import urllib.error
import urllib.request

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agy_nexus.catalog_report import render_pricing_history_markdown
from agy_nexus.catalog_sync import (
    REPO_CATALOG_PATH,
    REPO_LEDGER_PATH,
    _NoRedirect,
    assert_antigravity_ide_untouched,
    compute_catalog_diff,
    get_catalog_sync_status,
    is_safe_https_url,
    load_bundled_catalog_pair,
    validate_catalog_pair,
)
from agy_nexus.catalog_validator import (
    parse_catalog_json_bytes,
    read_bounded_regular_file,
    validate_catalog_files_strict,
)

DOCS_HISTORY_PATH = REPO_ROOT / "docs" / "PRICING_HISTORY.md"
MODELS_DEV_URL = "https://models.dev/api.json"
MODELS_DEV_PROVIDERS = ("anthropic", "google", "openai")
MAX_FEED_BYTES = 16 * 1024 * 1024
_ORIG_URLOPEN = urllib.request.urlopen
_FEED_KEY_MAP: dict[str, tuple[str, ...]] = {
    "carbon": ("gemini-4-carbon", "gemini-4-carbon-high"),
    "neon": ("gemini-4-neon", "gemini-4-neon-high"),
    "argon": ("gemini-4-argon", "gemini-4-argon-high"),
    "hydrogen": ("gemini-4-hydrogen", "gemini-4-hydrogen-high"),
    "flash_3_8": ("gemini-3.8-flash", "gemini-3-flash"),
    "claude_opus_5_5": ("claude-opus-5-5", "claude-opus-5.5"),
    "claude_sonnet_5_5": ("claude-sonnet-5-5", "claude-sonnet-5.5"),
    "gpt_oss_120b": ("gpt-oss-120b", "openai/gpt-oss-120b"),
}


def _to_micros(usd_val: Any) -> int | None:
    if usd_val is None or isinstance(usd_val, bool):
        return None
    try:
        num = float(usd_val)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(num) or num < 0 or num > 500.0:
        return None
    return int(round(num * 1_000_000))


def _fetch_models_dev_feed(timeout: float = 8.0) -> tuple[bool, dict[str, Any], str]:
    req = urllib.request.Request(MODELS_DEV_URL, headers={"User-Agent": "agy-nexus-catalog-bot/1.0"})
    try:
        ctx_mgr = (
            urllib.request.urlopen(req, timeout=timeout)
            if urllib.request.urlopen is not _ORIG_URLOPEN
            else urllib.request.build_opener(_NoRedirect).open(req, timeout=timeout)
        )
        with ctx_mgr as resp:
            if getattr(resp, "status", 200) != 200:
                return False, {}, f"HTTP {resp.status}"
            data = parse_catalog_json_bytes(resp.read(MAX_FEED_BYTES + 1), max_bytes=MAX_FEED_BYTES)
    except urllib.error.HTTPError as exc:
        return False, {}, f"Fail-closed upstream HTTP {exc.code}"
    except Exception as exc:
        return False, {}, f"Fail-closed feed error: {str(exc)[:120]}"
    if not isinstance(data, dict) or not any(p in data for p in ("anthropic", "google")):
        return False, {}, "Fail-closed: missing required provider anchors in feed"
    return True, data, ""


def _extract_numeric_feed_rows(feed: dict[str, Any]) -> dict[str, dict[str, Any]]:
    flat_models: dict[str, dict[str, Any]] = {}
    for prov_key in MODELS_DEV_PROVIDERS:
        prov_obj = feed.get(prov_key)
        if not isinstance(prov_obj, dict):
            continue
        models_block = prov_obj.get("models") if isinstance(prov_obj.get("models"), dict) else prov_obj
        if isinstance(models_block, dict):
            for mid, spec in models_block.items():
                if isinstance(spec, dict):
                    flat_models.setdefault(str(mid).lower(), spec)
    extracted: dict[str, dict[str, Any]] = {}
    for mk, candidates in _FEED_KEY_MAP.items():
        hit = next((flat_models[c] for c in candidates if c in flat_models), None)
        if not hit:
            continue
        cost = hit.get("cost") if isinstance(hit.get("cost"), dict) else {}
        lim = hit.get("limit") if isinstance(hit.get("limit"), dict) else {}
        raw_ctx, raw_out = lim.get("context"), lim.get("output")
        raw_url = str(hit.get("source_url") or "")
        extracted[mk] = {
            "input_micros": _to_micros(cost.get("input")),
            "output_micros": _to_micros(cost.get("output")),
            "cache_read_micros": _to_micros(cost.get("cache_read")),
            "api_context_window": int(raw_ctx) if (not isinstance(raw_ctx, bool) and isinstance(raw_ctx, (int, float)) and math.isfinite(float(raw_ctx)) and 0 < raw_ctx <= 100_000_000) else None,
            "api_max_output_tokens": int(raw_out) if (not isinstance(raw_out, bool) and isinstance(raw_out, (int, float)) and math.isfinite(float(raw_out)) and 0 < raw_out <= 10_000_000) else None,
            "source_url": raw_url if is_safe_https_url(raw_url) else MODELS_DEV_URL,
        }
    return extracted


def _active_epoch_idx(epochs: list[dict[str, Any]], today_iso: str) -> int:
    for idx, ep in enumerate(epochs):
        ef = str(ep.get("effective_from") or "0000-01-01")
        et = ep.get("effective_to")
        if today_iso >= ef and (not et or today_iso <= str(et)):
            return idx
    return 0


def apply_numeric_feed_updates(
    cat: dict[str, Any],
    led: dict[str, Any],
    feed: dict[str, Any],
    today_iso: str,
) -> tuple[bool, dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Apply verified numeric pricing/limit diffs without downgrading curated token floors or touching antigravity_ide."""
    parsed = _extract_numeric_feed_rows(feed)
    new_cat, new_led = deepcopy(cat), deepcopy(led)
    led_models = new_led.setdefault("models", {})
    changed_models: list[str] = []
    prev_day = (date.fromisoformat(today_iso) - timedelta(days=1)).isoformat()

    for m in new_cat.get("models") or []:
        mk = str(m.get("key") or "")
        upd = parsed.get(mk)
        if not upd:
            continue
        pub = m.setdefault("public_api", {})
        mod_changed = False
        for api_k in ("api_context_window", "api_max_output_tokens"):
            nv = upd.get(api_k)
            cur_v = pub.get(api_k)
            cur_int = cur_v if (not isinstance(cur_v, bool) and isinstance(cur_v, int) and cur_v > 0) else 0
            if isinstance(nv, int) and not isinstance(nv, bool) and nv > cur_int:
                pub[api_k] = nv
                mod_changed = True
        epochs = (led_models.setdefault(mk, {})).setdefault("rate_epochs", [])
        if epochs:
            ep_idx = _active_epoch_idx(epochs, today_iso)
            cur_ep = epochs[ep_idx]
            rate_changed = any(
                isinstance(upd.get(rk), int) and upd[rk] >= 0 and cur_ep.get(rk) != upd[rk]
                for rk in ("input_micros", "output_micros", "cache_read_micros")
            )
            if rate_changed:
                src_u = str(upd.get("source_url") or pub.get("source_url") or MODELS_DEV_URL)
                if not is_safe_https_url(src_u):
                    src_u = MODELS_DEV_URL
                in_m = upd["input_micros"] if upd["input_micros"] is not None else int(cur_ep.get("input_micros") or 0)
                out_m = upd["output_micros"] if upd["output_micros"] is not None else int(cur_ep.get("output_micros") or 0)
                ca_m = upd["cache_read_micros"] if upd["cache_read_micros"] is not None else int(cur_ep.get("cache_read_micros") or 0)
                if str(cur_ep.get("effective_from") or "") == today_iso:
                    cur_ep.update({"input_micros": in_m, "output_micros": out_m, "cache_read_micros": ca_m, "source_url": src_u, "verified_at": today_iso})
                else:
                    nxt_ef = str(epochs[ep_idx + 1].get("effective_from") or "") if ep_idx + 1 < len(epochs) else ""
                    nxt_to = (date.fromisoformat(nxt_ef) - timedelta(days=1)).isoformat() if nxt_ef > today_iso else None
                    cur_ep["effective_to"] = prev_day
                    epochs.insert(ep_idx + 1, {
                        "effective_from": today_iso, "effective_to": nxt_to,
                        "input_micros": in_m, "output_micros": out_m, "cache_read_micros": ca_m,
                        "source_url": src_u, "verified_at": today_iso, "note": f"Synced from public rate feed ({today_iso})",
                    })
                mod_changed = True
        if mod_changed:
            pub["verified_at"] = today_iso
            changed_models.append(mk)

    if not changed_models:
        return False, cat, led, {"changed": False, "changed_models": [], "summary_lines": []}
    if assert_antigravity_ide_untouched(cat, new_cat):
        raise RuntimeError("Refusing Price Book update: antigravity_ide lock violation detected.")
    next_rev = max(int(cat.get("catalog_revision") or 1), int(led.get("catalog_revision") or 1)) + 1
    new_cat["catalog_revision"] = next_rev
    new_cat["updated_at"] = today_iso
    new_cat["catalog_version"] = today_iso
    new_led["catalog_revision"] = next_rev
    new_led["updated_at"] = today_iso
    errs = validate_catalog_pair(new_cat, new_led)
    if errs:
        raise ValueError(f"Generated Price Book failed validation: {'; '.join(errs)}")
    diff = compute_catalog_diff((cat, led), (new_cat, new_led))
    return True, new_cat, new_led, {"changed": True, "revision": next_rev, "changed_models": changed_models, "diff": diff}


def cmd_render_docs(*, check_only: bool = False) -> int:
    cat, led = load_bundled_catalog_pair()
    rendered = render_pricing_history_markdown(cat, led)
    if check_only:
        existing = DOCS_HISTORY_PATH.read_text(encoding="utf-8") if DOCS_HISTORY_PATH.is_file() else ""
        if existing != rendered:
            print("[catalog-sync] docs/PRICING_HISTORY.md is out of date. Run: python3 scripts/catalog_sync.py --render-docs", file=sys.stderr)
            return 2
        print("[catalog-sync] docs/PRICING_HISTORY.md matches model_catalog.json + cost_ledger.json.")
        return 0
    DOCS_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOCS_HISTORY_PATH.write_text(rendered, encoding="utf-8")
    print(f"[catalog-sync] Rendered {DOCS_HISTORY_PATH.relative_to(REPO_ROOT)} (rev {cat.get('catalog_revision')}).")
    return 0


def cmd_sync_ci(feed_file: str, pr_summary_out: str) -> int:
    cat, led = load_bundled_catalog_pair()
    today_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if feed_file:
        feed = parse_catalog_json_bytes(
            read_bounded_regular_file(Path(feed_file), max_bytes=MAX_FEED_BYTES),
            max_bytes=MAX_FEED_BYTES,
        )
    else:
        ok, feed, err = _fetch_models_dev_feed()
        if not ok:
            out = {"changed": False, "status": "FAIL_CLOSED", "error": err}
            if pr_summary_out:
                Path(pr_summary_out).write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
            print(f"[catalog-sync] {err}")
            return 0
    changed, new_cat, new_led, summary = apply_numeric_feed_updates(cat, led, feed, today_iso)
    if changed:
        REPO_CATALOG_PATH.write_text(json.dumps(new_cat, indent=2) + "\n", encoding="utf-8")
        REPO_LEDGER_PATH.write_text(json.dumps(new_led, indent=2) + "\n", encoding="utf-8")
        cmd_render_docs(check_only=False)
    if pr_summary_out:
        Path(pr_summary_out).write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"[catalog-sync] changed={changed} models={summary.get('changed_models', [])}")
    return 0


def cmd_propose_local_pr(model_code: str, model_key: str, *, push: bool = False) -> int:
    code = (model_code or "").strip().upper()
    if not code:
        print("[catalog-sync] Provide --model-code MODEL_PLACEHOLDER_M* to stage a local catalog PR.", file=sys.stderr)
        return 2
    cat, led = load_bundled_catalog_pair()
    target_key = (model_key or "").strip().lower()
    if target_key:
        for m in cat.get("models") or []:
            if str(m.get("key") or "") == target_key:
                phs = m.setdefault("antigravity_ide", {}).setdefault("placeholders", [])
                if code not in phs:
                    phs.append(code)
                    next_rev = max(int(cat.get("catalog_revision") or 1), int(led.get("catalog_revision") or 1)) + 1
                    today_s = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    cat["catalog_revision"] = next_rev
                    cat["updated_at"] = today_s
                    led["catalog_revision"] = next_rev
                    led["updated_at"] = today_s
                    errs = validate_catalog_pair(cat, led)
                    if errs:
                        print(f"[catalog-sync] Validation failed: {'; '.join(errs[:3])}", file=sys.stderr)
                        return 2
                    REPO_CATALOG_PATH.write_text(json.dumps(cat, indent=2) + "\n", encoding="utf-8")
                    REPO_LEDGER_PATH.write_text(json.dumps(led, indent=2) + "\n", encoding="utf-8")
                    cmd_render_docs(check_only=False)
    branch_cmd = ["git", "checkout", "-B", "bot/catalog-sync"]
    if push:
        subprocess.run(branch_cmd, cwd=str(REPO_ROOT), check=True)
    else:
        print(f"[catalog-sync] Dry-run staged proposal for {code} (target={target_key or 'unassigned'}).")
        print(f"[catalog-sync] Next step when ready: {' '.join(branch_cmd)} -> commit -> open PR to main")
    return 0


def cmd_validate_strict(*, require_jsonschema: bool = False, as_json: bool = False) -> int:
    ok, errs, info = validate_catalog_files_strict(
        REPO_CATALOG_PATH, REPO_LEDGER_PATH, require_jsonschema=require_jsonschema,
    )
    payload = {"ok": ok, **info, "errors": errs}
    if as_json:
        print(json.dumps(payload, indent=2))
    elif ok:
        print(
            f"[catalog-sync] --validate-strict PASS: rev={info.get('catalog_revision')} "
            f"models={info.get('model_count')} jsonschema={info.get('jsonschema_checked')}"
        )
    else:
        for e in errs:
            print(f"[catalog-sync] VALIDATION ERROR: {e}", file=sys.stderr)
    return 0 if ok else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="AGY-Nexus two-file Price Book sync, docs renderer, and PR bot.")
    parser.add_argument("--render-docs", action="store_true", help="Render docs/PRICING_HISTORY.md from repo JSON truth files.")
    parser.add_argument("--check", action="store_true", help="Verify docs/PRICING_HISTORY.md matches generated output.")
    parser.add_argument("--validate-strict", action="store_true", help="Run strict schema and anti-injection security validation.")
    parser.add_argument("--require-jsonschema", action="store_true", help="Fail if optional jsonschema package is absent.")
    parser.add_argument("--check-upstream", action="store_true", help="Run read-only upstream main Price Book check.")
    parser.add_argument("--sync-ci", action="store_true", help="Run fail-closed CI numeric rate sync.")
    parser.add_argument("--feed-file", default="", help="Optional local feed JSON file for deterministic sync tests.")
    parser.add_argument("--pr-summary-out", default="", help="Write JSON sync summary payload to this path.")
    parser.add_argument("--propose-local-pr", action="store_true", help="Stage a local bot/catalog-sync PR proposal for new IDE M* codes.")
    parser.add_argument("--model-code", default="", help="New MODEL_PLACEHOLDER_M* code to propose.")
    parser.add_argument("--model-key", default="", help="Target canonical model key for --model-code.")
    parser.add_argument("--push", action="store_true", help="Actually switch branch in --propose-local-pr (disabled by default).")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args()

    if args.validate_strict:
        return cmd_validate_strict(require_jsonschema=args.require_jsonschema, as_json=args.json)
    if args.render_docs:
        return cmd_render_docs(check_only=args.check)
    if args.sync_ci:
        return cmd_sync_ci(args.feed_file, args.pr_summary_out)
    if args.propose_local_pr:
        return cmd_propose_local_pr(args.model_code, args.model_key, push=args.push)
    st = get_catalog_sync_status(refresh=True)
    if args.json:
        print(json.dumps(st, indent=2))
    else:
        print(f"[catalog-sync] status={st['status']} branch={st.get('upstream_branch', 'main')} effective=r{st['effective_revision']} upstream=r{st['upstream_revision']} update={st['update_available']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
