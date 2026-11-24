#!/usr/bin/env python3
"""agy_nexus.catalog_report — Unmapped M* Alerts, Subagent Adjudication & Price Book Docs."""
from __future__ import annotations

from typing import Any
import urllib.parse

GITHUB_REPO_ISSUES_URL = "https://github.com/FrankXLT/agy-nexus-mcp/issues/new"
_IGNORED_UNMAPPED = frozenset({"", "auto", "default", "none", "null", "unspecified", "inherit", "flash", "flash_lite", "pro"})


def record_unmapped_model_hit(
    bucket: dict[str, dict[str, Any]],
    raw_id: str,
    tokens: int,
    seen_ts: str,
    day_s: str,
) -> None:
    """Record one unmapped raw model barcode occurrence into a per-transcript accumulator."""
    code = (raw_id or "").strip()
    if code.lower() in _IGNORED_UNMAPPED:
        return
    rec = bucket.setdefault(code, {"steps": 0, "tokens": 0, "last_seen": "", "days": {}})
    rec["steps"] += 1
    rec["tokens"] += max(0, int(tokens or 0))
    if seen_ts and seen_ts > str(rec["last_seen"] or ""):
        rec["last_seen"] = seen_ts
    if day_s:
        days = rec["days"]
        d_rec = days.setdefault(day_s, {"steps": 0, "tokens": 0})
        d_rec["steps"] += 1
        d_rec["tokens"] += max(0, int(tokens or 0))


def fold_unmapped_models(
    dst: dict[str, dict[str, Any]],
    src: dict[str, dict[str, Any]] | None,
    s_iso: str,
    e_iso: str,
) -> None:
    """Aggregate per-conversation unmapped model observations scoped to [s_iso, e_iso]."""
    if not isinstance(src, dict):
        return
    for raw_id, info in src.items():
        if not isinstance(info, dict):
            continue
        days = info.get("days")
        st_sum, tok_sum = 0, 0
        if isinstance(days, dict) and days:
            for d_s, dv in days.items():
                if s_iso <= str(d_s) <= e_iso and isinstance(dv, dict):
                    st_sum += int(dv.get("steps") or 0)
                    tok_sum += int(dv.get("tokens") or 0)
        else:
            ls_day = str(info.get("last_seen") or "")[:10]
            if not ls_day or (s_iso <= ls_day <= e_iso):
                st_sum = int(info.get("steps") or 0)
                tok_sum = int(info.get("tokens") or 0)
        if st_sum <= 0:
            continue
        cur = dst.setdefault(str(raw_id), {"id": str(raw_id), "steps": 0, "tokens": 0, "last_seen": ""})
        cur["steps"] += st_sum
        cur["tokens"] += tok_sum
        ls = str(info.get("last_seen") or "")
        if ls and ls > str(cur["last_seen"] or ""):
            cur["last_seen"] = ls


def build_unmapped_issue_url(unmapped_models: list[dict[str, Any]]) -> str:
    """Build a 1-click pre-filled GitHub Issue URL to report unmapped M* model barcodes."""
    if not unmapped_models:
        return ""
    codes = [str(m.get("id") or "") for m in unmapped_models[:5] if str(m.get("id") or "")]
    title = f"[Catalog] Unmapped model code(s): {', '.join(codes)}"
    rows = [
        f"- `{m.get('id', '')}` — {int(m.get('steps') or 0)} steps, {int(m.get('tokens') or 0)} tokens, last seen `{m.get('last_seen', '')}`"
        for m in unmapped_models[:10]
    ]
    body = "\n".join([
        "### Unmapped Antigravity / Transcript Model Barcode Report",
        "",
        "Observed unrecognized model identifier(s) during local transcript scan:",
        *rows,
        "",
        "### Suggested Catalog Addition",
        "- Canonical model family / label:",
        "- Provider pool (`Google 20x` / `Partner 1x`):",
        "- Reasoning tier (`Low` / `Medium` / `High` / `XHigh` / `Tiered`):",
    ])
    return f"{GITHUB_REPO_ISSUES_URL}?title={urllib.parse.quote(title)}&body={urllib.parse.quote(body)}"


def finalize_unmapped_models(
    raw_map: dict[str, dict[str, Any]],
    drift_status: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Produce sorted unmapped_models list enriched with optional LS drift findings and GitHub Issue URLs."""
    merged: dict[str, dict[str, Any]] = {k: dict(v) for k, v in (raw_map or {}).items()}
    for f in (drift_status or {}).get("findings") or []:
        if isinstance(f, dict) and str(f.get("type") or "") == "UNKNOWN_MODEL_ID":
            code = str(f.get("model") or "").strip()
            if code and code not in merged:
                merged[code] = {
                    "id": code, "steps": 0, "tokens": 0,
                    "last_seen": str((drift_status or {}).get("checked_at") or ""),
                    "source": "antigravity_ls",
                }
    items = sorted(merged.values(), key=lambda r: (-int(r.get("steps") or 0), -int(r.get("tokens") or 0), str(r.get("id") or "")))
    for item in items:
        item["issue_url"] = build_unmapped_issue_url([item])
    return items


def build_subagent_adjudication(
    role_key: str,
    votes: dict[str, int],
    dom_mk: str,
    is_inherited: bool,
    role_spec: dict[str, Any] | None,
    short_labels: dict[str, str],
) -> dict[str, Any]:
    """Compare a subagent's intended targetModel against actual executed model telemetry."""
    spec = role_spec or {}
    intended_keys = [str(k) for k in (spec.get("intended_model_keys") or []) if str(k)]
    intended_mk = str(spec.get("intended_model_key") or (intended_keys[0] if intended_keys else ""))
    intended_lbl = str(spec.get("intended_model_label") or (short_labels.get(intended_mk, intended_mk) if intended_mk else ""))
    yaml_mode = str(spec.get("yaml_model") or "")
    inh_flag = bool(is_inherited or yaml_mode == "inherit")

    tot_votes = sum(max(0, int(v)) for v in (votes or {}).values())
    actual_mk = max(votes.items(), key=lambda kv: kv[1])[0] if tot_votes > 0 else dom_mk
    actual_cnt = int((votes or {}).get(actual_mk) or 0)
    actual_pct = int(round((actual_cnt / tot_votes) * 100.0)) if tot_votes > 0 else 100
    actual_lbl = short_labels.get(actual_mk, actual_mk)
    shares = [
        {"key": mk, "label": short_labels.get(mk, mk), "steps": int(cnt), "pct": int(round((int(cnt) / tot_votes) * 100.0))}
        for mk, cnt in sorted((votes or {}).items(), key=lambda kv: -kv[1]) if tot_votes > 0 and int(cnt) > 0
    ]
    diverged = bool(
        intended_keys and (
            actual_mk not in intended_keys
            or any(sh["key"] not in intended_keys and sh["pct"] >= 5 for sh in shares)
        )
    )
    inh_suffix = " (inherited)" if inh_flag else ""
    if diverged:
        status = "REDIRECTED" if inh_flag else "DIVERGED"
        text = f"Intended: {intended_lbl} · Ran: {actual_pct}% {actual_lbl}{inh_suffix}"
    elif intended_keys:
        status = "ALIGNED"
        text = f"Matched: {actual_lbl}{inh_suffix}"
    else:
        status = "OBSERVED"
        text = f"Ran: {actual_pct}% {actual_lbl}{inh_suffix}"
    return {
        "intended_model_key": intended_mk,
        "intended_model_keys": intended_keys,
        "intended_model_label": intended_lbl,
        "yaml_model_mode": yaml_mode,
        "actual_model_key": actual_mk,
        "actual_model_label": actual_lbl,
        "actual_dominant_pct": actual_pct,
        "actual_model_shares": shares,
        "is_inherited": inh_flag,
        "model_diverged": diverged,
        "adjudication_status": status,
        "adjudication_text": text,
    }


def render_pricing_history_markdown(catalog_obj: dict[str, Any], ledger_obj: dict[str, Any]) -> str:
    """Deterministically generate docs/PRICING_HISTORY.md from model_catalog.json and cost_ledger.json."""
    rev = int(catalog_obj.get("catalog_revision") or 1)
    updated = str(catalog_obj.get("updated_at") or ledger_obj.get("updated_at") or "")
    lines = [
        "# AGY-Nexus Price Book & Model Rate History",
        "",
        f"> Generated deterministically from `src/agy_nexus/data/model_catalog.json` and `src/agy_nexus/data/cost_ledger.json` (**Catalog Revision `{rev}`** · Updated `{updated}`).  ",
        "> Do not edit by hand; regenerate via `python3 scripts/catalog_sync.py --render-docs`.",
        "",
        "## Subscription Tiers (Official US)",
        "",
        "| Tier | Monthly USD | Included Dev Credits | Pool Multiplier | Notes |",
        "| :--- | ---: | ---: | :---: | :--- |",
    ]
    from agy_nexus.catalog_sync import is_safe_https_url

    def esc_cell(val: Any) -> str:
        return str(val or "").replace("\r", " ").replace("\n", " ").replace("|", "\\|").strip()

    for t in catalog_obj.get("subscription_tiers") or []:
        mo = int(t.get("monthly_usd_micros") or 0) / 1_000_000.0
        cr = int(t.get("included_credits_usd_micros") or 0) / 1_000_000.0
        lines.append(
            f"| {esc_cell(t.get('label', ''))} | ${mo:.2f} | ${cr:.2f} | {esc_cell(t.get('pool_multiplier', ''))} | {esc_cell(t.get('notes', ''))} |"
        )
    lines.extend([
        "",
        "## Model API Rate Epochs & IDE Context Limits",
        "",
        "| Model | Effective Window | Input / 1M | Cache / 1M | Output / 1M | IDE Ctx / Out (Locked) | API Ctx / Out | Verified | Source | Notes |",
        "| :--- | :--- | ---: | ---: | ---: | :---: | :---: | :---: | :--- | :--- |",
    ])
    led_models = ledger_obj.get("models") or {}
    for m in catalog_obj.get("models") or []:
        mk, lbl = esc_cell(m.get("key")), esc_cell(m.get("label"))
        pub, ide = m.get("public_api") or {}, m.get("antigravity_ide") or {}
        ide_ctx = f"{int(ide.get('context_window') or 0) // 1000}k/{int(ide.get('max_output_tokens') or 0) // 1000}k"
        api_ctx = f"{int(pub.get('api_context_window') or 0) // 1000}k/{int(pub.get('api_max_output_tokens') or 0) // 1000}k"
        for ep in (led_models.get(str(m.get("key") or "")) or {}).get("rate_epochs") or m.get("rate_epochs") or []:
            ef, et = esc_cell(ep.get("effective_from")), esc_cell(ep.get("effective_to") or "present")
            in_u, ca_u, out_u = int(ep.get("input_micros") or 0) / 1e6, int(ep.get("cache_read_micros") or 0) / 1e6, int(ep.get("output_micros") or 0) / 1e6
            ver = esc_cell(ep.get("verified_at") or pub.get("verified_at") or updated)
            src = str(ep.get("source_url") or pub.get("source_url") or "").strip()
            src_md = f"[pricing]({src})" if is_safe_https_url(src) else (esc_cell(src) or "—")
            lines.append(
                f"| {lbl} (`{mk}`) | `{ef}` .. `{et}` | ${in_u:.2f} | ${ca_u:.3f} | ${out_u:.2f} | `{ide_ctx}` | `{api_ctx}` | `{ver}` | {src_md} | {esc_cell(ep.get('note', ''))} |"
            )
    lines.append("")
    return "\n".join(lines)
