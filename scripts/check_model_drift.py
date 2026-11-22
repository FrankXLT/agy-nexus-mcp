#!/usr/bin/env python3
"""
Read-only 01:45 AM model ID & token pricing drift detector for AGY-Nexus.
Never auto-edits model_catalog.json or agents/*.md; writes AGY_BG_DIR/model_drift_status.json.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any
import urllib.error
import urllib.request

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agy_nexus.model_pricing import (  # noqa: E402
    classify_model_key,
    get_placeholder_map,
    load_model_catalog,
    resolve_rate_epoch,
)


def _default_bg_dir() -> Path:
    env_bg = os.getenv("AGY_BG_DIR", "").strip()
    if env_bg:
        return Path(env_bg).expanduser()
    env_data = os.getenv("AGY_DATA_DIR", "").strip()
    base = Path(env_data).expanduser() if env_data else (Path.home() / ".gemini" / "antigravity")
    return base / "sidecar_data" / "ag-bridge-bg"


AGY_BG_DIR = _default_bg_dir()


def _atomic_write_json_600(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fd = -1
            json.dump(payload, fh, indent=2)
            fh.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _http_get_json(url: str, timeout: float = 4.0, headers: dict[str, str] | None = None) -> tuple[bool, Any, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "agy-nexus-drift-check/1.0", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True, json.loads(resp.read().decode("utf-8", errors="replace")), ""
    except Exception as exc:
        return False, None, str(exc)[:140]


def _check_local_language_server(cat: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    ph_map = get_placeholder_map()
    findings: list[dict[str, str]] = []
    try:
        ps_out = subprocess.run(
            ["ps", "-u", str(os.getuid()), "-o", "args"], capture_output=True, text=True, timeout=2.0, check=False
        ).stdout
        csrf = ""
        for line in ps_out.splitlines():
            if "language_server" in line and "--csrf_token" in line:
                m = re.search(r"--csrf_token[=\s]+([^\s]+)", line)
                if m:
                    csrf = m.group(1).strip()
                    break
        if not csrf:
            return {"status": "SKIPPED_NO_LS", "checked_models": 0}, findings
        ss_out = subprocess.run(["ss", "-tlnp"], capture_output=True, text=True, timeout=2.0, check=False).stdout
        ports = [int(m.group(1)) for ln in ss_out.splitlines() if "language_server" in ln for m in re.finditer(r"127\.0\.0\.1:(\d+)", ln)]
        cfgs: list[dict[str, Any]] = []
        no_proxy_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for port in ports[:4]:
            try:
                req = urllib.request.Request(
                    f"http://127.0.0.1:{port}/exa.language_server_pb.LanguageServerService/GetUserStatus",
                    data=b"{}",
                    headers={"Content-Type": "application/json", "Connect-Protocol-Version": "1", "X-Codeium-Csrf-Token": csrf},
                    method="POST",
                )
                with no_proxy_opener.open(req, timeout=2.0) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="replace"))
                cfgs = ((data.get("userStatus") or {}).get("cascadeModelConfigData") or {}).get("clientModelConfigs") or []
                if cfgs:
                    break
            except Exception:
                continue
        if not cfgs:
            return {"status": "UNREACHABLE", "checked_models": 0}, findings
        seen_ids: set[str] = set()
        for c in cfgs:
            mid = str((c.get("modelOrAlias") or {}).get("model") or "").strip()
            lbl = str(c.get("label") or "").strip()
            if not mid:
                continue
            seen_ids.add(mid)
            if mid.upper() not in ph_map:
                known_mids = {str(x) for m in (cat.get("models") or []) for x in (m.get("model_ids") or [])}
                if mid not in known_mids:
                    findings.append({"source": "antigravity_ls", "type": "UNKNOWN_MODEL_ID", "model": mid, "detail": f"Unmapped live LS model '{lbl}' ({mid})"})
        return {"status": "OK", "checked_models": len(seen_ids)}, findings
    except Exception as exc:
        return {"status": "ERROR", "detail": str(exc)[:120]}, findings


def _check_gemini_api(cat: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        return {"status": "SKIPPED_NO_API_KEY"}, []
    ok, data, err = _http_get_json(
        "https://generativelanguage.googleapis.com/v1beta/models",
        timeout=4.0,
        headers={"x-goog-api-key": key},
    )
    if not ok or not isinstance(data, dict):
        return {"status": "UNREACHABLE", "detail": err}, []
    known = {str(x).lower() for m in (cat.get("models") or []) for x in [*(m.get("model_ids") or []), *(m.get("aliases") or [])]}
    findings: list[dict[str, str]] = []
    matched = 0
    for row in data.get("models") or []:
        name = str(row.get("name") or "").replace("models/", "").strip()
        if name.startswith("gemini-4") or name.startswith("gemini-3.8"):
            matched += 1
            if name.lower() not in known:
                findings.append({"source": "gemini_api", "type": "NEW_API_MODEL", "model": name, "detail": f"Upstream Gemini model '{name}' absent from catalog"})
    return {"status": "OK", "matched_models": matched}, findings


def _check_public_rate_feeds(cat: dict[str, Any], today_iso: str) -> tuple[dict[str, Any], list[dict[str, str]]]:
    sources: dict[str, Any] = {}
    findings: list[dict[str, str]] = []
    ok_md, md_data, md_err = _http_get_json("https://models.dev/api.json", timeout=4.0)
    if not ok_md or not isinstance(md_data, dict):
        sources["models_dev"] = {"status": "UNREACHABLE", "detail": md_err}
    else:
        checked = 0
        for prov_key in ("google", "anthropic", "openai"):
            prov_models = ((md_data.get(prov_key) or {}).get("models") or {})
            for mid, info in prov_models.items():
                if not isinstance(info, dict):
                    continue
                low = str(mid).lower()
                if not any(tok in low for tok in ("gemini-4", "gemini-3.8", "sonnet-5", "opus-5", "gpt-oss-120b")):
                    continue
                checked += 1
                mk = classify_model_key(mid)
                ep = resolve_rate_epoch(mk, today_iso)
                cost = info.get("cost") or {}
                if isinstance(cost, dict) and cost.get("input") is not None and cost.get("output") is not None:
                    try:
                        pub_in = round(float(cost["input"]) * 1_000_000)
                        pub_out = round(float(cost["output"]) * 1_000_000)
                    except (TypeError, ValueError):
                        continue
                    if abs(pub_in - int(ep["input_micros"])) > 10_000 or abs(pub_out - int(ep["output_micros"])) > 50_000:
                        findings.append({
                            "source": "models.dev",
                            "type": "RATE_DRIFT",
                            "model": f"{mk} ({mid})",
                            "detail": f"Catalog ${ep['input_micros']/1e6:.2f}/${ep['output_micros']/1e6:.2f} vs models.dev ${pub_in/1e6:.2f}/${pub_out/1e6:.2f}",
                        })
        sources["models_dev"] = {"status": "OK", "matched_models": checked}

    ok_ll, ll_data, ll_err = _http_get_json(
        "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json",
        timeout=4.0,
    )
    if not ok_ll or not isinstance(ll_data, dict):
        sources["litellm"] = {"status": "UNREACHABLE", "detail": ll_err}
    else:
        ll_cnt = sum(1 for k in ll_data if any(t in str(k).lower() for t in ("gemini-4", "gemini-3.8", "sonnet-5", "opus-5", "gpt-oss-120b")))
        sources["litellm"] = {"status": "OK", "matched_models": ll_cnt}
    return sources, findings


def run_drift_check(bg_dir: Path | None = None, *, strict: bool = False) -> dict[str, Any]:
    """Run read-only drift checks and persist model_drift_status.json to bg_dir."""
    cat = load_model_catalog()
    now_dt = datetime.now(timezone.utc)
    today_iso = now_dt.strftime("%Y-%m-%d")
    target_bg = bg_dir or AGY_BG_DIR

    ls_src, ls_find = _check_local_language_server(cat)
    gem_src, gem_find = _check_gemini_api(cat)
    feed_srcs, feed_find = _check_public_rate_feeds(cat, today_iso)
    findings = [*ls_find, *gem_find, *feed_find]
    sources = {"antigravity_ls": ls_src, "gemini_api": gem_src, **feed_srcs}
    ok_sources = sum(1 for s in sources.values() if isinstance(s, dict) and s.get("status") == "OK")
    if findings:
        status = "DRIFT_DETECTED"
        summary = f"{len(findings)} drift finding(s): {findings[0]['detail']}"
    elif ok_sources == 0:
        status = "UNREACHABLE"
        summary = f"All {len(sources)} drift check sources unreachable or skipped ({today_iso})"
    else:
        status = "OK"
        summary = f"0 drift findings across {ls_src.get('checked_models', 0)} live LS models ({today_iso})"
    report: dict[str, Any] = {
        "status": status,
        "checked_at": now_dt.isoformat(),
        "drift_count": len(findings),
        "summary": summary,
        "read_only": True,
        "sources": sources,
        "findings": findings[:25],
    }
    _atomic_write_json_600(target_bg / "model_drift_status.json", report)
    if strict and findings:
        report["strict_exit_code"] = 2
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only AGY-Nexus 01:45 AM model ID & pricing drift detector.")
    parser.add_argument("--check-only", action="store_true", help="Strictly read-only check writing only model_drift_status.json.")
    parser.add_argument("--strict", action="store_true", help="Exit 2 when drift is detected.")
    parser.add_argument("--bg-dir", default="", help="Override AGY_BG_DIR output directory.")
    parser.add_argument("--json", action="store_true", help="Print full JSON report.")
    args = parser.parse_args()

    bg = Path(args.bg_dir).expanduser() if args.bg_dir else AGY_BG_DIR
    report = run_drift_check(bg_dir=bg, strict=args.strict)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"[drift-check] {report['status']} | {report['summary']}")
    sys.exit(int(report.get("strict_exit_code") or 0))


if __name__ == "__main__":
    main()
