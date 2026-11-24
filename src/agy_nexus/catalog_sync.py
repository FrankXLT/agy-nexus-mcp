#!/usr/bin/env python3
"""agy_nexus.catalog_sync — Two-File Price Book, User Override & Sync Status Pipeline."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import time
from typing import Any, Callable
import urllib.error
import urllib.parse
import urllib.request

DATA_DIR = Path(__file__).resolve().parent / "data"
REPO_CATALOG_PATH = DATA_DIR / "model_catalog.json"
REPO_LEDGER_PATH = DATA_DIR / "cost_ledger.json"
RAW_UPSTREAM_BASE = "https://raw.githubusercontent.com/FrankXLT/agy-nexus-mcp/main/src/agy_nexus/data"
_PINNED_UPSTREAM_HOSTS = frozenset({"raw.githubusercontent.com", "gist.githubusercontent.com"})
SYNC_CACHE_TTL_SECONDS = 86400
MAX_CATALOG_BYTES = 524288
_CATALOG_FS_LOCK = threading.RLock()
_UNSAFE_URL_RE = re.compile(r"[\s\x00-\x1f\x7f()<>\[\]|`\"']")


def is_safe_https_url(raw_url: str) -> bool:
    """Validate strictly HTTPS URL without whitespace, control chars, or Markdown injection tokens."""
    u = str(raw_url or "").strip()
    if not u or _UNSAFE_URL_RE.search(u):
        return False
    try:
        parts = urllib.parse.urlsplit(u)
    except Exception:
        return False
    return parts.scheme.lower() == "https" and bool(parts.netloc) and not any(c.isspace() for c in parts.netloc)


def _resolve_data_dir(data_dir: Path | None = None) -> Path:
    if data_dir is not None:
        return Path(data_dir).expanduser()
    return Path(os.getenv("AGY_DATA_DIR", str(Path.home() / ".gemini/antigravity"))).expanduser()


def _resolve_bg_dir(bg_dir: Path | None = None, data_dir: Path | None = None) -> Path:
    if bg_dir is not None:
        return Path(bg_dir).expanduser()
    env_bg = os.getenv("AGY_BG_DIR", "").strip()
    if env_bg:
        return Path(env_bg).expanduser()
    return _resolve_data_dir(data_dir) / "sidecar_data" / "ag-bridge-bg"


def _atomic_write_json_600(target: Path, payload: dict[str, Any]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, indent=2) + "\n"
    with _CATALOG_FS_LOCK:
        fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
        tmp_p = Path(tmp_name)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(raw)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_p, target)
            os.chmod(target, 0o600)
        finally:
            if tmp_p.exists():
                tmp_p.unlink(missing_ok=True)


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_bundled_catalog_pair() -> tuple[dict[str, Any], dict[str, Any]]:
    """Load the repo-tracked (model_catalog.json, cost_ledger.json) ground-truth pair."""
    cat = json.loads(REPO_CATALOG_PATH.read_text(encoding="utf-8"))
    led = json.loads(REPO_LEDGER_PATH.read_text(encoding="utf-8")) if REPO_LEDGER_PATH.is_file() else {"models": {}}
    return cat, led


def validate_catalog_pair(catalog_obj: Any, ledger_obj: Any) -> list[str]:
    """Validate two-file Price Book schema, revision types, URLs, and micro-USD epochs."""
    errs: list[str] = []
    if not isinstance(catalog_obj, dict) or not isinstance(ledger_obj, dict):
        return ["Catalog and cost_ledger payloads must be JSON objects."]
    rev = catalog_obj.get("catalog_revision")
    if isinstance(rev, bool) or not isinstance(rev, int) or rev < 1:
        errs.append("model_catalog.catalog_revision must be an integer >= 1.")
    models = catalog_obj.get("models")
    if not isinstance(models, list) or not models:
        errs.append("model_catalog.models must be a non-empty list.")
        return errs
    led_models = ledger_obj.get("models")
    if not isinstance(led_models, dict):
        errs.append("cost_ledger.models must be a dictionary keyed by model key.")
        return errs
    for idx, m in enumerate(models):
        if not isinstance(m, dict) or not str(m.get("key") or "").strip():
            errs.append(f"model_catalog.models[{idx}] missing key.")
            continue
        mk = str(m["key"])
        pub = m.get("public_api")
        ide = m.get("antigravity_ide")
        if not isinstance(pub, dict) or not isinstance(ide, dict):
            errs.append(f"Model '{mk}' must define public_api and antigravity_ide sections.")
        else:
            s_url = str(pub.get("source_url") or "")
            if s_url and not is_safe_https_url(s_url):
                errs.append(f"Model '{mk}' public_api.source_url must be a clean https:// URL.")
        l_entry = led_models.get(mk)
        epochs = (l_entry or {}).get("rate_epochs") if isinstance(l_entry, dict) else m.get("rate_epochs")
        if not isinstance(epochs, list) or not epochs:
            errs.append(f"Model '{mk}' missing non-empty rate_epochs in cost_ledger.json.")
            continue
        for e_i, ep in enumerate(epochs):
            if not isinstance(ep, dict):
                errs.append(f"{mk}.rate_epochs[{e_i}] must be an object.")
                continue
            for k in ("input_micros", "output_micros", "cache_read_micros"):
                val = ep.get(k)
                if isinstance(val, bool) or not isinstance(val, int) or val < 0:
                    errs.append(f"{mk}.rate_epochs[{e_i}].{k} must be non-negative int.")
            ep_url = str(ep.get("source_url") or "")
            if ep_url and not is_safe_https_url(ep_url):
                errs.append(f"{mk}.rate_epochs[{e_i}].source_url must be a clean https:// URL.")
    return errs


def assert_antigravity_ide_untouched(base_cat: dict[str, Any], cand_cat: dict[str, Any]) -> list[str]:
    """Ensure automated catalog sync never alters locked antigravity_ide fields on existing models."""
    base_by_key = {str(m.get("key")): m for m in (base_cat.get("models") or []) if isinstance(m, dict)}
    diffs: list[str] = []
    for m in cand_cat.get("models") or []:
        if not isinstance(m, dict):
            continue
        mk = str(m.get("key") or "")
        if mk in base_by_key and m.get("antigravity_ide") != base_by_key[mk].get("antigravity_ide"):
            diffs.append(mk)
    return diffs


def merge_catalog_and_ledger(
    catalog_obj: dict[str, Any],
    ledger_obj: dict[str, Any],
    *,
    override_active: bool = False,
    bundled_revision: int | None = None,
) -> dict[str, Any]:
    """Flatten public_api, locked antigravity_ide, and rate_epochs onto runtime model specs."""
    out = deepcopy(catalog_obj)
    led_models = (ledger_obj.get("models") or {}) if isinstance(ledger_obj, dict) else {}
    merged_models: list[dict[str, Any]] = []
    for raw_m in out.get("models") or []:
        if not isinstance(raw_m, dict):
            continue
        m = deepcopy(raw_m)
        mk = str(m.get("key") or "")
        pub = m.get("public_api") or {}
        ide = m.get("antigravity_ide") or {}
        for k, v in pub.items():
            if k not in m:
                m[k] = deepcopy(v)
        for k, v in ide.items():
            if k not in m:
                m[k] = deepcopy(v)
        l_mod = led_models.get(mk) or {}
        if l_mod.get("rate_epochs"):
            m["rate_epochs"] = deepcopy(l_mod["rate_epochs"])
        m["public_api"] = deepcopy(pub)
        m["antigravity_ide"] = deepcopy(ide)
        merged_models.append(m)
    out["models"] = merged_models
    out["effective_catalog_revision"] = int(out.get("catalog_revision") or 1)
    out["bundled_catalog_revision"] = int(bundled_revision or out.get("catalog_revision") or 1)
    out["override_active"] = bool(override_active)
    out["ledger_revision"] = int(ledger_obj.get("catalog_revision") or out["effective_catalog_revision"])
    out["ledger_updated_at"] = str(ledger_obj.get("updated_at") or out.get("updated_at") or "")
    return out


def load_active_override_pair(
    data_dir: Path | None = None,
    bundled_revision: int | None = None,
) -> tuple[dict[str, Any] | None, bool]:
    """Load valid AGY_DATA_DIR/catalog_override.json if strictly newer than bundled; auto-retire stale overrides."""
    d_dir = _resolve_data_dir(data_dir)
    ov_path = d_dir / "catalog_override.json"
    if bundled_revision is None:
        b_cat, _b_led = load_bundled_catalog_pair()
        bundled_revision = int(b_cat.get("catalog_revision") or 1)
    with _CATALOG_FS_LOCK:
        try:
            raw = ov_path.read_bytes()
            if len(raw) > MAX_CATALOG_BYTES:
                return None, False
            doc = json.loads(raw.decode("utf-8"))
            if not isinstance(doc, dict):
                return None, False
            ov_rev = int(doc.get("catalog_revision") or 0)
            if ov_rev <= int(bundled_revision):
                ov_path.unlink(missing_ok=True)
                return None, True
            if validate_catalog_pair(doc.get("model_catalog"), doc.get("cost_ledger")):
                return None, False
            return doc, False
        except Exception:
            return None, False


def get_effective_catalog_pair(data_dir: Path | None = None) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Return (catalog_obj, ledger_obj, meta) combining repo truth and newer user catalog_override.json."""
    b_cat, b_led = load_bundled_catalog_pair()
    b_rev = int(b_cat.get("catalog_revision") or 1)
    ov_doc, retired_stale = load_active_override_pair(data_dir, b_rev)
    if ov_doc and isinstance(ov_doc.get("model_catalog"), dict) and isinstance(ov_doc.get("cost_ledger"), dict):
        return (
            ov_doc["model_catalog"],
            ov_doc["cost_ledger"],
            {
                "override_active": True,
                "retired_stale_override": retired_stale,
                "bundled_revision": b_rev,
                "effective_revision": int(ov_doc["model_catalog"].get("catalog_revision") or b_rev),
                "accepted_at": str(ov_doc.get("accepted_at") or ""),
            },
        )
    return (
        b_cat,
        b_led,
        {
            "override_active": False,
            "retired_stale_override": retired_stale,
            "bundled_revision": b_rev,
            "effective_revision": b_rev,
            "accepted_at": "",
        },
    )


def compute_catalog_diff(
    cur_pair: tuple[dict[str, Any], dict[str, Any]],
    cand_pair: tuple[dict[str, Any], dict[str, Any]],
) -> dict[str, Any]:
    """Compute concise human-inspectable diff between current and candidate Price Book revisions."""
    c_cat, c_led = cur_pair
    n_cat, n_led = cand_pair
    c_mods = {str(m.get("key")): m for m in (c_cat.get("models") or []) if isinstance(m, dict)}
    n_mods = {str(m.get("key")): m for m in (n_cat.get("models") or []) if isinstance(m, dict)}
    c_led_m = c_led.get("models") or {}
    n_led_m = n_led.get("models") or {}
    rate_changes: list[dict[str, Any]] = []
    api_changes: list[dict[str, Any]] = []
    new_models: list[str] = []
    summary_lines: list[str] = []
    for mk, nm in n_mods.items():
        lbl = str(nm.get("label") or mk)
        if mk not in c_mods:
            new_models.append(mk)
            summary_lines.append(f"+ Model {lbl} ({mk})")
            continue
        cm = c_mods[mk]
        for f in ("api_context_window", "api_max_output_tokens", "source_url"):
            ov = (cm.get("public_api") or {}).get(f)
            nv = (nm.get("public_api") or {}).get(f)
            if ov != nv:
                api_changes.append({"model_key": mk, "label": lbl, "field": f, "old": ov, "new": nv})
                summary_lines.append(f"~ {lbl} {f}: {ov} -> {nv}")
        old_eps = ((c_led_m.get(mk) or {}).get("rate_epochs") or cm.get("rate_epochs") or [])
        new_eps = ((n_led_m.get(mk) or {}).get("rate_epochs") or nm.get("rate_epochs") or [])
        if old_eps != new_eps:
            o_cur = old_eps[-1] if old_eps else {}
            n_cur = new_eps[-1] if new_eps else {}
            rate_changes.append({
                "model_key": mk, "label": lbl,
                "effective_from": str(n_cur.get("effective_from") or ""),
                "old_in": o_cur.get("input_micros"), "new_in": n_cur.get("input_micros"),
                "old_out": o_cur.get("output_micros"), "new_out": n_cur.get("output_micros"),
                "source_url": str(n_cur.get("source_url") or ""),
                "verified_at": str(n_cur.get("verified_at") or ""),
            })
            o_s = f"${int(o_cur.get('input_micros') or 0)/1e6:.2f}/${int(o_cur.get('output_micros') or 0)/1e6:.2f}"
            n_s = f"${int(n_cur.get('input_micros') or 0)/1e6:.2f}/${int(n_cur.get('output_micros') or 0)/1e6:.2f}"
            summary_lines.append(f"$ {lbl}: {o_s} -> {n_s} per 1M")
    return {
        "revision_from": int(c_cat.get("catalog_revision") or 1),
        "revision_to": int(n_cat.get("catalog_revision") or 1),
        "updated_at": str(n_cat.get("updated_at") or ""),
        "rate_changes": rate_changes,
        "api_changes": api_changes,
        "new_models": new_models,
        "ide_lock_violations": assert_antigravity_ide_untouched(c_cat, n_cat),
        "summary_lines": summary_lines[:18],
    }


def detect_local_catalog_edits(repo_root: Path | None = None) -> dict[str, Any]:
    """Compare local data/*.json SHA-256 against git HEAD when running from a checkout (fail-open offline)."""
    root = repo_root or Path(__file__).resolve().parent.parent.parent
    rel_paths = ("src/agy_nexus/data/model_catalog.json", "src/agy_nexus/data/cost_ledger.json")
    modified: list[str] = []
    if not (root / ".git").exists():
        return {"git_checkout": False, "dirty": False, "modified_files": []}
    for rel in rel_paths:
        cur_p = root / rel
        if not cur_p.is_file():
            continue
        try:
            proc = subprocess.run(
                ["git", "-c", "safe.directory=*", "show", f"HEAD:{rel}"],
                cwd=str(root), capture_output=True, timeout=2.0, check=False,
            )
            if proc.returncode == 0 and _sha256_bytes(cur_p.read_bytes()) != _sha256_bytes(proc.stdout):
                modified.append(rel)
        except Exception:
            continue
    return {"git_checkout": True, "dirty": bool(modified), "modified_files": modified}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        raise urllib.error.HTTPError(req.full_url, code, f"Blocked redirect ({code})", headers, fp)


def _fetch_upstream_pair(base_url: str = RAW_UPSTREAM_BASE, timeout: float = 3.0) -> tuple[bool, dict[str, Any] | None, dict[str, Any] | None, str]:
    parsed_b = urllib.parse.urlsplit(str(base_url or "").strip())
    if parsed_b.scheme.lower() != "https" or parsed_b.netloc.lower() not in _PINNED_UPSTREAM_HOSTS:
        return False, None, None, "Blocked unpinned catalog upstream URL"
    headers = {"User-Agent": "agy-nexus-catalog-sync/1.0", "Accept": "application/json"}
    opener = urllib.request.build_opener(_NoRedirect)
    out: list[dict[str, Any]] = []
    for fname in ("model_catalog.json", "cost_ledger.json"):
        req = urllib.request.Request(f"{base_url.rstrip('/')}/{fname}", headers=headers)
        try:
            with opener.open(req, timeout=timeout) as resp:
                raw = resp.read(MAX_CATALOG_BYTES + 1)
                if len(raw) > MAX_CATALOG_BYTES:
                    return False, None, None, f"{fname} exceeded max byte limit"
                out.append(json.loads(raw.decode("utf-8")))
        except Exception as exc:
            return False, None, None, f"Upstream fetch unavailable ({fname}): {str(exc)[:100]}"
    errs = validate_catalog_pair(out[0], out[1])
    if errs:
        return False, None, None, f"Invalid upstream Price Book schema: {errs[0]}"
    return True, out[0], out[1], ""


def get_catalog_sync_status(
    data_dir: Path | None = None,
    bg_dir: Path | None = None,
    *,
    allow_network: bool = True,
    refresh: bool = False,
    upstream_fetcher: Callable[[], tuple[bool, dict[str, Any] | None, dict[str, Any] | None, str]] | None = None,
) -> dict[str, Any]:
    """Return read-only Price Book sync state, cached 24h upstream comparison, and diff preview."""
    d_dir = _resolve_data_dir(data_dir)
    b_dir = _resolve_bg_dir(bg_dir, d_dir)
    eff_cat, eff_led, meta = get_effective_catalog_pair(d_dir)
    cache_path = b_dir / "catalog_sync_cache.json"
    cached: dict[str, Any] = {}
    if cache_path.is_file():
        try:
            loaded = json.loads(cache_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                cached = loaded
        except Exception:
            cached = {}
    now_epoch = time.time()
    is_fresh = bool(cached.get("fetched_epoch") and (now_epoch - float(cached.get("fetched_epoch") or 0.0)) < SYNC_CACHE_TTL_SECONDS)
    up_cat, up_led = cached.get("upstream_catalog"), cached.get("upstream_ledger")
    fetch_err = str(cached.get("error") or "")
    checked_at = str(cached.get("checked_at") or "")
    status = str(cached.get("status") or "UNKNOWN")

    if (refresh or not is_fresh) and allow_network:
        fetcher = upstream_fetcher or _fetch_upstream_pair
        ok, f_cat, f_led, err = fetcher()
        checked_at = datetime.now(timezone.utc).isoformat()
        if ok and f_cat and f_led:
            up_cat, up_led, fetch_err, status = f_cat, f_led, "", "OK"
        else:
            fetch_err = err or "Upstream check unreachable"
            status = "OFFLINE"
        _atomic_write_json_600(cache_path, {
            "status": status, "checked_at": checked_at, "fetched_epoch": now_epoch,
            "error": fetch_err, "upstream_catalog": up_cat, "upstream_ledger": up_led,
        })
    elif not is_fresh and not cached:
        status = "NOT_CHECKED"

    eff_rev = int(meta["effective_revision"])
    up_rev = int(up_cat.get("catalog_revision") or eff_rev) if isinstance(up_cat, dict) else eff_rev
    upd_avail = bool(isinstance(up_cat, dict) and isinstance(up_led, dict) and not validate_catalog_pair(up_cat, up_led) and up_rev > eff_rev)
    diff = compute_catalog_diff((eff_cat, eff_led), (up_cat, up_led)) if upd_avail and up_cat and up_led else None
    local_edits = detect_local_catalog_edits()
    return {
        "status": status, "checked_at": checked_at, "error": fetch_err if not upd_avail else "",
        "bundled_revision": int(meta["bundled_revision"]), "effective_revision": eff_rev, "upstream_revision": up_rev,
        "updated_at": str(eff_cat.get("updated_at") or ""), "override_active": bool(meta["override_active"]),
        "override_accepted_at": str(meta["accepted_at"]), "retired_stale_override": bool(meta["retired_stale_override"]),
        "update_available": upd_avail, "diff": diff,
        "local_repo_dirty": bool(local_edits.get("dirty")), "local_modified_files": local_edits.get("modified_files") or [],
    }


def accept_catalog_override(
    data_dir: Path | None = None,
    bg_dir: Path | None = None,
    *,
    candidate_catalog: dict[str, Any] | None = None,
    candidate_ledger: dict[str, Any] | None = None,
    allow_fetch: bool = False,
    on_change: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Validate and atomically persist upstream Price Book into AGY_DATA_DIR/catalog_override.json (0600)."""
    d_dir = _resolve_data_dir(data_dir)
    b_dir = _resolve_bg_dir(bg_dir, d_dir)
    b_cat, _b_led = load_bundled_catalog_pair()
    b_rev = int(b_cat.get("catalog_revision") or 1)
    with _CATALOG_FS_LOCK:
        if candidate_catalog is None or candidate_ledger is None:
            st = get_catalog_sync_status(d_dir, b_dir, allow_network=allow_fetch, refresh=allow_fetch)
            cache_p = b_dir / "catalog_sync_cache.json"
            cached = json.loads(cache_p.read_text(encoding="utf-8")) if cache_p.is_file() else {}
            candidate_catalog, candidate_ledger = cached.get("upstream_catalog"), cached.get("upstream_ledger")
            if candidate_catalog is None or candidate_ledger is None:
                return {"ok": False, "error": st.get("error") or "No validated upstream catalog snapshot cached."}
        errs = validate_catalog_pair(candidate_catalog, candidate_ledger)
        if errs:
            return {"ok": False, "error": "; ".join(errs[:3])}
        cand_rev = int(candidate_catalog.get("catalog_revision") or 0)
        if cand_rev <= b_rev:
            return {"ok": False, "error": f"Candidate revision {cand_rev} is not newer than bundled revision {b_rev}."}
        ov_doc = {
            "catalog_revision": cand_rev, "updated_at": str(candidate_catalog.get("updated_at") or ""),
            "accepted_at": datetime.now(timezone.utc).isoformat(), "source": "upstream_main",
            "model_catalog": candidate_catalog, "cost_ledger": candidate_ledger,
        }
        ov_path = d_dir / "catalog_override.json"
        _atomic_write_json_600(ov_path, ov_doc)
        if on_change is not None:
            on_change()
        return {"ok": True, "catalog_revision": cand_rev, "override_path": str(ov_path)}


def reset_catalog_override(data_dir: Path | None = None, *, on_change: Callable[[], None] | None = None) -> dict[str, Any]:
    """Remove user catalog_override.json and revert to repo-bundled Price Book."""
    d_dir = _resolve_data_dir(data_dir)
    ov_path = d_dir / "catalog_override.json"
    with _CATALOG_FS_LOCK:
        removed = ov_path.exists()
        ov_path.unlink(missing_ok=True)
        if on_change is not None:
            on_change()
        return {"ok": True, "removed": removed}


from agy_nexus.catalog_report import (  # noqa: E402,F401
    build_unmapped_issue_url,
    render_pricing_history_markdown,
)

