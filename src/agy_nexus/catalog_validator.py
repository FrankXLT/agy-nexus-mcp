#!/usr/bin/env python3
"""agy_nexus.catalog_validator — Defense-in-Depth Price Book Schema & Anti-Injection Gate."""
from __future__ import annotations

from datetime import date
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import stat
from typing import Any, NoReturn
import urllib.parse

MAX_CATALOG_BYTES = 262_144
MAX_RATE_MICROS = 500_000_000
MAX_REVISION = 1_000_000
MAX_URL_LENGTH = 512

SCHEMAS_DIR = Path(__file__).resolve().parent / "data" / "schemas"

ALLOWED_SOURCE_HOSTS: frozenset[str] = frozenset({
    "ai.google.dev", "cloud.google.com", "one.google.com", "blog.google",
    "deepmind.google", "docs.anthropic.com", "www.anthropic.com", "claude.com",
    "openai.com", "platform.openai.com", "github.com", "models.dev",
})

ALLOWED_CATALOG_BOT_PATHS: frozenset[str] = frozenset({
    "src/agy_nexus/data/model_catalog.json",
    "src/agy_nexus/data/cost_ledger.json",
    "docs/PRICING_HISTORY.md",
})

_KEY_RE = re.compile(r"\A[a-z][a-z0-9_]{1,47}\Z")
_DATE_RE = re.compile(r"\A\d{4}-\d{2}-\d{2}\Z")
_MODEL_ID_RE = re.compile(r"\A[a-z0-9][a-z0-9._/-]{1,95}\Z")
_PLACEHOLDER_RE = re.compile(r"\AMODEL_(?:PLACEHOLDER_M\d{1,6}|OPENAI_[A-Z0-9_]{3,64})\Z")
_UNSAFE_URL_RE = re.compile(r"[\s\x00-\x1f\x7f-\x9f()<>\[\]|`\"'\\;]")
_PCT_CTRL_RE = re.compile(r"%(?:0[0-9a-f]|1[0-9a-f]|3[ce]|7f)", re.IGNORECASE)
_BIDI_ZW_RE = re.compile(r"[\u061c\u180e\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff\ufff9-\ufffb]")
_DANGEROUS_TEXT_RE = re.compile(r"[\x00-\x1f\x7f-\x9f<>\[\]|`\\]")
_SCHEME_INJECT_RE = re.compile(r"(?:javascript|vbscript|data)\s*:", re.IGNORECASE)
_EVENT_HANDLER_RE = re.compile(r"\bon[a-z]{2,24}\s*=", re.IGNORECASE)

_VALID_POOL_KEYS = frozenset({"google", "claude", "gpt_oss"})
_VALID_POOL_LABELS = frozenset({"Google 20x", "Partner 1x"})
_VALID_QUOTA_GROUPS = frozenset({"Gemini Models", "Claude and GPT models"})
_VALID_TIERS = frozenset({"Low", "Medium", "High", "XHigh", "Tiered"})

_CAT_TOP_KEYS = frozenset({
    "catalog_revision", "updated_at", "catalog_version", "currency",
    "micros_per_usd", "tokens_per_rate_unit", "subscription_tiers",
    "fallback_token_split", "models",
})
_TIER_KEYS = frozenset({
    "id", "label", "monthly_usd_micros", "included_credits_usd_micros",
    "pool_multiplier", "storage", "notes",
})
_SPLIT_KEYS = frozenset({"uncached_input_ratio", "cached_input_ratio", "output_ratio"})
_MODEL_KEYS = frozenset({
    "key", "label", "short_label", "short_11", "short_7",
    "model_ids", "aliases", "public_api", "antigravity_ide",
})
_PUB_API_KEYS = frozenset({"api_context_window", "api_max_output_tokens", "source_url", "verified_at"})
_IDE_KEYS = frozenset({
    "pool_key", "pool_label", "quota_group", "context_window", "max_output_tokens",
    "reasoning_tiers", "placeholders", "tier_placeholders", "target_pct",
})
_TARGET_PCT_KEYS = frozenset({"ultra-20x", "ultra-5x"})
_LED_TOP_KEYS = frozenset({
    "schema_version", "catalog_revision", "updated_at", "currency",
    "micros_per_usd", "tokens_per_rate_unit", "models",
})
_LED_MOD_KEYS = frozenset({"label", "source_url", "verified_at", "rate_epochs"})
_EPOCH_KEYS = frozenset({
    "effective_from", "effective_to", "input_micros", "output_micros",
    "cache_read_micros", "source_url", "verified_at", "note",
})
_OVERRIDE_KEYS = frozenset({"catalog_revision", "updated_at", "accepted_at", "source", "model_catalog", "cost_ledger"})


def _reject_json_constant(token: str) -> NoReturn:
    raise ValueError(f"Non-finite JSON constant rejected: {token}")


def _parse_finite_float(token: str) -> float:
    val = float(token)
    if not math.isfinite(val):
        raise ValueError(f"Non-finite JSON float rejected: {token}")
    return val


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise ValueError(f"Duplicate JSON object key rejected: {k}")
        out[k] = v
    return out


def read_bounded_regular_file(path: Path, *, max_bytes: int = MAX_CATALOG_BYTES) -> bytes:
    """Open regular non-symlink file safely (O_NOFOLLOW) and read up to max_bytes without unbounded buffering."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(str(path), flags)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise ValueError(f"Refusing non-regular file: {path.name}")
        if st.st_size > max_bytes:
            raise ValueError(f"{path.name} size {st.st_size} exceeds {max_bytes} byte limit.")
        with os.fdopen(fd, "rb") as fh:
            fd = -1
            raw = fh.read(max_bytes + 1)
    finally:
        if fd >= 0:
            os.close(fd)
    if len(raw) > max_bytes:
        raise ValueError(f"{path.name} exceeds {max_bytes} byte limit.")
    return raw


def parse_catalog_json_bytes(raw: bytes | bytearray | str, *, max_bytes: int = MAX_CATALOG_BYTES) -> Any:
    """Strictly decode and parse Price Book JSON within byte cap, rejecting NaN/Infinity/duplicate keys."""
    if isinstance(raw, (bytes, bytearray)):
        if len(raw) > max_bytes:
            raise ValueError(f"Catalog payload size {len(raw)} exceeds {max_bytes} byte limit.")
        text = bytes(raw).decode("utf-8", errors="strict")
    elif isinstance(raw, str):
        enc_len = len(raw.encode("utf-8", errors="strict"))
        if enc_len > max_bytes:
            raise ValueError(f"Catalog payload size {enc_len} exceeds {max_bytes} byte limit.")
        text = raw
    else:
        raise ValueError("Catalog payload must be bytes or str.")
    if "\x00" in text or text.startswith("\ufeff"):
        raise ValueError("Disallowed NUL byte or UTF-8 BOM in JSON payload.")
    return json.loads(
        text, parse_constant=_reject_json_constant, parse_float=_parse_finite_float, object_pairs_hook=_reject_duplicate_keys,
    )


def _check_int(val: Any, field: str, lo: int, hi: int) -> str | None:
    if isinstance(val, bool) or not isinstance(val, int) or val < lo or val > hi:
        return f"{field} must be integer in [{lo}, {hi}]."
    return None


def _check_finite_num(val: Any, field: str, lo: float, hi: float) -> str | None:
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        return f"{field} must be a finite number in [{lo}, {hi}]."
    num = float(val)
    return None if math.isfinite(num) and lo <= num <= hi else f"{field} must be finite within [{lo}, {hi}]."


def _check_date_str(val: Any, field: str, *, allow_none: bool = False) -> str | None:
    if val is None and allow_none:
        return None
    if not isinstance(val, str) or not _DATE_RE.match(val):
        return f"{field} must be YYYY-MM-DD."
    try:
        date.fromisoformat(val)
    except ValueError:
        return f"{field} is not a valid calendar date."
    return None


def check_clean_text(val: Any, field: str, *, min_len: int = 1, max_len: int = 240) -> list[str]:
    """Reject non-strings, HTML/XSS tags, control/bidi spoofing, script schemes, and Markdown breaks."""
    if not isinstance(val, str):
        return [f"{field} must be a string."]
    if not (min_len <= len(val) <= max_len):
        return [f"{field} length must be in [{min_len}, {max_len}]."]
    if _DANGEROUS_TEXT_RE.search(val) or _BIDI_ZW_RE.search(val):
        return [f"{field} contains disallowed control, HTML, Markdown, or bidi characters."]
    if _SCHEME_INJECT_RE.search(val) or _EVENT_HANDLER_RE.search(val):
        return [f"{field} contains disallowed script or event-handler syntax."]
    return []


def validate_source_url(raw_url: Any, field: str = "source_url") -> list[str]:
    """Enforce https:// URLs on ALLOWED_SOURCE_HOSTS with zero SSRF, userinfo, ports, or injection chars."""
    if not isinstance(raw_url, str) or not raw_url:
        return [f"{field} must be a non-empty https:// URL."]
    if len(raw_url) > MAX_URL_LENGTH:
        return [f"{field} exceeds {MAX_URL_LENGTH} chars."]
    if _UNSAFE_URL_RE.search(raw_url) or _BIDI_ZW_RE.search(raw_url) or _PCT_CTRL_RE.search(raw_url):
        return [f"{field} contains unsafe URL or injection characters."]
    if not raw_url.isascii() or _SCHEME_INJECT_RE.search(raw_url):
        return [f"{field} must be pure ASCII https:// URL without script schemes."]
    try:
        parts = urllib.parse.urlsplit(raw_url)
    except Exception:
        return [f"{field} failed URL parsing."]
    if parts.scheme.lower() != "https" or not parts.netloc:
        return [f"{field} must use https:// scheme."]
    if parts.username is not None or parts.password is not None or "@" in parts.netloc or parts.port is not None or ":" in parts.netloc:
        return [f"{field} must not include userinfo credentials or explicit ports."]
    host = (parts.hostname or "").lower()
    if not host or parts.netloc.lower() != host or host.endswith("."):
        return [f"{field} hostname is malformed."]
    if host == "localhost" or host.endswith((".local", ".lan", ".internal")):
        return [f"{field} blocks local/internal hostnames."]
    try:
        ipaddress.ip_address(host)
        return [f"{field} blocks raw IP literals."]
    except ValueError:
        pass
    return [] if host in ALLOWED_SOURCE_HOSTS else [f"{field} host '{host}' is not in ALLOWED_SOURCE_HOSTS."]


def is_safe_catalog_source_url(raw_url: str) -> bool:
    """Return True only when raw_url passes strict https:// allowlist and anti-SSRF/XSS validation."""
    return not validate_source_url(raw_url)


def _check_exact_keys(obj: Any, allowed: frozenset[str], ctx: str) -> list[str]:
    if not isinstance(obj, dict):
        return [f"{ctx} must be a JSON object."]
    keys = set(obj.keys())
    errs: list[str] = []
    if extra := sorted(keys - allowed):
        errs.append(f"{ctx} has unexpected properties: {', '.join(extra[:5])}")
    if missing := sorted(allowed - keys):
        errs.append(f"{ctx} missing required properties: {', '.join(missing[:5])}")
    return errs


def _collect_err(errs: list[str], msg: str | None) -> None:
    if msg:
        errs.append(msg)


def _validate_tiers_and_split(cat: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    tiers = cat.get("subscription_tiers")
    if not isinstance(tiers, list) or not (1 <= len(tiers) <= 16):
        errs.append("model_catalog.subscription_tiers must contain 1..16 entries.")
    else:
        seen_ids: set[str] = set()
        for idx, t in enumerate(tiers):
            ctx = f"subscription_tiers[{idx}]"
            if k_errs := _check_exact_keys(t, _TIER_KEYS, ctx):
                errs.extend(k_errs)
                continue
            tid = t.get("id")
            if not isinstance(tid, str) or not _KEY_RE.match(tid) or tid in seen_ids:
                errs.append(f"{ctx}.id must be unique snake_case identifier.")
            else:
                seen_ids.add(tid)
            for tf, mn, mx in (("label", 1, 80), ("pool_multiplier", 1, 32), ("storage", 1, 32), ("notes", 0, 240)):
                errs.extend(check_clean_text(t.get(tf), f"{ctx}.{tf}", min_len=mn, max_len=mx))
            for mf in ("monthly_usd_micros", "included_credits_usd_micros"):
                _collect_err(errs, _check_int(t.get(mf), f"{ctx}.{mf}", 0, MAX_RATE_MICROS))
    sp = cat.get("fallback_token_split")
    if sp_errs := _check_exact_keys(sp, _SPLIT_KEYS, "fallback_token_split"):
        return errs + sp_errs
    tot, bad = 0.0, False
    for sk in sorted(_SPLIT_KEYS):
        if msg := _check_finite_num(sp.get(sk), f"fallback_token_split.{sk}", 0.0, 1.0):
            errs.append(msg)
            bad = True
        else:
            tot += float(sp[sk])
    if not bad and abs(tot - 1.0) > 0.01:
        errs.append("fallback_token_split ratios must sum to ~1.0.")
    return errs


def _validate_model_entry(m: Any, idx: int, seen_keys: set[str]) -> list[str]:
    ctx = f"models[{idx}]"
    if errs := _check_exact_keys(m, _MODEL_KEYS, ctx):
        return errs
    mk = m.get("key")
    if not isinstance(mk, str) or not _KEY_RE.match(mk) or mk in seen_keys:
        errs.append(f"{ctx}.key must be unique snake_case identifier.")
    else:
        seen_keys.add(mk)
        ctx = f"model[{mk}]"
    for tf, ml in (("label", 64), ("short_label", 32), ("short_11", 16), ("short_7", 12)):
        errs.extend(check_clean_text(m.get(tf), f"{ctx}.{tf}", min_len=1, max_len=ml))
    mids = m.get("model_ids")
    if not isinstance(mids, list) or not (1 <= len(mids) <= 64) or not all(isinstance(x, str) and _MODEL_ID_RE.match(x) for x in mids):
        errs.append(f"{ctx}.model_ids must contain 1..64 safe ASCII slug identifiers.")
    aliases = m.get("aliases")
    if not isinstance(aliases, list) or not (1 <= len(aliases) <= 64):
        errs.append(f"{ctx}.aliases must contain 1..64 strings.")
    else:
        for ai, al in enumerate(aliases):
            errs.extend(check_clean_text(al, f"{ctx}.aliases[{ai}]", min_len=1, max_len=64))
    pub = m.get("public_api")
    if pub_errs := _check_exact_keys(pub, _PUB_API_KEYS, f"{ctx}.public_api"):
        errs.extend(pub_errs)
    else:
        for kf, lo, hi in (("api_context_window", 1024, 100_000_000), ("api_max_output_tokens", 256, 10_000_000)):
            _collect_err(errs, _check_int(pub.get(kf), f"{ctx}.public_api.{kf}", lo, hi))
        errs.extend(validate_source_url(pub.get("source_url"), f"{ctx}.public_api.source_url"))
        _collect_err(errs, _check_date_str(pub.get("verified_at"), f"{ctx}.public_api.verified_at"))
    return errs + _validate_ide_block(m.get("antigravity_ide"), ctx)


def _validate_ide_block(ide: Any, ctx: str) -> list[str]:
    if errs := _check_exact_keys(ide, _IDE_KEYS, f"{ctx}.antigravity_ide"):
        return errs
    for fk, allowed in (("pool_key", _VALID_POOL_KEYS), ("pool_label", _VALID_POOL_LABELS), ("quota_group", _VALID_QUOTA_GROUPS)):
        if ide.get(fk) not in allowed:
            errs.append(f"{ctx}.antigravity_ide.{fk} invalid.")
    for kf, lo, hi in (("context_window", 1024, 100_000_000), ("max_output_tokens", 256, 10_000_000)):
        _collect_err(errs, _check_int(ide.get(kf), f"{ctx}.antigravity_ide.{kf}", lo, hi))
    rt = ide.get("reasoning_tiers")
    if not isinstance(rt, list) or not (1 <= len(rt) <= 12) or not all(isinstance(x, str) and x in _VALID_TIERS for x in rt):
        errs.append(f"{ctx}.antigravity_ide.reasoning_tiers invalid.")
    phs = ide.get("placeholders")
    if not isinstance(phs, list) or not (1 <= len(phs) <= 64) or not all(isinstance(x, str) and _PLACEHOLDER_RE.match(x) for x in phs):
        errs.append(f"{ctx}.antigravity_ide.placeholders must contain 1..64 valid MODEL_* codes.")
    tph = ide.get("tier_placeholders")
    if not isinstance(tph, dict) or not tph:
        errs.append(f"{ctx}.antigravity_ide.tier_placeholders must be a non-empty map.")
    else:
        ph_set = set(phs) if isinstance(phs, list) else set()
        for tk, tv in tph.items():
            if tk not in _VALID_TIERS:
                errs.append(f"{ctx}.tier_placeholders unexpected tier '{tk}'.")
            if not isinstance(tv, str) or not _PLACEHOLDER_RE.match(tv) or (ph_set and tv not in ph_set):
                errs.append(f"{ctx}.tier_placeholders[{tk}] must reference a valid placeholder.")
    tp = ide.get("target_pct")
    if tp_errs := _check_exact_keys(tp, _TARGET_PCT_KEYS, f"{ctx}.antigravity_ide.target_pct"):
        errs.extend(tp_errs)
    else:
        for tk in ("ultra-20x", "ultra-5x"):
            _collect_err(errs, _check_finite_num(tp.get(tk), f"{ctx}.target_pct.{tk}", 0.0, 100.0))
    return errs


def _validate_header_constants(obj: dict[str, Any], name: str) -> list[str]:
    errs: list[str] = []
    _collect_err(errs, _check_int(obj.get("catalog_revision"), f"{name}.catalog_revision", 1, MAX_REVISION))
    _collect_err(errs, _check_date_str(obj.get("updated_at"), f"{name}.updated_at"))
    if obj.get("currency") != "USD":
        errs.append(f"{name}.currency must be 'USD'.")
    for ck in ("micros_per_usd", "tokens_per_rate_unit"):
        if isinstance(obj.get(ck), bool) or obj.get(ck) != 1_000_000:
            errs.append(f"{name}.{ck} must be integer 1000000.")
    return errs


def validate_catalog_doc(catalog_obj: Any) -> list[str]:
    """Validate model_catalog.json structure, bounds, URLs, and anti-injection string hygiene."""
    if errs := _check_exact_keys(catalog_obj, _CAT_TOP_KEYS, "model_catalog"):
        return errs
    errs.extend(_validate_header_constants(catalog_obj, "model_catalog"))
    _collect_err(errs, _check_date_str(catalog_obj.get("catalog_version"), "model_catalog.catalog_version"))
    errs.extend(_validate_tiers_and_split(catalog_obj))
    models = catalog_obj.get("models")
    if not isinstance(models, list) or not (1 <= len(models) <= 64):
        return errs + ["model_catalog.models must contain 1..64 items."]
    seen_keys: set[str] = set()
    for idx, m in enumerate(models):
        errs.extend(_validate_model_entry(m, idx, seen_keys))
    return errs


def _validate_epoch(ep: Any, ctx: str) -> list[str]:
    if errs := _check_exact_keys(ep, _EPOCH_KEYS, ctx):
        return errs
    ef_msg = _check_date_str(ep.get("effective_from"), f"{ctx}.effective_from")
    et_msg = _check_date_str(ep.get("effective_to"), f"{ctx}.effective_to", allow_none=True)
    va_msg = _check_date_str(ep.get("verified_at"), f"{ctx}.verified_at")
    for m in (ef_msg, et_msg, va_msg):
        _collect_err(errs, m)
    if not ef_msg and not et_msg and ep.get("effective_to") and str(ep["effective_to"]) < str(ep["effective_from"]):
        errs.append(f"{ctx}.effective_to precedes effective_from.")
    for rk in ("input_micros", "output_micros", "cache_read_micros"):
        _collect_err(errs, _check_int(ep.get(rk), f"{ctx}.{rk}", 0, MAX_RATE_MICROS))
    errs.extend(validate_source_url(ep.get("source_url"), f"{ctx}.source_url"))
    errs.extend(check_clean_text(ep.get("note"), f"{ctx}.note", min_len=0, max_len=240))
    return errs


def validate_ledger_doc(ledger_obj: Any) -> list[str]:
    """Validate cost_ledger.json structure, epoch bounds (0 <= rate <= 500M), dates, and URLs."""
    if errs := _check_exact_keys(ledger_obj, _LED_TOP_KEYS, "cost_ledger"):
        return errs
    if isinstance(ledger_obj.get("schema_version"), bool) or ledger_obj.get("schema_version") != 1:
        errs.append("cost_ledger.schema_version must be 1.")
    errs.extend(_validate_header_constants(ledger_obj, "cost_ledger"))
    l_mods = ledger_obj.get("models")
    if not isinstance(l_mods, dict) or not (1 <= len(l_mods) <= 64):
        return errs + ["cost_ledger.models must contain 1..64 model entries."]
    for mk, entry in l_mods.items():
        if not isinstance(mk, str) or not _KEY_RE.match(mk):
            errs.append(f"cost_ledger.models invalid key '{mk}'.")
            continue
        ctx = f"cost_ledger.models[{mk}]"
        if m_errs := _check_exact_keys(entry, _LED_MOD_KEYS, ctx):
            errs.extend(m_errs)
            continue
        errs.extend(check_clean_text(entry.get("label"), f"{ctx}.label", min_len=1, max_len=64))
        errs.extend(validate_source_url(entry.get("source_url"), f"{ctx}.source_url"))
        _collect_err(errs, _check_date_str(entry.get("verified_at"), f"{ctx}.verified_at"))
        epochs = entry.get("rate_epochs")
        if not isinstance(epochs, list) or not (1 <= len(epochs) <= 64):
            errs.append(f"{ctx}.rate_epochs must contain 1..64 epochs.")
            continue
        for ei, ep in enumerate(epochs):
            errs.extend(_validate_epoch(ep, f"{ctx}.rate_epochs[{ei}]"))
    return errs


def validate_with_jsonschema(
    catalog_obj: Any, ledger_obj: Any, *, schemas_dir: Path | None = None, require_installed: bool = False,
) -> tuple[bool, list[str]]:
    """Cross-validate both documents against JSON Schema files if `jsonschema` package is installed."""
    try:
        import jsonschema  # type: ignore[import-not-found]
    except ImportError:
        return (False, ["jsonschema package is required for schema cross-check."]) if require_installed else (False, [])
    s_dir, errs = schemas_dir or SCHEMAS_DIR, []
    for fname, doc in (("model_catalog.schema.json", catalog_obj), ("cost_ledger.schema.json", ledger_obj)):
        sp = s_dir / fname
        if not sp.is_file():
            errs.append(f"Missing JSON schema file: {sp}")
            continue
        validator = jsonschema.Draft202012Validator(json.loads(sp.read_text(encoding="utf-8")))
        for err in sorted(validator.iter_errors(doc), key=lambda e: list(e.path)):
            errs.append(f"{fname}@{'.'.join(str(p) for p in err.path) or '<root>'}: {err.message}")
    return True, errs


def validate_catalog_pair_strict(
    catalog_obj: Any, ledger_obj: Any, *, use_jsonschema: bool = False, require_jsonschema: bool = False, schemas_dir: Path | None = None,
) -> list[str]:
    """Run full pure-Python schema, cross-file parity, anti-injection, and optional jsonschema checks."""
    errs = validate_catalog_doc(catalog_obj) + validate_ledger_doc(ledger_obj)
    if isinstance(catalog_obj, dict) and isinstance(ledger_obj, dict) and isinstance(ledger_obj.get("models"), dict):
        c_keys = {str(m["key"]) for m in (catalog_obj.get("models") or []) if isinstance(m, dict) and isinstance(m.get("key"), str)}
        l_keys = set(ledger_obj["models"].keys())
        errs.extend(f"Model '{mk}' missing from cost_ledger.models." for mk in sorted(c_keys - l_keys))
        errs.extend(f"cost_ledger.models contains orphan key '{mk}'." for mk in sorted(l_keys - c_keys))
    if use_jsonschema or require_jsonschema:
        _ran, js_errs = validate_with_jsonschema(catalog_obj, ledger_obj, schemas_dir=schemas_dir, require_installed=require_jsonschema)
        errs.extend(js_errs)
    return errs


def validate_catalog_override_doc(doc: Any) -> list[str]:
    """Validate `${AGY_DATA_DIR}/catalog_override.json` wrapper before trusting or loading."""
    if errs := _check_exact_keys(doc, _OVERRIDE_KEYS, "catalog_override"):
        return errs
    _collect_err(errs, _check_int(doc.get("catalog_revision"), "catalog_override.catalog_revision", 1, MAX_REVISION))
    _collect_err(errs, _check_date_str(doc.get("updated_at"), "catalog_override.updated_at"))
    errs.extend(check_clean_text(doc.get("accepted_at"), "catalog_override.accepted_at", min_len=10, max_len=64))
    if doc.get("source") != "upstream_main":
        errs.append("catalog_override.source must equal 'upstream_main'.")
    errs.extend(validate_catalog_pair_strict(doc.get("model_catalog"), doc.get("cost_ledger")))
    if isinstance(doc.get("model_catalog"), dict) and doc["model_catalog"].get("catalog_revision") != doc.get("catalog_revision"):
        errs.append("catalog_override.catalog_revision mismatches model_catalog.catalog_revision.")
    return errs


def validate_catalog_files_strict(
    catalog_path: Path, ledger_path: Path, *, schemas_dir: Path | None = None, require_jsonschema: bool = False,
) -> tuple[bool, list[str], dict[str, Any]]:
    """Load raw catalog/ledger JSON files under byte caps and validate strictly."""
    try:
        cat_obj = parse_catalog_json_bytes(read_bounded_regular_file(catalog_path))
        led_obj = parse_catalog_json_bytes(read_bounded_regular_file(ledger_path))
    except Exception as exc:
        return False, [str(exc)], {"jsonschema_checked": False}
    errs = validate_catalog_pair_strict(cat_obj, led_obj)
    ran_js, js_errs = validate_with_jsonschema(cat_obj, led_obj, schemas_dir=schemas_dir, require_installed=require_jsonschema)
    errs.extend(js_errs)
    info = {
        "jsonschema_checked": ran_js,
        "catalog_revision": cat_obj.get("catalog_revision") if isinstance(cat_obj, dict) else None,
        "model_count": len(cat_obj.get("models") or []) if isinstance(cat_obj, dict) else 0,
    }
    return len(errs) == 0, errs, info


def verify_catalog_bot_changed_paths(changed_paths: list[str] | tuple[str, ...]) -> list[str]:
    """Return any changed path outside the 3 allowed catalog-sync PR target files."""
    disallowed: list[str] = []
    for raw in changed_paths:
        if raw == "":
            continue
        norm = str(raw).replace("\\", "/")
        while norm.startswith("./"):
            norm = norm[2:]
        if norm not in ALLOWED_CATALOG_BOT_PATHS:
            disallowed.append(norm)
    return disallowed
