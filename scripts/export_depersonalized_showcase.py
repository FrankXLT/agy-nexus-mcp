#!/usr/bin/env python3
"""
scripts/export_depersonalized_showcase.py — Export Live Telemetry to Public v4.0.3 Showcases.

Reads live workstation bundles (current_month, last_month, qtd, ytd, last_30d, last_90d, last_year),
Workspace Explorer tree, bundled demo docs, and Code Health, applies deterministic 1-to-1 SHA-256-keyed
aliasing, writes `web/demo_snapshot.js`, and regenerates the four `README.md` ASCII showcase blocks.
"""
from __future__ import annotations

import copy, hashlib, hmac, json, os, re, sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for _p in (str(SRC_DIR), str(SCRIPTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from agy_nexus import __version__
from agy_nexus.ascii_default import render_ascii_default, render_ascii_quick
from agy_nexus.ascii_rich import render_ascii_rich
from agy_nexus.bucket_api import build_workspace_tree_payload
from agy_nexus.code_health import get_code_health_summary
from agy_nexus.config import AGY_BG_DIR, AGY_BRAIN_DIR, AGY_CONFIG_DIR, AGY_DATA_DIR, AGY_DB_FILE
from agy_nexus.session_tree import build_project_session_tree, render_ascii_session_tree
from agy_nexus.stats import build_nexus_stats_bundle

SHOWCASE_SALT = b"agy-nexus-v323-public-showcase"
PUBLIC_REPOS: frozenset[str] = frozenset({"agy-nexus-mcp", "quiet-ui-skills"})

# SHA-256[:12] hashes of private slugs/project names -> clean public open-source aliases.
_WS_HASH_ALIASES: dict[str, tuple[str, str]] = {
    "d3b2fffdf371": ("cloud-gitops-stack", "Cloud GitOps Stack"), "7e4712893a83": ("container-gitops", "Container & Edge GitOps"),
    "b69a2bdcf5ff": ("stem-curriculum-lab", "Stem Curriculum Lab"), "c79698445329": ("stem-curriculum-lab", "Stem Curriculum Lab"), "c96d8cec0414": ("stem-curriculum-lab", "Stem Curriculum Lab"),
    "706b7e095944": ("task-queue-engine", "Task Queue Engine"), "5ee3540e48a0": ("edge-iot-controller", "Edge IoT Controller"), "6f85b417c3da": ("edge-iot-controller", "Edge IoT Controller"),
    "03aac20b09f0": ("home-telemetry-bus", "Home Telemetry Bus"), "e4618e9965fa": ("home-telemetry-bus", "Home Telemetry Bus"), "0bcd728f4324": ("home-telemetry-bus", "Home Telemetry Bus"),
    "1cca6683e2c3": ("mail-triage-ui", "Mail Triage UI"), "6ab73f5201aa": ("net-topology-anms", "Net Topology ANMS"), "fdab4c070761": ("net-topology-anms", "Net Topology ANMS"), "68ed130a8c40": ("net-topology-anms", "Net Topology ANMS"),
    "870cda499a7c": ("agent-harness-cfg", "Agent Harness Config"), "855b121cc8bb": ("agent-harness-cfg", "Agent Harness Config"),
    "2f23e841e448": ("scratch-prototypes", "Scratch Prototypes"), "81df0b8858d1": ("scratch-prototypes", "General Prototypes"),
    "d6ae5d4f33c5": ("container-gitops", "Container GitOps"), "e25f1cb29a5e": ("rf-dsp-modem", "RF DSP Modem"),
    "a6e9ab25d0a2": ("audio-synth-studio", "Audio Synth Studio"), "5639308b1ddd": ("astro-sky-mapper", "Astro Sky Mapper"),
    "5c61d4f74fd5": ("civic-map-engine", "Civic Map Engine"), "251615180347": ("civic-map-engine", "Civic Map Engine"), "51f3746109d1": ("civic-map-engine", "Civic Map Engine"),
}

_SCRUB_TOKEN_REPLACEMENTS: dict[str, str] = {
    "d14f94143998": "example.invalid", "d7b198e6b435": "example.invalid", "8a802bc9956a": "edge-node", "43a90bfe213e": "nas-01", "13398c7a9455": "nas-01",
    "8c214ac536b7": "nas-02", "2a6574634363": "nas-02", "b1426473816d": "ip-cam", "8ba6d143eee8": "relay-hub",
    "07a07ff2a800": "oidc-sso", "d98970309b28": "doc-archive", "ce29c26322ab": "container-host",
    "422068e530b9": "SCL", "306f3216ffb6": "SCL-Core", "1d19d799bfb7": "SCL-Arch", "8d66bc0b2ba7": "SCL-Portal",
    "b4da5cf46e4c": "SCL-Chem", "aa50c46bd048": "SCL-RF", "706b7e095944": "task-queue-engine", "51f3746109d1": "civic-map",
    "6f85b417c3da": "edge-iot", "0bcd728f4324": "home-telemetry", "03aac20b09f0": "home-telemetry", "fa232a37422c": "home-telemetry",
    "1cca6683e2c3": "mail-triage", "68ed130a8c40": "net-topology", "ace3ceff4857": "net-topology", "5639308b1ddd": "astro-mapper",
    "d6ae5d4f33c5": "container-gitops", "c96d8cec0414": "scl-lab", "29478196cd2c": "scl-lab", "ac56ac1145af": "scl-lab",
}

_DOMAIN_TITLES: dict[str, list[str]] = {
    "net-topology-anms": ["Deterministic Multi-MCP Entity Fusion & FSD Hierarchy", "Topology Studio — Canvas Engine, Bento Solver & LOD Portals", "Rollout RCCA, Progressive Setup Wizard & Light UI", "Redis Capsule Vault, Rate Governance & Adaptive Light Shell"],
    "home-telemetry-bus": ["Edge Telemetry v2.0 — Event Bus Audit & Alert Debounce", "Edge Camera Stream v2.0 — Clip Indexing & Responsive Dashboard", "Storage Collector Integration — Sequence Engine & Buffering", "Relay Lighting Migration, Sky Curves & Chronogram Views"],
    "edge-iot-controller": ["MQTT Sparkplug Collector & Device Registry Sync", "Mobile Wall Panel Redesign & Responsive Grid Overhaul"],
    "stem-curriculum-lab": ["[SCL-Arch] Sprints 1–14 — Curriculum Engine & Edge CI", "[SCL-Portal] Landing Page, Control-Plane & OIDC Auth", "[SCL-RF] Ch. I–VIII Interactive Signal Modules Overhaul", "[SCL-Core] Stepped & Hex Domain Mosaics + Skill Trees", "[SCL-Chem] Sprint 12 Release Closeout & Live Preview"],
    "task-queue-engine": ["Sprints 1–5 (v1.0.0) — Core UX, Quick-Add & Calendar Sync", "Phase 0.5 — Container Stack, Scoped Auth & Core UI", "Phase 1.5 — Explorer Slideout, Routines & Category Filters"],
    "mail-triage-ui": ["Stages 1.0–3.8 — Core Classifier, Wizard & Sankey Audit", "Stage 5.1 — 3-Factor Outcomes & Multi-Pool Rules", "Stage 6.0 — Parent Vendor Consolidation & 6-Stage Sankey", "Stage 7.2 — Holdout Verification & Delta Scoreboard"],
    "cloud-gitops-stack": ["Infra Ops v2.0 — Portainer Guardrails & MCP Observability", "Document Archive Recovery & Worker Pinning Fix", "Identity Phase 1 — Container LDAP/OIDC & SSO Standup", "MCP Gateways v1.1 — Config Sync & Internal DNS Routing"],
    "container-gitops": ["Compose Hardening, Memory Caps & Watchdog Monitors", "Automated GitOps Stack Sync & Rollback Verification"],
    "agent-harness-cfg": ["Workspace v2.0 — 3-Pillar Layout & Worktree Recovery", "Permissions v1.0 — Sandbox & Command Allowlist Rules", "MCP Fleet v1.0 — Sidecar Health & Readiness Sweep", "Architecture v2.6 — Dual-Pool 8-Agent Roster & Carbon 4"],
    "rf-dsp-modem": ["Edition 6.0 — RF & DSP Interactive Lab & 3-Tier Solver"],
    "audio-synth-studio": ["DSP Oscillator Bank & Wavetable Envelope Editor"],
    "astro-sky-mapper": ["Coordinate Solver & Ephemeris Horizon Renderer"],
    "civic-map-engine": ["Sprint 0 — Choropleth Canvas, Boundaries & CSS Layers"],
    "scratch-prototypes": ["Workspace Hygiene v1.0 — Session Archiver & Standardization"],
}
_FALLBACK_SLUGS: tuple[str, ...] = ("telemetry-ingestor", "edge-proxy-rs", "workflow-runner", "media-pipeline", "auth-broker-oidc", "billing-ledger", "cache-shard-kv", "sensor-fusion-py")
_TARGET_SLUGS: frozenset[str] = PUBLIC_REPOS | {v[0] for v in _WS_HASH_ALIASES.values()} | set(_FALLBACK_SLUGS)
_CLEAN_WORKTREE_LEAVES: tuple[str, ...] = ("feat_api_gateway", "fix_telemetry_sync", "perf_canvas_solver", "feat_oidc_auth", "fix_mobile_grid", "refactor_worker_pool", "feat_cache_layer", "fix_ws_reconnect")


def _h12(raw: str) -> str:
    return hashlib.sha256((raw or "").strip().lower().encode("utf-8")).hexdigest()[:12]


def _load_secret_values() -> list[str]:
    vals: list[str] = []
    sec_p = Path.home() / ".config/ag-bridge-mcp/secrets.env"
    if sec_p.is_file():
        for ln in sec_p.read_text(encoding="utf-8", errors="ignore").splitlines():
            s = ln.strip()
            if s and not s.startswith("#") and "=" in s:
                v = s.split("=", 1)[1].strip().strip('"').strip("'")
                if len(v) >= 6 and "/" not in v:
                    vals.append(v)
    return vals


class ShowcaseDepersonalizer:
    """Deterministic 1-to-1 showcase aliaser holding zero private cleartext identifiers."""

    def __init__(self) -> None:
        self._dynamic_ws: dict[str, str] = {}
        self._fallback_idx = 0
        self._home_user = Path.home().name
        self._secret_vals = _load_secret_values()

    def uuid_alias(self, orig_id: str) -> str:
        raw = (orig_id or "").strip()
        if not raw or raw.startswith("ws:") or raw in ("__other_projects__", "outside-of-project"):
            if raw == "outside-of-project":
                return "ws:scratch-prototypes"
            if raw.startswith("ws:"):
                return f"ws:{self.alias_repo(raw[3:])}"
            return raw
        digest = bytearray(hmac.new(SHOWCASE_SALT, raw.encode("utf-8"), hashlib.sha256).digest()[:16])
        digest[6] = (digest[6] & 0x0F) | 0x40
        digest[8] = (digest[8] & 0x3F) | 0x80
        hx = digest.hex()
        return f"{hx[:8]}-{hx[8:12]}-{hx[12:16]}-{hx[16:20]}-{hx[20:32]}"

    def sha_alias(self, orig_sha: str) -> str:
        if not orig_sha:
            return ""
        return hashlib.sha256(SHOWCASE_SALT + orig_sha.encode("utf-8")).hexdigest()[: len(orig_sha)]

    def alias_repo(self, raw_slug: str) -> str:
        clean = (raw_slug or "").strip()
        low = clean.lower()
        if not clean:
            return "scratch-prototypes"
        if low in _TARGET_SLUGS:
            return low
        h = _h12(low)
        if h in _WS_HASH_ALIASES:
            return _WS_HASH_ALIASES[h][0]
        if low in self._dynamic_ws:
            return self._dynamic_ws[low]
        idx = self._fallback_idx
        self._fallback_idx += 1
        alias = _FALLBACK_SLUGS[idx] if idx < len(_FALLBACK_SLUGS) else f"sandbox-app-{idx - len(_FALLBACK_SLUGS) + 1:02d}"
        self._dynamic_ws[low] = alias
        return alias

    _SLUG_DISPLAY: dict[str, str] = {v[0]: v[1] for v in _WS_HASH_ALIASES.values()} | {
        "agy-nexus-mcp": "AGY Nexus MCP", "quiet-ui-skills": "Quiet UI Skills", "scratch-prototypes": "Scratch Prototypes",
    }

    def alias_project_name(self, pid: str, pname: str, fallback_slug: str = "") -> str:
        raw_p = (pname or "").strip()
        low_p = raw_p.lower()
        if low_p in self._SLUG_DISPLAY:
            return self._SLUG_DISPLAY[low_p]
        if fallback_slug.lower() in self._SLUG_DISPLAY:
            return self._SLUG_DISPLAY[fallback_slug.lower()]
        h_p = _h12(low_p)
        if h_p in _WS_HASH_ALIASES:
            return _WS_HASH_ALIASES[h_p][1]
        if fallback_slug:
            h_s = _h12(fallback_slug)
            if h_s in _WS_HASH_ALIASES:
                return _WS_HASH_ALIASES[h_s][1]
        return self.scrub_text(raw_p) if raw_p else self.alias_repo(fallback_slug)

    def scrub_text(self, text: str) -> str:
        if not text:
            return ""
        out = text
        if self._home_user and len(self._home_user) >= 3:
            out = out.replace(f"/home/{self._home_user}/", "/home/dev/")
            out = out.replace(f"/Users/{self._home_user}/", "/home/dev/")
            out = re.sub(rf"\b{re.escape(self._home_user)}\b", "dev", out)
        for sec in self._secret_vals:
            if sec in out:
                out = out.replace(sec, "showcase_token")
        out = re.sub(r"\b[a-z0-9-]+\.lan\b", "app-node.local", out, flags=re.I)
        out = re.sub(r"\b(?:192\.168|10\.\d+|172\.(?:1[6-9]|2\d|3[01]))\.\d+\.\d+\b", "10.0.0.10", out)
        for tok in set(re.findall(r"[A-Za-z0-9][A-Za-z0-9&._:/-]{2,}", out)):
            for part in [tok] + [p for p in re.split(r"[-_./:]", tok) if len(p) >= 3]:
                hx = _h12(part)
                rep = _WS_HASH_ALIASES[hx][0] if hx in _WS_HASH_ALIASES else _SCRUB_TOKEN_REPLACEMENTS.get(hx)
                if rep:
                    out = re.sub(rf"(?<![A-Za-z0-9]){re.escape(part)}(?![A-Za-z0-9])", rep, out)
        out = re.sub(r"\[([A-Za-z0-9]{2,5})-", lambda m: f"[{_SCRUB_TOKEN_REPLACEMENTS.get(_h12(m.group(1)), m.group(1))}-", out)
        return out

    def alias_workspace_path(self, raw_ws: str, repo_slug_hint: str = "") -> str:
        ws = (raw_ws or "").strip().rstrip("/")
        if not ws:
            return ""
        parts = [p for p in Path(ws).parts if p]
        aliased_repo = self.alias_repo(repo_slug_hint or (parts[-2] if "worktrees" in parts and len(parts) >= 2 else parts[-1]))
        if "worktrees" in parts:
            idx_w = parts.index("worktrees")
            aliased_repo = self.alias_repo(parts[idx_w + 1] if idx_w + 1 < len(parts) else aliased_repo)
            leaf = parts[idx_w + 2] if idx_w + 2 < len(parts) else "feat"
            clean_leaf = leaf if aliased_repo in PUBLIC_REPOS else _CLEAN_WORKTREE_LEAVES[int(_h12(leaf), 16) % len(_CLEAN_WORKTREE_LEAVES)]
            return f"/home/dev/.gemini/antigravity/worktrees/{aliased_repo}/{clean_leaf}"
        if "configuration" in parts:
            return f"/home/dev/agentic_workspace/configuration/{aliased_repo}"
        if "workbooks" in parts:
            return f"/home/dev/agentic_workspace/workbooks/{aliased_repo}"
        return f"/home/dev/agentic_workspace/projects/{aliased_repo}"

    def alias_title(self, raw_title: str, repo_slug: str, key_hint: str, idx_fallback: int = 0) -> str:
        if repo_slug in PUBLIC_REPOS and "Home" not in raw_title and ".lan" not in raw_title:
            return self.scrub_text(raw_title)
        if repo_slug == "quiet-ui-skills":
            return self.scrub_text(re.sub(r"\bHome\s+[A-Za-z]+\b", "Smart Telemetry", raw_title))
        pool = _DOMAIN_TITLES.get(repo_slug)
        if pool:
            return pool[int(_h12(key_hint or raw_title or str(idx_fallback)), 16) % len(pool)]
        return self.scrub_text(raw_title)

    def alias_handoff_id(self, raw_hid: str) -> str:
        if not raw_hid or "-" not in raw_hid:
            return raw_hid
        slug, num = raw_hid.rsplit("-", 1)
        return f"{self.alias_repo(slug)}-{num}"


def _scrub_handoff_record(
    rec: dict[str, Any], dp: ShowcaseDepersonalizer, fallback_slug: str, idx_rec: int,
    pid_override: str = "", pname_override: str = "",
) -> dict[str, Any]:
    new_repo = dp.alias_repo(str(rec.get("repo_slug") or fallback_slug))
    hid = dp.alias_handoff_id(str(rec.get("handoff_id") or rec.get("ticket_id") or ""))
    rec["handoff_id"], rec["repo_slug"] = hid, new_repo
    rec["workspace_path"] = dp.alias_workspace_path(str(rec.get("workspace_path") or ""), new_repo)
    rec["title"] = dp.alias_title(str(rec.get("title") or ""), new_repo, hid, idx_rec)
    if rec.get("handoff_file"):
        rec["handoff_file"] = f"staged_handoffs/{hid}.md"
    for k_id in ("ticket_id", "topic_slug"):
        if k_id in rec:
            rec[k_id] = hid
    for bk in ("default_branch", "branch"):
        if rec.get(bk):
            rec[bk] = dp.scrub_text(str(rec[bk]))
    for k_uuid in ("claimed_by_conversation_id", "target_conversation_id", "rollover_from"):
        if rec.get(k_uuid):
            rec[k_uuid] = dp.uuid_alias(str(rec[k_uuid]))
    if rec.get("superseded_by"):
        rec["superseded_by"] = dp.alias_handoff_id(str(rec["superseded_by"]))
    if isinstance(rec.get("superseded_ids"), list):
        rec["superseded_ids"] = [dp.alias_handoff_id(str(sid)) for sid in rec["superseded_ids"]]
    if rec.get("job_id"):
        rec["job_id"] = f"job-{dp.sha_alias(str(rec['job_id']))[:8]}"
    if pid_override or rec.get("project_id"):
        rec["project_id"] = pid_override or dp.uuid_alias(str(rec.get("project_id") or ""))
    if pname_override or rec.get("project_name"):
        rec["project_name"] = pname_override or dp.alias_project_name(str(rec.get("project_id") or ""), str(rec.get("project_name") or ""), new_repo)
    for rk in ("notes", "preview", "task_preview", "prompt", "handoff_markdown", "summary", "completion_notes", "resolution_notes"):
        rec.pop(rk, None)
    return rec


def _depersonalize_project_group(pg: dict[str, Any], dp: ShowcaseDepersonalizer) -> dict[str, Any]:
    out = copy.deepcopy(pg)
    raw_pid, raw_pname = str(out.get("project_id") or ""), str(out.get("project_name") or "")
    first_ws = next((str(s.get("workspace_path") or "") for s in (out.get("sessions") or []) if s.get("workspace_path")), "")
    fallback_slug = Path(first_ws).parent.name if "/worktrees/" in first_ws else Path(first_ws).name if first_ws else ""
    aliased_pname = dp.alias_project_name(raw_pid, raw_pname, fallback_slug)
    out["project_id"], out["project_name"] = dp.uuid_alias(raw_pid), aliased_pname
    if isinstance(out.get("workspaces"), list):
        out["workspaces"] = [dp.alias_workspace_path(w, fallback_slug) for w in out["workspaces"]]
    for idx_s, s in enumerate(out.get("sessions") or []):
        ws_orig = str(s.get("workspace_path") or "")
        new_ws = dp.alias_workspace_path(ws_orig, fallback_slug)
        repo_s = new_ws.split("/")[-2] if "/worktrees/" in new_ws else Path(new_ws).name
        s["conversation_id"] = dp.uuid_alias(str(s.get("conversation_id") or ""))
        s["project_id"], s["project_name"], s["workspace_path"] = out["project_id"], aliased_pname, new_ws
        s["workspace_short"] = Path(new_ws).name if new_ws else repo_s
        s["title"] = dp.alias_title(str(s.get("title") or ""), repo_s, str(s.get("conversation_id") or ""), idx_s)
        for rk in ("task_preview", "notes", "summary", "preview", "prompt"):
            s.pop(rk, None)
    for idx_h, ho in enumerate(out.get("staged_handoffs") or []):
        _scrub_handoff_record(ho, dp, fallback_slug, idx_h, out["project_id"], aliased_pname)
    return out


def depersonalize_stats_bundle(raw_bundle: dict[str, Any], dp: ShowcaseDepersonalizer) -> dict[str, Any]:
    b = copy.deepcopy(raw_bundle)
    b["version"] = __version__
    seen_ws_ids: set[int] = set()
    for list_key in ("all_workspaces", "top_workspaces"):
        for w in b.get(list_key) or []:
            if id(w) not in seen_ws_ids:
                seen_ws_ids.add(id(w))
                w["workspace"] = dp.alias_repo(str(w.get("workspace") or ""))
    ws_ser = b.get("workspace_series") or {}
    if isinstance(ws_ser, dict):
        old_keys = list(ws_ser.get("keys") or [])
        ws_ser["keys"] = [dp.alias_repo(k) for k in old_keys]
        for map_k in ("layers", "token_layers"):
            old_m = ws_ser.get(map_k) or {}
            ws_ser[map_k] = {dp.alias_repo(k): v for k, v in old_m.items()}
    ph = b.get("project_hierarchy") or {}
    if ph.get("latest_session_id"):
        ph["latest_session_id"] = dp.uuid_alias(str(ph["latest_session_id"]))
    for pk in ("top_projects", "idle_projects"):
        ph[pk] = [_depersonalize_project_group(pg, dp) for pg in (ph.get(pk) or [])]
    if isinstance(ph.get("other_projects"), dict):
        ph["other_projects"] = _depersonalize_project_group(ph["other_projects"], dp)
    def scrub_obj(obj: Any) -> Any:
        if isinstance(obj, str):
            return dp.scrub_text(obj)
        if isinstance(obj, list):
            return [scrub_obj(x) for x in obj]
        if isinstance(obj, dict):
            return {k: scrub_obj(v) for k, v in obj.items()}
        return obj

    ch = b.get("code_health") or {}
    if isinstance(ch.get("version"), dict):
        ch["version"] = {
            "installed": __version__, "remote": f"v{__version__}",
            "status": "up_to_date", "status_label": f"Up to Date (v{__version__})",
            "status_dot": "#10b981", "repo": "github.com/FrankXLT/agy-nexus-mcp",
        }
    for sub_k in ("polyglot_health", "local_lsp", "ast_integrity"):
        if sub_k in ch:
            ch[sub_k] = scrub_obj(ch[sub_k])
    for sk in ("wire_telemetry", "model_drift_status"):
        if sk in b:
            b[sk] = scrub_obj(b[sk])
    bk = b.get("backup_321") or {}
    if bk.get("head_sha"):
        bk["head_sha"] = dp.sha_alias(str(bk["head_sha"]))
        bk["origin_sha"] = bk["head_sha"]
        bk["gitlab_sha"] = bk["head_sha"]
        bk["short_sha"] = bk["head_sha"][:7]
    rt = b.get("routing_telemetry") or {}
    for sl in rt.get("slots") or []:
        sl["conversation_id"] = dp.uuid_alias(str(sl.get("conversation_id") or ""))
        sl["project_id"] = dp.uuid_alias(str(sl.get("project_id") or ""))
        sl["workspace"] = dp.alias_workspace_path(str(sl.get("workspace") or ""))
        sl["project_name"] = dp.alias_project_name(sl["project_id"], str(sl.get("project_name") or ""))
        repo_s = Path(sl["workspace"]).name if sl["workspace"] else "agy-nexus-mcp"
        sl["title"] = dp.alias_title(str(sl.get("title") or ""), repo_s, sl["conversation_id"])
    return b


def build_depersonalized_workspace_tree(dp: ShowcaseDepersonalizer, bundle_90d: dict[str, Any]) -> dict[str, Any]:
    wt = copy.deepcopy(build_workspace_tree_payload())
    q = wt.get("queue") or {}
    q["tickets"] = [_scrub_handoff_record(dict(tk), dp, "", idx_t) for idx_t, tk in enumerate((q.get("tickets") or [])[:25])]
    q["staged_count"] = sum(1 for t in q["tickets"] if t.get("status") == "STAGED")

    projects_out = [_depersonalize_project_group(pg, dp) for pg in (wt.get("projects") or [])]
    seen_names = {p["project_name"].lower() for p in projects_out}
    base_ts = max((float(p.get("last_updated_ts") or 0) for p in projects_out), default=1795050000.0)
    for ws_row in bundle_90d.get("all_workspaces") or []:
        if len(projects_out) >= 16:
            break
        w_slug = str(ws_row.get("workspace") or "")
        p_disp = dp.alias_project_name("", w_slug, w_slug)
        if p_disp.lower() in seen_names:
            continue
        seen_names.add(p_disp.lower())
        ts_val = base_ts - len(projects_out) * 72000.0
        cid = dp.uuid_alias(f"demo-{w_slug}")
        projects_out.append({
            "project_id": dp.uuid_alias(f"proj-{w_slug}"), "project_name": p_disp,
            "last_updated_ts": ts_val, "staged_count": 0, "in_work_count": 0, "completed_count": 1,
            "sessions": [{
                "conversation_id": cid, "title": dp.alias_title("", w_slug, cid),
                "workspace_path": f"/home/dev/agentic_workspace/projects/{w_slug}",
                "is_running": False, "is_pinned": False, "step_count": int(ws_row.get("steps") or 120),
                "relative_age": f"{max(1, len(projects_out) // 2)}d ago", "last_updated_ts": ts_val,
                "rollover_posture": "FRESH", "capture_count": 0, "upload_batches": [], "artifacts": [],
            }],
            "staged_handoffs": [],
        })
    for p in projects_out:
        for s in p.get("sessions") or []:
            s["rollover_posture"] = str(s.get("rollover_posture") or "FRESH")
            s["upload_batches"] = []
            s["artifacts"] = []
            if p["project_name"] == "AGY Nexus MCP" and (s.get("is_running") or __version__ in s.get("title", "")):
                s["capture_count"] = max(4, int(s.get("capture_count") or 4))
    projects_out.sort(key=lambda p: (-(float(p.get("last_updated_ts") or 0.0)), p["project_name"].lower()))
    sel_sess = next((p["sessions"][0]["conversation_id"] for p in projects_out if p["project_name"] == "AGY Nexus MCP" and p.get("sessions")), "")
    if not sel_sess and projects_out and projects_out[0].get("sessions"):
        sel_sess = projects_out[0]["sessions"][0]["conversation_id"]
    ch_ver = (bundle_90d.get("code_health") or {}).get("version") or {
        "installed": __version__, "remote": f"v{__version__}", "status": "up_to_date", "status_label": f"Up to Date (v{__version__})",
    }
    return {"ok": True, "version": __version__, "version_info": ch_ver, "queue": q, "projects": projects_out, "selected_session": sel_sess}


def _build_showcase_session_tree_ascii(dp: ShowcaseDepersonalizer) -> str:
    raw_tree = build_project_session_tree(active_only=False, limit=60, bg_dir=AGY_BG_DIR)
    picked: list[dict[str, Any]] = []
    for pg in raw_tree.get("projects") or []:
        dep = _depersonalize_project_group(pg, dp)
        dep["sessions"] = dep["sessions"][:3]
        dep["staged_handoffs"] = dep["staged_handoffs"][:2]
        picked.append(dep)
        if len(picked) >= 3:
            break
    for idx_p, pg in enumerate(picked, 1):
        pg["project_index"] = idx_p
    routing = {"active_slots": 3, "pinned_calls": 24, "auto_resolved_calls": 11, "ttl_remaining_min": 119.5}
    bk = depersonalize_stats_bundle({"backup_321": raw_tree.get("backup_321") or {}}, dp)["backup_321"]
    return render_ascii_session_tree(picked, routing, bk)


def _trim_bundle_for_snapshot(b: dict[str, Any], ascii_tree_str: str) -> dict[str, Any]:
    out = {k: b.get(k) for k in ("period", "kpis", "quota_and_pools", "model_usage_vs_target", "subagent_role_breakdown", "subagent_list", "all_workspaces", "top_workspaces", "velocity_series", "model_series", "subagent_series", "project_hierarchy", "heatmap_series", "wire_telemetry", "hourly_whiskers", "billing_comparison", "model_drift_status")}
    out.update({"server": b.get("server", "agy-nexus-mcp"), "version": __version__, "routing_telemetry": {"active_slots": 3, "pinned_calls": 24, "auto_resolved_calls": 11}, "project_session_tree": {"ascii_tree": ascii_tree_str}})
    out["backup_321"] = {k: v for k, v in (b.get("backup_321") or {}).items() if k in ("ok", "short_sha", "shas_match", "age", "bundle_size_kb", "status_label")}
    return out


def _collect_shared_dates(bundles: dict[str, dict[str, Any]]) -> dict[tuple[str, ...], str]:
    seen: dict[tuple[str, ...], str] = {}
    for b in bundles.values():
        for sec in ("velocity_series", "model_series", "subagent_series", "project_hierarchy"):
            d = (b.get(sec) or {}).get("dates")
            if isinstance(d, list) and len(d) >= 10:
                t = tuple(str(x) for x in d)
                if t not in seen:
                    seen[t] = f"_D{len(seen)}"
    return seen


def _to_compact_js(val: Any, date_vars: dict[tuple[str, ...], str]) -> str:
    if isinstance(val, dict):
        return "{" + ",".join(f"{json.dumps(str(k))}:{_to_compact_js(v, date_vars)}" for k, v in val.items()) + "}"
    if isinstance(val, list):
        if len(val) >= 10 and all(isinstance(x, str) for x in val):
            t = tuple(val)
            if t in date_vars:
                return f"{date_vars[t]}.slice()"
        if len(val) >= 40 and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in val):
            pairs = [f"{i},{x}" for i, x in enumerate(val) if x]
            if len(pairs) * 2 + 4 < len(val):
                return f"_z({len(val)},[{','.join(pairs)}])"
        return "[" + ",".join(_to_compact_js(x, date_vars) for x in val) + "]"
    return json.dumps(val, separators=(",", ":"), ensure_ascii=False)


def _update_readme_blocks(tree_ascii: str, def_ascii: str, qck_ascii: str, rich_ascii: str) -> None:
    readme_p = REPO_ROOT / "README.md"
    txt = readme_p.read_text(encoding="utf-8")
    blocks = [tree_ascii, def_ascii, qck_ascii, rich_ascii]
    pat = re.compile(r"```text\n[\s\S]*?\n```")
    matches = list(pat.finditer(txt))
    assert len(matches) >= 4, f"Expected at least 4 ```text blocks in README.md, found {len(matches)}"
    parts, pos = [], 0
    for idx in range(4):
        m = matches[idx]
        parts.extend([txt[pos : m.start()], f"```text\n{blocks[idx]}\n```"])
        pos = m.end()
    parts.append(txt[pos:])
    readme_p.write_text("".join(parts), encoding="utf-8")


def main() -> None:
    dp = ShowcaseDepersonalizer()
    raw_90 = build_nexus_stats_bundle(data_dir=AGY_DATA_DIR, brain_dir=AGY_BRAIN_DIR, db_file=AGY_DB_FILE, config_dir=AGY_CONFIG_DIR, bg_dir=AGY_BG_DIR, period="last_90d", style="default")
    dep_90 = depersonalize_stats_bundle(raw_90, dp)
    tree_ascii = _build_showcase_session_tree_ascii(dp)
    def_ascii, qck_ascii, rich_ascii = render_ascii_default(dep_90), render_ascii_quick(dep_90), render_ascii_rich(dep_90)
    for ln in qck_ascii.splitlines():
        assert len(ln) <= 40, f"quick line >40 chars ({len(ln)}): {ln}"
    export_specs = (
        ("current_month", "month", "to_date", 0), ("last_month", "month", "to_date", -1),
        ("qtd", "quarter", "to_date", 0), ("ytd", "year", "to_date", 0),
        ("last_30d", "month", "rolling", 0), ("last_90d", "quarter", "rolling", 0), ("last_year", "year", "rolling", 0),
    )
    bundles: dict[str, Any] = {}
    for pk, tf, hm, off in export_specs:
        rb = raw_90 if pk == "last_90d" else build_nexus_stats_bundle(data_dir=AGY_DATA_DIR, brain_dir=AGY_BRAIN_DIR, db_file=AGY_DB_FILE, config_dir=AGY_CONFIG_DIR, bg_dir=AGY_BG_DIR, timeframe=tf, horizon_mode=hm, offset=off, style="default")
        bundles[pk] = _trim_bundle_for_snapshot(depersonalize_stats_bundle(rb, dp), tree_ascii)
    date_vars = _collect_shared_dates(bundles)
    ws_tree = build_depersonalized_workspace_tree(dp, dep_90)
    from build_github_showcase import build_demo_sessions
    demo_sessions = build_demo_sessions(dp, ws_tree, bundles)
    snap_lines = [
        f"// Auto-generated depersonalized live showcase snapshot (v{__version__})",
        "(() => {",
        "  const _z = (n, p) => { const a = new Array(n).fill(0); for (let i = 0; i < p.length; i += 2) a[p[i]] = p[i + 1]; return a; };",
        *[f"  const {var_n} = {json.dumps(list(dt_tup), separators=(',', ':'))};" for dt_tup, var_n in date_vars.items()],
        "  window.DEMO_SNAPSHOT = {", f'    version: "{__version__}",',
        f"    code_health: {json.dumps(dep_90['code_health'], separators=(',', ':'), ensure_ascii=False)},",
        f"    workspace_tree: {json.dumps(ws_tree, separators=(',', ':'), ensure_ascii=False)},",
        f"    demo_sessions: {json.dumps(demo_sessions, separators=(',', ':'), ensure_ascii=False)},",
        "    bundles: {", *[f'      "{pk}": {_to_compact_js(bundles[pk], date_vars)},' for pk, _, _, _ in export_specs], "    },",
        "  };", "})();", "",
    ]
    snap_path = REPO_ROOT / "web" / "demo_snapshot.js"
    snap_path.write_text("\n".join(snap_lines), encoding="utf-8")
    _update_readme_blocks(tree_ascii, def_ascii, qck_ascii, rich_ascii)
    print(f"Wrote {snap_path.name} ({len(snap_lines)}L, {snap_path.stat().st_size} B) and updated README.md (4 ASCII blocks).")


if __name__ == "__main__":
    main()
