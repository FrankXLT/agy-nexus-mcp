#!/usr/bin/env python3
"""agy_nexus.model_pricing — 8-Model Catalog, Effective-Dated Micro-USD Pricing & Billing Math."""
from __future__ import annotations

import functools
import json
import os
from pathlib import Path
from typing import Any

CATALOG_PATH = Path(__file__).resolve().parent / "data" / "model_catalog.json"
DEFAULT_SPLIT = (0.05, 0.94, 0.01)


@functools.lru_cache(maxsize=1)
def load_model_catalog() -> dict[str, Any]:
    """Load and cache the git-tracked model_catalog.json."""
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def get_canonical_model_keys() -> tuple[str, ...]:
    """Return all canonical model keys in display order."""
    return tuple(str(m["key"]) for m in load_model_catalog().get("models") or [])


def get_model_specs_map() -> dict[str, dict[str, Any]]:
    """Return mapping of canonical model_key -> catalog spec."""
    return {str(m["key"]): m for m in load_model_catalog().get("models") or []}


def get_placeholder_map() -> dict[str, dict[str, str]]:
    """Build exact MODEL_PLACEHOLDER_* -> metadata mapping for main-chat & transcript resolution."""
    out: dict[str, dict[str, str]] = {}
    for m in load_model_catalog().get("models") or []:
        mk, lbl, pool = str(m["key"]), str(m["label"]), str(m["pool_label"])
        tier_by_ph = {str(v): str(t) for t, v in (m.get("tier_placeholders") or {}).items()}
        for ph in m.get("placeholders") or []:
            t_lbl = tier_by_ph.get(str(ph), "")
            out[str(ph)] = {
                "id": str(ph),
                "model_key": mk,
                "label": lbl,
                "tier_label": f"{lbl} ({t_lbl})" if t_lbl else lbl,
                "pool": pool,
                "pool_key": str(m["pool_key"]),
                "subagent_inherit": lbl,
            }
    return out


def get_target_allocation_map(profile: str = "ultra-20x") -> dict[str, dict[str, Any]]:
    """Return per-model target percentage map for ultra-20x or ultra-5x."""
    prof = (profile or "ultra-20x").strip().lower()
    if prof not in ("ultra-20x", "ultra-5x"):
        prof = "ultra-20x"
    out: dict[str, dict[str, Any]] = {}
    for m in load_model_catalog().get("models") or []:
        tmap = m.get("target_pct") or {}
        out[str(m["key"])] = {
            "label": str(m["label"]),
            "short_label": str(m["short_label"]),
            "pool": str(m["pool_label"]),
            "pool_key": str(m["pool_key"]),
            "quota_group": str(m["quota_group"]),
            "target_pct": float(tmap.get(prof, tmap.get("ultra-20x", 0.0))),
        }
    return out


def classify_model_key(raw_model: str, agent_name: str = "") -> str:
    """Resolve placeholder ID, model slug, or agent name to one of the 8 canonical model keys."""
    raw_up = (raw_model or "").strip().upper()
    ph_map = get_placeholder_map()
    if raw_up in ph_map:
        return ph_map[raw_up]["model_key"]
    specs = get_model_specs_map()
    raw_low = (raw_model or "").strip().lower()
    if raw_low in specs:
        return raw_low
    for m in specs.values():
        mids = {str(x).lower() for x in (m.get("model_ids") or [])}
        aliases = {str(x).lower() for x in (m.get("aliases") or [])}
        if raw_low in mids or raw_low in aliases:
            return str(m["key"])
    s = f"{raw_model or ''} {agent_name or ''}".lower()
    if "opus" in s:
        return "claude_opus_5_5"
    if "sonnet" in s or "claude" in s:
        return "claude_sonnet_5_5"
    if "gpt" in s or "120b" in s:
        return "gpt_oss_120b"
    if "neon" in s:
        return "neon"
    if "hydrogen" in s:
        return "hydrogen"
    if "flash" in s or "3.8" in s or "3.6" in s or "m318" in s or "m319" in s or "m320" in s or "m322" in s:
        return "flash_3_8"
    if "carbon" in s or "m427" in s or "m437" in s or "m438" in s:
        return "carbon"
    if "argon" in s or "m417" in s or "m418" in s or "m419" in s:
        return "argon"
    return "argon"


def _load_price_overrides(bg_dir: Path | None = None) -> dict[str, dict[str, int]]:
    overrides: dict[str, dict[str, int]] = {}
    if bg_dir:
        ov_file = bg_dir / "model_price_overrides.json"
        if ov_file.is_file():
            try:
                loaded = json.loads(ov_file.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    overrides.update(loaded)
            except Exception:
                pass
    env_raw = os.getenv("AGY_MODEL_PRICE_OVERRIDES", "").strip()
    if env_raw:
        try:
            loaded = json.loads(env_raw)
            if isinstance(loaded, dict):
                overrides.update(loaded)
        except Exception:
            pass
    return overrides


def resolve_rate_epoch(
    model_key: str,
    date_iso: str,
    *,
    forecast: bool = False,
    bg_dir: Path | None = None,
) -> dict[str, Any]:
    """Return the active (or upcoming forecast) rate epoch in integer micro-USD per 1M tokens."""
    specs = get_model_specs_map()
    spec = specs.get(model_key) or specs["argon"]
    epochs = list(spec.get("rate_epochs") or [])
    if not epochs:
        return {"input_micros": 0, "output_micros": 0, "cache_read_micros": 0, "note": ""}
    chosen = dict(epochs[-1] if forecast else epochs[0])
    if not forecast and date_iso:
        d_day = date_iso[:10]
        for ep in epochs:
            ef = str(ep.get("effective_from") or "0000-01-01")
            et = ep.get("effective_to")
            if d_day >= ef and (not et or d_day <= str(et)):
                chosen = dict(ep)
                break
        else:
            if d_day > str(epochs[0].get("effective_to") or "9999-12-31"):
                chosen = dict(epochs[-1])
    overrides = _load_price_overrides(bg_dir)
    if model_key in overrides and isinstance(overrides[model_key], dict):
        for k in ("input_micros", "output_micros", "cache_read_micros"):
            v = overrides[model_key].get(k)
            if v is not None and not isinstance(v, bool):
                try:
                    chosen[k] = max(0, int(v))
                except (TypeError, ValueError):
                    pass
        chosen["note"] = "Configured override"
    return chosen


def compute_step_cost_micros(
    model_key: str,
    date_iso: str,
    uncached_input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
    *,
    forecast: bool = False,
    bg_dir: Path | None = None,
) -> int:
    """Compute exact integer micro-USD cost for one step at the effective rate epoch."""
    ep = resolve_rate_epoch(model_key, date_iso, forecast=forecast, bg_dir=bg_dir)
    in_m = int(ep.get("input_micros") or 0)
    out_m = int(ep.get("output_micros") or 0)
    ca_m = int(ep.get("cache_read_micros") or 0)
    total_raw = (
        max(0, int(uncached_input_tokens)) * in_m
        + max(0, int(output_tokens)) * out_m
        + max(0, int(cached_input_tokens)) * ca_m
    )
    if total_raw <= 0:
        return 0
    return (total_raw + 500_000) // 1_000_000


def split_estimated_tokens(total_tokens: int) -> tuple[int, int, int]:
    """Split legacy/estimated total tokens into (uncached_input, cached_input, output) matching empirical ratios."""
    tot = max(0, int(total_tokens or 0))
    if tot <= 0:
        return 0, 0, 0
    cfg_split = load_model_catalog().get("fallback_token_split") or {}
    r_in = float(cfg_split.get("uncached_input_ratio", DEFAULT_SPLIT[0]))
    r_ca = float(cfg_split.get("cached_input_ratio", DEFAULT_SPLIT[1]))
    u_in = int(round(tot * r_in))
    c_in = int(round(tot * r_ca))
    out_t = max(0, tot - u_in - c_in)
    return u_in, c_in, out_t


def build_billing_comparison(
    historical_cost_micros: int,
    forecast_cost_micros: int,
    *,
    window_days: int = 30,
    active_days: int = 1,
    active_profile: str = "ultra-20x",
    drift_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute Subscription Break-Even & Client Billing comparison payload."""
    cat = load_model_catalog()
    months_factor = max(1.0, float(max(1, window_days)) / 30.0)
    hist_usd = round(historical_cost_micros / 1_000_000.0, 2)
    fore_usd = round(forecast_cost_micros / 1_000_000.0, 2)
    delta_usd = round(fore_usd - hist_usd, 2)
    delta_pct = round(((fore_usd - hist_usd) / hist_usd) * 100.0, 1) if hist_usd > 0 else 0.0
    tiers = []
    for t in cat.get("subscription_tiers") or []:
        mo_usd = int(t.get("monthly_usd_micros") or 0) / 1_000_000.0
        prorated_sub = round(mo_usd * months_factor, 2)
        net_savings = round(hist_usd - prorated_sub, 2)
        mult = round(hist_usd / prorated_sub, 2) if prorated_sub > 0 else 0.0
        tiers.append({
            "id": str(t.get("id") or ""),
            "label": str(t.get("label") or ""),
            "monthly_usd": round(mo_usd, 2),
            "included_credits_usd": round(int(t.get("included_credits_usd_micros") or 0) / 1_000_000.0, 2),
            "window_cost_usd": prorated_sub,
            "net_savings_usd": net_savings,
            "value_multiplier": mult,
            "notes": str(t.get("notes") or ""),
        })
    drift = drift_status or {}
    return {
        "active_profile": active_profile,
        "window_days": max(1, int(window_days)),
        "active_days": max(1, int(active_days)),
        "months_factor": round(months_factor, 2),
        "historical_usd": hist_usd,
        "historical_cost_micros": int(historical_cost_micros),
        "forecast_usd": fore_usd,
        "forecast_cost_micros": int(forecast_cost_micros),
        "forecast_delta_usd": delta_usd,
        "forecast_delta_pct": delta_pct,
        "avg_usd_per_active_day": round(hist_usd / max(1, active_days), 2),
        "tiers": tiers,
        "drift_status": {
            "status": str(drift.get("status") or "UNKNOWN"),
            "checked_at": str(drift.get("checked_at") or ""),
            "drift_count": int(drift.get("drift_count") or 0),
            "summary": str(drift.get("summary") or "Drift check pending"),
        },
    }


def format_usd(usd_or_micros: float | int, *, from_micros: bool = False) -> str:
    """Format USD amounts compactly for tables and ASCII columns."""
    val = (float(usd_or_micros or 0) / 1_000_000.0) if from_micros else float(usd_or_micros or 0.0)
    if val >= 1000.0:
        return f"${val:,.0f}"
    if val >= 10.0:
        return f"${val:.1f}"
    return f"${val:.2f}"
