"""Regression tests for Round 7 8-model pricing catalog, ledger persistence, whiskers, billing, drift, sync, and ASCII parity."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from agy_nexus import (
    ascii_default,
    ascii_models,
    ascii_rich,
    config as cfg,
    cost_ledger,
    model_pricing,
    stats,
    tools_ops,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_script_module(rel_path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, str(REPO_ROOT / rel_path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_eight_model_classification_and_distinct_placeholders() -> None:
    """All 8 live models classify deterministically, keeping M417 Argon distinct from M427 Carbon."""
    keys = model_pricing.get_canonical_model_keys()
    assert keys == (
        "carbon",
        "neon",
        "argon",
        "hydrogen",
        "flash_3_8",
        "claude_opus_5_5",
        "claude_sonnet_5_5",
        "gpt_oss_120b",
    )
    assert model_pricing.classify_model_key("MODEL_PLACEHOLDER_M417") == "argon"
    assert model_pricing.classify_model_key("MODEL_PLACEHOLDER_M418") == "argon"
    assert model_pricing.classify_model_key("MODEL_PLACEHOLDER_M419") == "argon"
    assert model_pricing.classify_model_key("MODEL_PLACEHOLDER_M427") == "carbon"
    assert model_pricing.classify_model_key("MODEL_PLACEHOLDER_M437") == "carbon"
    assert model_pricing.classify_model_key("MODEL_PLACEHOLDER_M438") == "carbon"
    assert model_pricing.classify_model_key("gemini-4-neon-high") == "neon"
    assert model_pricing.classify_model_key("gemini-4-hydrogen") == "hydrogen"
    assert model_pricing.classify_model_key("gemini-3.6-flash") == "flash_3_8"
    assert model_pricing.classify_model_key("claude-opus-5-5-thinking") == "claude_opus_5_5"
    assert model_pricing.classify_model_key("claude-sonnet-5-5-thinking") == "claude_sonnet_5_5"
    assert model_pricing.classify_model_key("gpt-oss-120b-medium") == "gpt_oss_120b"


def test_effective_dated_micro_usd_rates_and_overrides(tmp_path: Path, monkeypatch) -> None:
    """Verify exact micro-USD epoch transitions and file/env price overrides."""
    pre_dec = model_pricing.resolve_rate_epoch("carbon", "2026-11-22", bg_dir=tmp_path)
    post_dec = model_pricing.resolve_rate_epoch("carbon", "2026-12-01", bg_dir=tmp_path)
    fore_dec = model_pricing.resolve_rate_epoch("carbon", "2026-11-22", forecast=True, bg_dir=tmp_path)
    assert pre_dec["input_micros"] == 2_000_000 and pre_dec["output_micros"] == 10_000_000 and pre_dec["cache_read_micros"] == 100_000
    assert post_dec["input_micros"] == 4_000_000 and post_dec["output_micros"] == 20_000_000 and post_dec["cache_read_micros"] == 200_000
    assert fore_dec["input_micros"] == 4_000_000

    fl_26 = model_pricing.resolve_rate_epoch("flash_3_8", "2026-12-31", bg_dir=tmp_path)
    fl_27 = model_pricing.resolve_rate_epoch("flash_3_8", "2027-01-01", bg_dir=tmp_path)
    assert fl_26["input_micros"] == 750_000 and fl_27["input_micros"] == 1_500_000

    opus = model_pricing.resolve_rate_epoch("claude_opus_5_5", "2026-11-22", bg_dir=tmp_path)
    sonnet = model_pricing.resolve_rate_epoch("claude_sonnet_5_5", "2026-11-22", bg_dir=tmp_path)
    assert opus["input_micros"] == 4_000_000 and sonnet["input_micros"] == 2_000_000

    cost_m = model_pricing.compute_step_cost_micros("carbon", "2026-11-22", 1_000_000, 1_000_000, 1_000_000, bg_dir=tmp_path)
    assert cost_m == 12_100_000  # $2.00 + $0.10 + $10.00 = $12.10

    override_file = tmp_path / "model_price_overrides.json"
    override_file.write_text(json.dumps({"gpt_oss_120b": {"input_micros": 1_000_000, "output_micros": 2_000_000, "cache_read_micros": 100_000}}), encoding="utf-8")
    gpt_file_ovr = model_pricing.resolve_rate_epoch("gpt_oss_120b", "2026-11-22", bg_dir=tmp_path)
    assert gpt_file_ovr["input_micros"] == 1_000_000 and gpt_file_ovr["output_micros"] == 2_000_000

    monkeypatch.setenv("AGY_MODEL_PRICE_OVERRIDES", json.dumps({"gpt_oss_120b": {"input_micros": 500_000, "output_micros": 1_500_000, "cache_read_micros": 50_000}}))
    gpt_env_ovr = model_pricing.resolve_rate_epoch("gpt_oss_120b", "2026-11-22", bg_dir=tmp_path)
    assert gpt_env_ovr["input_micros"] == 500_000 and gpt_env_ovr["output_micros"] == 1_500_000


def test_cost_ledger_preserves_pruned_brain_history_and_stats_rollup(tmp_path: Path) -> None:
    """Historical spend persists in cost_ledger.json and folds back into stats even after brain dir deletion."""
    bg_dir = tmp_path / "bg"
    bg_dir.mkdir()
    data_dir = tmp_path / "data"
    brain_dir = tmp_path / "brain"
    cfg_dir = tmp_path / "config"
    data_dir.mkdir()
    brain_dir.mkdir()
    cfg_dir.mkdir()

    old_cid = "aaaa1111-1111-4111-8111-111111111111"
    live_cid = "bbbb2222-2222-4222-8222-222222222222"
    today_iso = date.today().strftime("%Y-%m-%d")
    old_raw_cdata = {
        "mtime": 1_790_000_000,
        "size": 1024,
        "day_models": {today_iso: {"carbon": 4}},
        "day_model_tokens": {today_iso: {"carbon": 1_000_000}},
        "day_model_token_splits": {today_iso: {"carbon": [1_000_000, 0, 0]}},
    }
    built_entry = cost_ledger.build_conv_ledger_entry(
        old_cid,
        old_raw_cdata,
        project_id="ws:demo-proj",
        project_name="Demo Proj",
        workspace="/home/dev/agentic_workspace/projects/demo-proj",
        bg_dir=bg_dir,
    )
    assert built_entry["by_date_model"][today_iso]["carbon"]["cost_usd_micros"] == 2_000_000
    ledger = cost_ledger.merge_and_persist_cost_ledger(
        bg_dir,
        {old_cid: old_raw_cdata},
        db_convs={old_cid: {"title": "Archived Chat", "project_id": "ws:demo-proj", "workspace": "/home/dev/agentic_workspace/projects/demo-proj"}},
    )
    assert old_cid in ledger["conversations"]
    ledger_path = bg_dir / "cost_ledger.json"
    assert ledger_path.is_file()
    assert (os.stat(ledger_path).st_mode & 0o777) == 0o600

    # Simulate brain cleanup removing old_cid completely while live_cid continues cleanly
    archived = cost_ledger.collect_archived_ledger_totals(ledger, {live_cid}, today_iso, today_iso)
    assert archived["archived_convs"] == 1
    assert archived["model_tokens"]["carbon"] == 1_000_000
    assert archived["model_cost_micros"]["carbon"] == model_pricing.compute_step_cost_micros("carbon", today_iso, 1_000_000, 0, 0, bg_dir=bg_dir)

    live_brain = brain_dir / live_cid / ".system_generated" / "logs"
    live_brain.mkdir(parents=True)
    transcript_row = {
        "step_index": 0,
        "type": "PLANNER_RESPONSE",
        "created_at": f"{today_iso}T10:15:00Z",
        "model": "gemini-3.8-flash",
        "token_usage": {"input_tokens": 200_000, "output_tokens": 20_000, "cache_read_input_tokens": 0},
    }
    (live_brain / "transcript.jsonl").write_text(json.dumps(transcript_row) + "\n", encoding="utf-8")

    bundle = stats.build_nexus_stats_bundle(
        data_dir=data_dir,
        brain_dir=brain_dir,
        db_file=tmp_path / "missing.vscdb",
        config_dir=cfg_dir,
        bg_dir=bg_dir,
        period="current_month",
        include_ascii=True,
    )
    rows_by_key = {r["model_key"]: r for r in bundle["model_usage_vs_target"]}
    assert rows_by_key["carbon"]["est_tokens"] >= 1_000_000
    assert rows_by_key["carbon"]["est_cost_usd"] > 0.0
    assert bundle["kpis"]["window_cost_usd"] >= rows_by_key["carbon"]["est_cost_usd"]
    ascii_out = bundle.get("ascii_report_default") or ""
    assert "BILLING" in ascii_out
    for ln in ascii_out.splitlines():
        assert len(ln) <= 72, f"default ASCII exceeded 72 chars ({len(ln)}): {ln}"


def test_hourly_whiskers_and_billing_comparison() -> None:
    """Verify active-day Min/Avg/Max ordering, closed-window last_24h suppression, and 4-tier break-even math."""
    s1_steps = {"2026-11-01T10": 10, "2026-11-02T10": 30, "2026-11-03T10": 20}
    s1_toks = {"2026-11-01T10": 1000, "2026-11-02T10": 3000, "2026-11-03T10": 2000}
    s1_cost = {"2026-11-01T10": 500_000, "2026-11-02T10": 1_500_000, "2026-11-03T10": 1_000_000}

    closed = cost_ledger.compute_hourly_whiskers(
        s1_steps, s1_toks, s1_cost,
        date(2026, 11, 1), date(2026, 11, 5), date(2026, 11, 22), 14,
    )
    assert closed["has_last_24h"] is False
    h10 = closed["steps"][10]
    assert h10["min"] == 10 and h10["avg"] == 20.0 and h10["max"] == 30 and h10["active_days"] == 3
    assert h10["last_24h"] is None
    assert closed["cost"][10]["avg"] == 1.0

    bill = model_pricing.build_billing_comparison(
        250_000_000, 500_000_000, window_days=30, active_days=10, active_profile="ultra-20x",
    )
    assert bill["historical_usd"] == 250.0 and bill["forecast_usd"] == 500.0 and bill["forecast_delta_pct"] == 100.0
    assert len(bill["tiers"]) == 4
    plus = next(t for t in bill["tiers"] if t["id"] == "google_ai_plus")
    pro = next(t for t in bill["tiers"] if t["id"] == "google_ai_pro")
    ultra5 = next(t for t in bill["tiers"] if t["id"] == "google_ai_ultra_5x")
    ultra20 = next(t for t in bill["tiers"] if t["id"] == "google_ai_ultra_20x")
    assert plus["monthly_usd"] == 4.99 and plus["storage"] == "400 GB"
    assert pro["monthly_usd"] == 19.99 and pro["storage"] == "5 TB"
    assert ultra5["monthly_usd"] == 99.99 and ultra5["storage"] == "20 TB"
    assert ultra20["monthly_usd"] == 199.99 and ultra20["storage"] == "30 TB"
    assert ultra20["value_multiplier"] == pytest.approx(250.0 / 199.99, rel=1e-2)


def test_deadbolt_safe_models_ascii_vs_locked_boundaries(tmp_path: Path, monkeypatch) -> None:
    """style=ascii without skills/rules bypasses Deadbolt; include_skills/rules/json remain blocked."""
    monkeypatch.setattr(cfg, "PASS_HASH", cfg.normalize_phrase("canary passphrase round 7"))
    cfg.SESSION_STATE["unlocked_at"] = 0.0
    monkeypatch.setattr(cfg, "ALLOW_LOCKED_STATS", False)

    locked_json = tools_ops.list_models_and_agents(style="json", include_skills=False, include_rules=False)
    assert "LOCKED" in locked_json or "passphrase" in locked_json.lower()

    locked_skills = tools_ops.list_models_and_agents(style="ascii", include_skills=True, include_rules=False)
    assert "LOCKED" in locked_skills or "passphrase" in locked_skills.lower()

    locked_rules = tools_ops.list_models_and_agents(style="ascii", include_skills=False, include_rules=True)
    assert "LOCKED" in locked_rules or "passphrase" in locked_rules.lower()

    models_out = json.loads(tools_ops.list_models_and_agents(style="ascii", include_skills=False, include_rules=False))
    bg_out = json.loads(tools_ops.manage_background_run(action="models", style="ascii"))
    assert models_out["ok"] is True and bg_out["ok"] is True
    assert models_out["style"] == "ascii" and bg_out["style"] == "ascii"
    rep_a = models_out["ascii_models_report"]
    rep_b = bg_out["ascii_models_report"]
    assert rep_a == rep_b
    for label in ("Carbon 4", "Neon 4", "Argon 4", "Hydrogen 4", "Flash 3.8", "Opus 5.5", "Sonnet 5.5", "GPT-OSS 120"):
        assert label in rep_a
    for price in ("$4.99", "$19.99", "$99.99", "$199.99"):
        assert price in rep_a, f"Missing tier price {price} in ascii_models report"
    assert not re.search(r"/home/(?!dev(?:/|$))[A-Za-z0-9_.-]+", rep_a)
    for ln in rep_a.splitlines():
        assert len(ln) <= 76, f"models report line > 76 ({len(ln)}): {ln}"


def test_ascii_width_parity_and_renderers(tmp_path: Path) -> None:
    """All three dashboard ASCII renderers and the models status renderer stay within column guarantees."""
    b = stats.build_nexus_stats_bundle(
        data_dir=tmp_path / "missing_d",
        brain_dir=tmp_path / "missing_b",
        db_file=tmp_path / "missing.vscdb",
        config_dir=tmp_path / "missing_c",
        bg_dir=tmp_path / "missing_bg",
        period="current_month",
        include_ascii=False,
    )
    def_s = ascii_default.render_ascii_default(b)
    qck_s = ascii_default.render_ascii_quick(b)
    rch_s = ascii_rich.render_ascii_rich(b)
    mod_s = ascii_models.render_ascii_models_status(ls_configs=[])

    assert all(len(ln) <= 72 for ln in def_s.splitlines())
    assert all(len(ln) <= 40 for ln in qck_s.splitlines())
    assert all(len(ln) == 76 for ln in rch_s.splitlines() if ln)
    assert all(len(ln) == 76 for ln in mod_s.splitlines() if ln)


def test_drift_checker_mock_and_sync_agents_check(tmp_path: Path, monkeypatch) -> None:
    """check_model_drift writes 0600 status JSON on OK & DRIFT_DETECTED; sync_agents --check succeeds."""
    drift_mod = _load_script_module("scripts/check_model_drift.py", "agy_check_model_drift_test")
    sync_mod = _load_script_module("scripts/sync_agents.py", "agy_sync_agents_test")

    monkeypatch.setattr(drift_mod, "_check_local_language_server", lambda _cat: ({"status": "OK", "checked_models": 8}, []))
    monkeypatch.setattr(drift_mod, "_check_gemini_api", lambda _cat: ({"status": "OK"}, []))
    monkeypatch.setattr(
        drift_mod,
        "_check_public_rate_feeds",
        lambda _cat, _today: (
            {"models_dev": {"status": "OK"}},
            [{"source": "models.dev", "model_key": "claude_opus_5_5", "detail": "rate delta"}],
        ),
    )
    out = drift_mod.run_drift_check(bg_dir=tmp_path, strict=True)
    assert out["status"] == "DRIFT_DETECTED" and out["drift_count"] == 1 and out["strict_exit_code"] == 2
    st_path = tmp_path / "model_drift_status.json"
    assert st_path.is_file() and (os.stat(st_path).st_mode & 0o777) == 0o600

    res = sync_mod.check_agent_sync()
    assert res["ok"] is True and res["total"] >= 10

    # Zero OK sources must report UNREACHABLE (never silent OK)
    monkeypatch.setattr(drift_mod, "_check_local_language_server", lambda _cat: ({"status": "UNREACHABLE", "checked_models": 0}, []))
    monkeypatch.setattr(drift_mod, "_check_gemini_api", lambda _cat: ({"status": "SKIPPED_NO_API_KEY"}, []))
    monkeypatch.setattr(drift_mod, "_check_public_rate_feeds", lambda _c, _t: ({"models_dev": {"status": "UNREACHABLE"}, "litellm": {"status": "UNREACHABLE"}}, []))
    unr = drift_mod.run_drift_check(bg_dir=tmp_path)
    assert unr["status"] == "UNREACHABLE"

    with pytest.raises(ValueError):
        sync_mod.apply_agent_sync(sync_mod.DEFAULT_SOURCE_DIR, sync_mod.DEFAULT_SOURCE_DIR)


def test_dual_review_p1_invariants(tmp_path: Path) -> None:
    """Verify pre-epoch fallback, malformed override safety, closed-yesterday whiskers, and subagent/archived ledger parity."""
    # 1. Pre-epoch dates never fall forward to future epochs; malformed overrides are ignored safely.
    pre = model_pricing.resolve_rate_epoch("carbon", "2024-01-01", bg_dir=tmp_path)
    assert pre["input_micros"] == 2_000_000
    (tmp_path / "model_price_overrides.json").write_text(
        json.dumps({"carbon": {"input_micros": True, "output_micros": "bad", "cache_read_micros": -5}}),
        encoding="utf-8",
    )
    safe_ov = model_pricing.resolve_rate_epoch("carbon", "2026-11-22", bg_dir=tmp_path)
    assert safe_ov["input_micros"] == 2_000_000 and safe_ov["cache_read_micros"] == 0

    # 2. Closed past window ending yesterday must suppress Last 24h dots completely.
    closed_yest = cost_ledger.compute_hourly_whiskers(
        {"2026-11-21T20": 5}, {"2026-11-21T20": 500}, {"2026-11-21T20": 1000},
        date(2026, 11, 1), date(2026, 11, 21), date(2026, 11, 22), 14,
    )
    assert closed_yest["has_last_24h"] is False
    assert all(r["last_24h"] is None for r in closed_yest["steps"])

    # 3. Canonical archived project ID + subagent daily_cost repricing parity.
    raw_sub = {
        "mtime": 1_790_000_000, "size": 512,
        "day_steps": {"2026-11-20": 2},
        "day_models": {"2026-11-20": {"argon": 2}},
        "day_model_tokens": {"2026-11-20": {"argon": 1_000_000}},
        "day_model_cost_micros": {"2026-11-20": {"argon": 2_000_000}},
        "day_cost_micros": {"2026-11-20": 2_000_000},
        "day_model_token_splits": {"2026-11-20": {"argon": [1_000_000, 0, 0]}},
    }
    ledger = cost_ledger.merge_and_persist_cost_ledger(
        tmp_path,
        {"sub-1": raw_sub},
        db_convs={"sub-1": {"is_subagent": True, "agent_name": "flash-surgeon", "workspace": "/home/dev/projects/demo-proj"}},
        agent_target_map={"flash-surgeon": "flash_3_8"},
    )
    arch = cost_ledger.collect_archived_ledger_totals(ledger, set(), "2026-11-01", "2026-11-30", allowed_project_id="ws:demo-proj")
    assert arch["ws_map"]["demo-proj"]["cost_usd_micros"] == 750_000
    assert arch["subagent_roles"]["flash-surgeon"]["cost_usd_micros"] == 750_000
    assert arch["model_cost_micros"]["flash_3_8"] == 750_000

