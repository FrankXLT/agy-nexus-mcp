#!/usr/bin/env python3
"""
scripts/build_github_showcase.py — Build & Privacy-Audit Public Static GitHub Pages Showcase.

Produces a completely self-contained, zero-backend static bundle in `build/gh-pages/`:
  - `.nojekyll` + relative `./` asset URLs + `manifest.webmanifest`
  - Quiet UI v9.3.0 Studio (`index.html` with `window.AGY_STATIC_SHOWCASE = true`)
  - Real-distribution depersonalized `demo_snapshot.js` across 7 windows & bundled Workspace sessions
  - Metadata-stripped PNG thumbnails (`tEXt`/`iTXt`/`zTXt`/`eXIf`/`tIME` chunks removed)
  - Hard fail-closed 0-leak privacy gate (`scan_showcase_privacy`)
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agy_nexus import __version__

_PNG_SIG = b"\x89PNG\r\n\x1a\n"
_PNG_META_CHUNKS = frozenset({b"tEXt", b"zTXt", b"iTXt", b"eXIf", b"tIME"})
_TEXT_EXTS = frozenset({".html", ".js", ".css", ".json", ".webmanifest", ".md", ".svg"})
_ALLOWED_PUBLIC_STRINGS = (
    "https://github.com/FrankXLT/agy-nexus-mcp",
    "github.com/FrankXLT/agy-nexus-mcp",
    "https://FrankXLT.github.io/agy-nexus-mcp",
    "FrankXLT.github.io/agy-nexus-mcp",
    "@users.noreply.github.com",
    "/home/dev/",
    "/home/dev",
    "selftest_runner.py",
)
_BANNED_HASHES = frozenset({
    "d3b2fffdf371", "7e4712893a83", "b69a2bdcf5ff", "c79698445329", "c96d8cec0414",
    "706b7e095944", "5ee3540e48a0", "6f85b417c3da", "03aac20b09f0", "e4618e9965fa",
    "0bcd728f4324", "1cca6683e2c3", "6ab73f5201aa", "fdab4c070761", "68ed130a8c40",
    "870cda499a7c", "855b121cc8bb", "2f23e841e448", "81df0b8858d1", "d6ae5d4f33c5",
    "e25f1cb29a5e", "a6e9ab25d0a2", "5639308b1ddd", "5c61d4f74fd5", "251615180347",
    "51f3746109d1", "d14f94143998", "d7b198e6b435", "8a802bc9956a", "43a90bfe213e",
    "13398c7a9455", "8c214ac536b7", "2a6574634363", "b1426473816d", "8ba6d143eee8",
    "07a07ff2a800", "d98970309b28", "ce29c26322ab", "fa232a37422c", "ac56ac1145af",
    "29478196cd2c", "2279a2478c30", "ace3ceff4857", "a955b9f5c160",
})


def _h12(raw: str) -> str:
    return hashlib.sha256((raw or "").strip().lower().encode("utf-8")).hexdigest()[:12]


def _pick_featured_sessions(ws_tree: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    picked: list[tuple[dict[str, Any], dict[str, Any]]] = []
    seen_cids: set[str] = set()
    preferred = ("AGY Nexus MCP", "Net Topology ANMS", "Stem Curriculum Lab", "Home Telemetry Bus")
    projs = list(ws_tree.get("projects") or [])
    ordered = sorted(projs, key=lambda p: (0 if p.get("project_name") in preferred else 1, -float(p.get("last_updated_ts") or 0)))
    for proj in ordered:
        sessions = proj.get("sessions") or []
        if not sessions:
            continue
        sess = sessions[0]
        cid = str(sess.get("conversation_id") or "")
        if not cid or cid in seen_cids:
            continue
        seen_cids.add(cid)
        picked.append((proj, sess))
        if len(picked) >= 4:
            break
    return picked


def _render_session_markdown_docs(
    proj: dict[str, Any], sess: dict[str, Any], idx: int, kpi_mtd: dict[str, Any], kpi_90d: dict[str, Any],
) -> dict[str, str]:
    pname = str(proj.get("project_name") or "Workspace Project")
    title = str(sess.get("title") or f"{pname} Architecture Session")
    ws_path = str(sess.get("workspace_path") or "/home/dev/agentic_workspace/projects/telemetry-pipeline")
    repo_slug = Path(ws_path).name or "telemetry-pipeline"
    steps = int(sess.get("step_count") or 180)
    mtd_cost = float(kpi_mtd.get("window_cost_usd") or 0.0)
    d90_steps = int(kpi_90d.get("window_steps") or 0)
    docs: dict[str, str] = {}
    docs["task.md"] = (
        f"# {title}\n\n"
        f"- **Repository**: `{repo_slug}` (`{ws_path}`)\n"
        f"- **Session Window**: {steps:,} steps · `{sess.get('relative_age', 'recent')}` · Posture `{sess.get('rollover_posture', 'FRESH')}`\n\n"
        "## Execution Checklist\n"
        "- [x] Sync Quiet UI v9.3.0 tokens & zero-CDN ECharts adapters\n"
        "- [x] Reconcile 8-model effective-dated micro-USD ledger (`CACHE_VERSION = 8`)\n"
        "- [x] Verify active-day hourly whisker distributions (`Min / Avg / Max + Last 24h`)\n"
        "- [x] Validate responsive Analytics (`390px / 820px / 1440px`) and Workspace captures\n"
    )
    docs["implementation_plan.md"] = (
        f"# Implementation Plan — {pname}\n\n"
        "## Architecture Summary\n"
        f"Cohesive modular rollout for `{repo_slug}` grounded in live 90-day fleet throughput "
        f"(`{d90_steps:,}` steps fleet-wide, MTD API equivalent `${mtd_cost:,.2f}`).\n\n"
        "| Module | Budget | Verification |\n"
        "| :--- | :---: | :--- |\n"
        "| `v9_analytics.js` | <= 500L | Pool reconciliation & KPI parity |\n"
        "| `v9_charts.js` | <= 500L | ECharts active-day whisker & slot scaling |\n"
        "| `v9_workspace.js` | <= 500L | Split doc reader & capture gallery |\n\n"
        "> [!NOTE]\n"
        "> All private repository identifiers, endpoints, and session UUIDs in this preview are SHA-256 aliased.\n"
    )
    thumb_map = ("demo_thumb_desktop.png", "demo_thumb_workspace.png", "demo_thumb_foldable.png", "demo_thumb_mobile.png")
    thumb_name = thumb_map[idx % len(thumb_map)]
    docs["walkthrough.md"] = (
        f"# Verification Walkthrough — {pname}\n\n"
        "## Visual & Telemetry Verification\n"
        f"Rendered and verified clean DOM geometry without horizontal overflow.\n\n"
        f"![{pname} Studio Capture](./{thumb_name})\n\n"
        "- **Modular Hygiene**: Every Python and frontend module remains `<= 500` lines.\n"
        "- **Dual-Pool Tracking**: Separates Google 20x Pool vs Partner 1x Pool quotas.\n"
    )
    if idx == 0:
        docs["scratch/gemini_research_handoff.md"] = (
            f"# Session Handoff — {repo_slug}-40\n\n"
            "- **Execution Mode**: `plan` (`stage & preview`)\n"
            "- **Artifact Scope**: Interactive GitHub Pages bundle & static Workspace docs\n"
            "- **Status**: Passed static hygiene, JS syntax check, and 0-leak privacy gate.\n"
        )
    return docs


def build_demo_sessions(dp: Any, ws_tree: dict[str, Any], bundles: dict[str, Any]) -> dict[str, Any]:
    """Attach 3-4 depersonalized bundled Workspace sessions with rich artifacts and captures."""
    kpi_mtd = (bundles.get("current_month") or {}).get("kpis") or {}
    kpi_90d = (bundles.get("last_90d") or {}).get("kpis") or {}
    thumb_specs = [
        ("demo_thumb_desktop.png", "desktop_analytics_1440x900.png", "desktop", 1440, 900),
        ("demo_thumb_workspace.png", "workspace_split_reader.png", "desktop", 1440, 900),
        ("demo_thumb_foldable.png", "foldable_unfolded_820x1080.png", "foldable", 820, 1080),
        ("demo_thumb_mobile.png", "mobile_viewport_390x844.png", "mobile", 390, 844),
    ]
    out: dict[str, Any] = {}
    for idx, (proj, sess) in enumerate(_pick_featured_sessions(ws_tree)):
        cid = str(sess["conversation_id"])
        ws_path = str(sess.get("workspace_path") or "")
        repo_slug = Path(ws_path).name or "telemetry-pipeline"
        raw_docs = _render_session_markdown_docs(proj, sess, idx, kpi_mtd, kpi_90d)
        clean_docs = {k: dp.scrub_text(v) for k, v in raw_docs.items()}
        artifacts = [{"name": k.split("/")[-1], "rel_path": k, "size": len(v), "type": "artifact"} for k, v in clean_docs.items()]
        rotated = thumb_specs[idx % len(thumb_specs) :] + thumb_specs[: idx % len(thumb_specs)]
        visuals = [
            {
                "name": name, "scope": f"demo-{cid}", "rel_path": name, "category": cat,
                "size": 64000, "width": w, "height": h, "asset_rel": rel,
            }
            for rel, name, cat, w, h in rotated
        ]
        repo_assets = [{
            "name": "code-health-watchlist.png", "scope": "repo-demo",
            "rel_path": "docs/assets/code-health-watchlist.png", "category": "repo_asset",
            "size": 51200, "width": 960, "height": 600, "asset_rel": "demo_thumb_health.png",
        }]
        out[cid] = {
            "repo_slug": repo_slug, "artifacts": artifacts, "uploads": [],
            "visual_artifacts": visuals, "repo_visual_assets": repo_assets, "files": clean_docs,
        }
        sess["capture_count"] = len(visuals)
        sess["artifacts"] = artifacts
    return out


def strip_png_metadata(src_path: Path, dst_path: Path) -> None:
    """Copy a PNG while stripping tEXt/zTXt/iTXt/eXIf/tIME ancillary metadata chunks."""
    data = src_path.read_bytes()
    if not data.startswith(_PNG_SIG):
        raise ValueError(f"Invalid PNG signature in {src_path}")
    chunks: list[bytes] = [_PNG_SIG]
    pos = len(_PNG_SIG)
    saw_iend = False
    while pos + 12 <= len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        ctype = data[pos + 4 : pos + 8]
        if length > len(data) - pos - 12:
            raise ValueError(f"Truncated/oversized PNG chunk in {src_path}")
        end = pos + 12 + length
        if ctype not in _PNG_META_CHUNKS:
            chunks.append(data[pos:end])
        pos = end
        if ctype == b"IEND":
            saw_iend = True
            break
    if not saw_iend:
        raise ValueError(f"Missing IEND chunk in {src_path}")
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.write_bytes(b"".join(chunks))


def _load_extra_banned_literals() -> set[str]:
    banned: set[str] = set()
    home_user = Path.home().name
    if len(home_user) >= 3:
        banned.add(home_user.lower())
    sec_p = Path.home() / ".config/ag-bridge-mcp/secrets.env"
    if sec_p.is_file():
        for ln in sec_p.read_text(encoding="utf-8", errors="ignore").splitlines():
            s = ln.strip()
            if s and not s.startswith("#") and "=" in s:
                val = s.split("=", 1)[1].strip().strip("\"'")
                if len(val) >= 8 and "/" not in val:
                    banned.add(val.lower())
    return banned


def _live_brain_uuids() -> set[str]:
    brain_dir = Path.home() / ".gemini/antigravity/brain"
    if not brain_dir.is_dir():
        return set()
    uuid_pat = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
    return {p.name.lower() for p in brain_dir.iterdir() if p.is_dir() and uuid_pat.match(p.name)}


def _inspect_png_privacy(png_path: Path, banned_literals: set[str], rel: str) -> list[str]:
    findings: list[str] = []
    raw = png_path.read_bytes()
    if not raw.startswith(_PNG_SIG):
        return [f"{rel}: invalid PNG header"]
    pos = len(_PNG_SIG)
    saw_iend = False
    while pos + 12 <= len(raw):
        length = struct.unpack(">I", raw[pos : pos + 4])[0]
        ctype = raw[pos + 4 : pos + 8]
        if length > len(raw) - pos - 12:
            findings.append(f"{rel}: truncated or oversized PNG chunk")
            break
        if ctype in _PNG_META_CHUNKS:
            findings.append(f"{rel}: disallowed PNG metadata chunk {ctype.decode('ascii', 'replace')}")
        pos += 12 + length
        if ctype == b"IEND":
            saw_iend = True
            break
    if not saw_iend:
        findings.append(f"{rel}: missing PNG IEND terminator")
    elif pos != len(raw):
        findings.append(f"{rel}: trailing bytes after PNG IEND ({len(raw) - pos} B)")
    low_bytes = raw.lower()
    for lit in banned_literals:
        if lit.encode("utf-8") in low_bytes:
            findings.append(f"{rel}: raw secret/username byte match")
    return findings


def scan_showcase_privacy(out_dir: Path) -> list[str]:
    """Fail-closed scanner ensuring 0 leaked repos, domains, LAN IPs, UUIDs, secrets, or PNG metadata."""
    findings: list[str] = []
    banned_lits = _load_extra_banned_literals()
    live_uuids = _live_brain_uuids()
    lan_pat = re.compile(r"\b[a-z0-9-]+\.lan\b", re.I)
    ip_pat = re.compile(r"\b(?:192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+)\b")
    for fp in sorted(out_dir.rglob("*")):
        if not fp.is_file():
            continue
        rel = fp.relative_to(out_dir).as_posix()
        if fp.suffix.lower() == ".png":
            findings.extend(_inspect_png_privacy(fp, banned_lits, rel))
            continue
        if fp.suffix.lower() not in _TEXT_EXTS and fp.name != ".nojekyll":
            continue
        txt = fp.read_text(encoding="utf-8", errors="ignore")
        sanitized = txt
        for allow in _ALLOWED_PUBLIC_STRINGS:
            sanitized = sanitized.replace(allow, " ")
        low = sanitized.lower()
        for m in lan_pat.findall(sanitized):
            findings.append(f"{rel}: disallowed .lan domain `{m}`")
        for m in ip_pat.findall(sanitized):
            if m != "10.0.0.10":
                findings.append(f"{rel}: private IP `{m}`")
        for lit in banned_lits:
            if re.search(rf"(?<![a-z0-9]){re.escape(lit)}(?![a-z0-9])", low):
                findings.append(f"{rel}: matched banned host/secret literal")
        for u in live_uuids:
            if u in low:
                findings.append(f"{rel}: un-aliased live UUID `{u[:8]}...`")
        for tok in set(re.findall(r"[A-Za-z0-9][A-Za-z0-9._+-]{2,}", sanitized)):
            for part in [tok] + [p for p in re.split(r"[-._/+]", tok) if len(p) >= 5]:
                if _h12(part) in _BANNED_HASHES:
                    findings.append(f"{rel}: hashed private identifier matched `{part[:3]}***`")
                    break
    return findings


def _rewrite_index_for_static(html_text: str) -> str:
    out = html_text.replace('href="/web/', 'href="./').replace('src="/web/', 'src="./')
    out = out.replace("content=\"/web/", "content=\"./")
    marker = '<script src="./demo_snapshot.js'
    flag_tag = '<script>window.AGY_STATIC_SHOWCASE = true;</script>\n  '
    if marker in out and "AGY_STATIC_SHOWCASE" not in out:
        out = out.replace(marker, f"{flag_tag}{marker}", 1)
    return out


def _rewrite_manifest_for_static(raw_manifest: str) -> str:
    data = json.loads(raw_manifest)
    data["id"] = "./"
    data["start_url"] = "./"
    data["scope"] = "./"
    for ic in data.get("icons") or []:
        if isinstance(ic, dict) and isinstance(ic.get("src"), str):
            ic["src"] = ic["src"].replace("/web/", "./")
    return json.dumps(data, indent=2) + "\n"


def build_showcase(out_dir: Path, *, refresh: bool = False) -> dict[str, Any]:
    """Assemble static GitHub Pages showcase in `out_dir` and enforce 0-leak privacy gate."""
    if refresh:
        scripts_dir = str(REPO_ROOT / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        import export_depersonalized_showcase as eds
        eds.main()

    web_dir = REPO_ROOT / "web"
    v9_dir = web_dir / "v9"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")

    src_html = web_dir / "index.html" if (web_dir / "index.html").is_file() else v9_dir / "index.html"
    (out_dir / "index.html").write_text(_rewrite_index_for_static(src_html.read_text(encoding="utf-8")), encoding="utf-8")
    (out_dir / "manifest.webmanifest").write_text(
        _rewrite_manifest_for_static((web_dir / "manifest.webmanifest").read_text(encoding="utf-8")), encoding="utf-8",
    )
    for asset_name in ("demo_snapshot.js", "gallery_select.js", "sheet_builder.js", "icon.svg", "icon-192.png", "icon-512.png"):
        src = web_dir / asset_name
        if src.is_file():
            if src.suffix.lower() == ".png":
                strip_png_metadata(src, out_dir / asset_name)
            else:
                shutil.copy2(src, out_dir / asset_name)
    for png_file in sorted(web_dir.glob("demo_thumb_*.png")):
        strip_png_metadata(png_file, out_dir / png_file.name)

    v9_out = out_dir / "v9"
    v9_out.mkdir(parents=True, exist_ok=True)
    for pattern in ("v9_*.css", "v9_*.js"):
        for fp in sorted(v9_dir.glob(pattern)):
            shutil.copy2(fp, v9_out / fp.name)
    shutil.copytree(v9_dir / "vendor", v9_out / "vendor", dirs_exist_ok=True)

    findings = scan_showcase_privacy(out_dir)
    if findings:
        sample = "\n  - ".join(findings[:10])
        raise RuntimeError(f"Showcase privacy scan failed ({len(findings)} issue(s)):\n  - {sample}")
    file_count = sum(1 for p in out_dir.rglob("*") if p.is_file())
    total_bytes = sum(p.stat().st_size for p in out_dir.rglob("*") if p.is_file())
    return {"ok": True, "version": __version__, "out_dir": str(out_dir), "files": file_count, "bytes": total_bytes, "privacy_findings": 0}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build depersonalized static GitHub Pages showcase.")
    parser.add_argument("--out", default=str(REPO_ROOT / "build" / "gh-pages"), help="Output directory")
    parser.add_argument("--refresh", action="store_true", help="Re-export web/demo_snapshot.js from live data first")
    args = parser.parse_args()
    res = build_showcase(Path(args.out).resolve(), refresh=args.refresh)
    print(f"[✓] Built v{res['version']} showcase in {res['out_dir']} ({res['files']} files, {res['bytes']} B, 0 leaks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
