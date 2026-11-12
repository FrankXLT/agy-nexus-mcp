#!/usr/bin/env python3
"""
agy_nexus.tools_media — Multimodal MCP ImageContent Endpoint (<20 KB WebP Thumbnails & Region Zoom).
"""

from __future__ import annotations

import io
import os
from pathlib import Path
import re
import shutil
from typing import Any

from fastmcp.utilities.types import Image as McpImage
from mcp.types import ImageContent, TextContent
try:
    from PIL import Image as PilImage, ImageDraw, ImageOps
    PilImage.MAX_IMAGE_PIXELS = 40_000_000
except ImportError:
    PilImage = ImageDraw = ImageOps = None  # type: ignore[assignment]

import agy_nexus.config as cfg
from agy_nexus.config import (
    AGY_BRAIN_DIR, AGY_DATA_DIR, AGY_GITLAB_DIR, LOCKED_RESPONSE, READONLY_ANNOTATIONS,
    SESSION_STATE, _compact_json, is_unlocked, mcp, pin_session_context,
)
from agy_nexus.media import (
    ALLOWED_MEDIA_EXTENSIONS, discover_visual_artifacts, get_public_base_url,
    record_verified_public_origin, sign_media_url,
)
from agy_nexus.routing import _resolve_session_identifier
from agy_nexus.workspace import _resolve_workspace_str

MAX_SOURCE_IMAGE_BYTES = 45 * 1024 * 1024
MAX_TOTAL_RAW_WEBP_BYTES = 12_200  # <= 16.3 KB base64 + ~1.8 KB JSON = <= 18.5 KB wire (<20 KB limit)

_REGION_PRESETS: dict[str, tuple[float, float, float, float]] = {
    "full": (0.0, 0.0, 1.0, 1.0),
    "top": (0.0, 0.0, 1.0, 0.38),
    "upper": (0.0, 0.18, 1.0, 0.56),
    "middle": (0.0, 0.31, 1.0, 0.69),
    "center": (0.0, 0.31, 1.0, 0.69),
    "lower": (0.0, 0.44, 1.0, 0.82),
    "bottom": (0.0, 0.62, 1.0, 1.0),
}


def _apply_region_crop(im: Any, region: str) -> tuple[Any, str]:
    """Crop an image to a named preset ('top'/'middle'/'bottom') or 'x,y,w,h' box before resizing."""
    w, h = im.size
    rk = (region or "full").strip().lower()
    if not rk or rk == "full":
        return im, "full"
    if rk in _REGION_PRESETS:
        fx0, fy0, fx1, fy1 = _REGION_PRESETS[rk]
        x0, y0, x1, y1 = int(w * fx0), int(h * fy0), max(int(w * fx0) + 16, int(w * fx1)), max(int(h * fy0) + 16, int(h * fy1))
        return im.crop((max(0, x0), max(0, y0), min(w, x1), min(h, y1))), rk
    parts = [p.strip() for p in rk.split(",")]
    if len(parts) == 4:
        try:
            vals = [float(p) for p in parts]
            if max(vals) <= 1.0 and min(vals) >= 0.0:
                x0, y0 = int(w * vals[0]), int(h * vals[1])
                x1, y1 = x0 + int(w * vals[2]), y0 + int(h * vals[3])
            else:
                x0, y0, x1, y1 = int(vals[0]), int(vals[1]), int(vals[0] + vals[2]), int(vals[1] + vals[3])
            x0, y0 = max(0, min(w - 16, x0)), max(0, min(h - 16, y0))
            x1, y1 = max(x0 + 16, min(w, x1)), max(y0 + 16, min(h, y1))
            return im.crop((x0, y0, x1, y1)), f"{x0},{y0},{x1 - x0},{y1 - y0}"
        except ValueError:
            pass
    return im, "full"


def encode_image_to_webp_budget(
    file_path: Path,
    budget_bytes: int = MAX_TOTAL_RAW_WEBP_BYTES,
    max_edge: int = 960,
    region: str = "full",
    min_quality: int = 22,
) -> tuple[bytes, dict[str, Any]]:
    """Downscale and encode PNG/JPEG/WebP/GIF to RGB WebP strictly within budget_bytes."""
    if PilImage is None or ImageOps is None:
        raise RuntimeError("Pillow is not installed in the active Python environment; install Pillow>=10.4.0.")
    st_size = file_path.stat().st_size
    if st_size > MAX_SOURCE_IMAGE_BYTES:
        raise ValueError(f"Image size ({st_size} B) exceeds 45 MB safety limit.")
    with PilImage.open(file_path) as raw_im:
        im = ImageOps.exif_transpose(raw_im)
        orig_w, orig_h = im.size
        cropped, applied_reg = _apply_region_crop(im, region)
        if cropped.mode in ("RGBA", "LA") or (cropped.mode == "P" and "transparency" in cropped.info):
            rgba = cropped.convert("RGBA")
            bg = PilImage.new("RGB", rgba.size, (15, 23, 42))
            bg.paste(rgba, mask=rgba.split()[3])
            rgb = bg
        else:
            rgb = cropped.convert("RGB")

    cw, ch = rgb.size
    full_ladder = [
        (1.0, 78), (1.0, 68), (0.92, 62), (0.84, 58), (0.74, 58),
        (0.64, 58), (0.60, 48), (0.50, 38), (0.38, 30), (0.28, 26), (0.20, 22),
    ]
    preferred = [step for step in full_ladder if step[1] >= min_quality] or full_ladder
    fallback = [step for step in full_ladder if step[1] < min_quality]
    best_bytes = b""
    thumb_w, thumb_h, used_q = cw, ch, 78
    for scale, qual in (*preferred, *fallback):
        lim_edge = max(80, int(round(max_edge * scale)))
        if max(cw, ch) > lim_edge:
            ratio = lim_edge / float(max(cw, ch))
            tw, th = max(1, int(round(cw * ratio))), max(1, int(round(ch * ratio)))
            work = rgb.resize((tw, th), PilImage.Resampling.LANCZOS)
        else:
            tw, th, work = cw, ch, rgb
        buf = io.BytesIO()
        work.save(buf, format="WEBP", quality=qual, method=4)
        cand = buf.getvalue()
        best_bytes, thumb_w, thumb_h, used_q = cand, tw, th, qual
        if len(cand) <= budget_bytes:
            break

    b64_len = ((len(best_bytes) + 2) // 3) * 4
    return best_bytes, {
        "original_px": f"{orig_w}x{orig_h}",
        "thumb_px": f"{thumb_w}x{thumb_h}",
        "region": applied_reg,
        "quality": used_q,
        "source_bytes": st_size,
        "webp_bytes": len(best_bytes),
        "wire_b64_bytes": b64_len,
    }


def _is_strict_child(cand: Path, roots: tuple[Path, ...]) -> bool:
    try:
        rc = cand.resolve()
        return any(rc != r and rc.is_relative_to(r) for r in roots)
    except Exception:
        return False


def _build_visual_catalog(conv_id: str, ws_path: Path, batch_folder: str = "") -> list[dict[str, Any]]:
    """Build sandbox-verified catalog of session scratch upload images + session/workspace visual artifacts."""
    catalog: list[dict[str, Any]] = []
    seen_real: set[str] = set()
    brain_root = AGY_BRAIN_DIR.resolve()
    allowed_ws_roots = (AGY_GITLAB_DIR.resolve(), (AGY_DATA_DIR / "worktrees").resolve())
    safe_cid = re.sub(r"[^a-zA-Z0-9_-]", "", conv_id)

    def _add_entry(fpath: Path, base_dir: Path, scope: str, seq_hint: int = 0, batch_name: str = "") -> None:
        try:
            rp = fpath.resolve()
            if str(rp) in seen_real or not rp.is_file() or rp.suffix.lower() not in ALLOWED_MEDIA_EXTENSIONS:
                return
            if rp == base_dir.resolve() or not rp.is_relative_to(base_dir.resolve()):
                return
            seen_real.add(str(rp))
            rel_str = str(rp.relative_to(base_dir.resolve())).replace("\\", "/")
            m_seq = re.match(r"^0*(\d{1,3})[_.-]", rp.name)
            seq_num = seq_hint or (int(m_seq.group(1)) if m_seq else 0)
            catalog.append({
                "seq": seq_num, "name": rp.name, "rel_path": rel_str, "scope": scope,
                "batch_folder": batch_name, "abs_path": rp, "signed_url": sign_media_url(scope, rel_str),
            })
        except Exception:
            return

    if safe_cid:
        sdir = (AGY_BRAIN_DIR / safe_cid).resolve()
        if sdir.is_dir() and _is_strict_child(sdir, (brain_root,)):
            scratch_dir = sdir / "scratch"
            if scratch_dir.is_dir():
                clean_bf = re.sub(r"[^a-zA-Z0-9_-]", "", batch_folder.strip())
                bf_cand = (scratch_dir / clean_bf).resolve() if clean_bf else None
                batches = [bf_cand] if (bf_cand and bf_cand.is_dir() and _is_strict_child(bf_cand, (scratch_dir.resolve(),))) else sorted(scratch_dir.glob("uploads_*"), reverse=True)
                for bdir in batches:
                    if bdir.is_dir() and _is_strict_child(bdir, (scratch_dir.resolve(),)):
                        imgs = [f for f in sorted(bdir.iterdir(), key=lambda x: x.name) if f.is_file() and f.suffix.lower() in ALLOWED_MEDIA_EXTENSIONS]
                        for idx, img_f in enumerate(imgs, 1):
                            _add_entry(img_f, sdir, f"brain:{safe_cid}", seq_hint=idx, batch_name=bdir.name)
            if not batch_folder.strip():
                for item in discover_visual_artifacts(safe_cid, str(ws_path), limit=30):
                    sc, rel = str(item.get("scope") or ""), str(item.get("rel_path") or "")
                    if sc == f"brain:{safe_cid}":
                        _add_entry(sdir / rel, sdir, sc)
                    elif sc.startswith("repo:") and ws_path.is_dir() and _is_strict_child(ws_path, allowed_ws_roots):
                        _add_entry(ws_path.resolve() / rel, ws_path.resolve(), sc)
    elif ws_path.is_dir() and _is_strict_child(ws_path, allowed_ws_roots):
        for item in discover_visual_artifacts("", str(ws_path), limit=30):
            _add_entry(ws_path.resolve() / str(item.get("rel_path") or ""), ws_path.resolve(), str(item.get("scope") or f"repo:{ws_path.name}"))
    return catalog


def _select_targets(catalog: list[dict[str, Any]], targets: str, conv_id: str, ws_path: Path, offset: int, limit: int) -> list[dict[str, Any]]:
    """Match sequence numbers ('#01', '1-3', '42'), relative paths, or substrings up to limit (1..4)."""
    eff_lim = max(1, min(int(limit or 2), 4))
    raw_t = (targets or "").strip()
    if not raw_t:
        start = max(0, int(offset or 0))
        return catalog[start : start + eff_lim]

    tokens: list[str] = []
    for part in [p.strip() for p in raw_t.split(",") if p.strip()]:
        m_rng = re.match(r"^#?0*(\d{1,3})\s*-\s*#?0*(\d{1,3})$", part)
        if m_rng:
            a, b = int(m_rng.group(1)), int(m_rng.group(2))
            step = 1 if b >= a else -1
            tokens.extend(str(n) for n in range(a, b + step, step)[:eff_lim])
        else:
            tokens.append(part)

    picked: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    brain_root = AGY_BRAIN_DIR.resolve()
    allowed_ws_roots = (AGY_GITLAB_DIR.resolve(), (AGY_DATA_DIR / "worktrees").resolve())
    safe_cid = re.sub(r"[^a-zA-Z0-9_-]", "", conv_id)

    for tok in tokens:
        if len(picked) >= eff_lim:
            break
        clean_tok = re.sub(r"^(?:image:|visual:)", "", tok.strip(), flags=re.IGNORECASE).strip()
        m_num = re.match(r"^#?0*(\d{1,3})$", clean_tok)
        match_item: dict[str, Any] | None = None
        if m_num:
            want_seq = int(m_num.group(1))
            match_item = next((c for c in catalog if c["seq"] == want_seq or re.match(rf"^0*{want_seq}[_.-]", c["name"])), None)
        if match_item is None:
            low = clean_tok.lower().lstrip("/")
            match_item = next((c for c in catalog if c["rel_path"].lower() == low or c["name"].lower() == low or c["rel_path"].lower().endswith("/" + low) or low in c["name"].lower()), None)
        if match_item is None and ".." not in Path(clean_tok).parts:
            for root_cand, sc_lbl in (
                (((AGY_BRAIN_DIR / safe_cid).resolve(), f"brain:{safe_cid}") if safe_cid else (None, "")),
                ((ws_path.resolve(), f"repo:{ws_path.name}") if ws_path.is_dir() else (None, "")),
            ):
                if root_cand and root_cand.is_dir():
                    is_ok_root = _is_strict_child(root_cand, (brain_root,)) if sc_lbl.startswith("brain:") else _is_strict_child(root_cand, allowed_ws_roots)
                    cand_f = (root_cand / clean_tok.lstrip("/")).resolve()
                    if is_ok_root and cand_f.is_file() and _is_strict_child(cand_f, (root_cand,)) and cand_f.suffix.lower() in ALLOWED_MEDIA_EXTENSIONS:
                        rel_s = str(cand_f.relative_to(root_cand)).replace("\\", "/")
                        match_item = {"seq": 0, "name": cand_f.name, "rel_path": rel_s, "scope": sc_lbl, "batch_folder": "", "abs_path": cand_f, "signed_url": sign_media_url(sc_lbl, rel_s)}
                        break
        if match_item and str(match_item["abs_path"]) not in seen_paths:
            seen_paths.add(str(match_item["abs_path"]))
            picked.append(match_item)
    return picked


@mcp.tool(annotations=READONLY_ANNOTATIONS, output_schema=None)
def inspect_visual_artifacts(
    targets: str = "",
    session_identifier: str = "",
    batch_folder: str = "",
    region: str = "full",
    offset: int = 0,
    limit: int = 2,
    workspace: str = "",
    spoken_passphrase: str = "",
) -> list[TextContent | ImageContent]:
    """Multimodal screenshot & visual artifact inspector returning native MCP ImageContent (WebP thumbnails strictly <20 KB total wire payload) plus 30-minute HMAC-signed HTTPS links.
    NOTE: Hosted Gemini Web/Mobile `custom_mcp` adapters strip binary MCP `ImageContent` blocks on ingress; when running from Gemini Web, share `signed_url` links with the user or route pixel review to Antigravity IDE.
    - targets: Comma-separated upload sequence numbers ('#01', '1,2', '1-4', '#42'), filenames, or relative paths. Leave empty to page through the latest upload batch or session artifacts via offset/limit (max 4 images/call).
    - region: 'full' (default), 'top', 'upper', 'middle', 'lower', 'bottom', or 'x,y,w,h' (0..1 normalized or pixels) to zoom into fine UI text on tall mobile screenshots at crisp detail."""
    if not is_unlocked(spoken_passphrase):
        return [TextContent(type="text", text=LOCKED_RESPONSE)]

    conv_id = _resolve_session_identifier(session_identifier.strip()) if session_identifier.strip() else str(SESSION_STATE.get("selected_session") or "")
    slot = (SESSION_STATE.get("active_contexts") or {}).get(conv_id, {}) if conv_id else {}
    ws_str = _resolve_workspace_str(workspace.strip()) if workspace.strip() else str(slot.get("workspace") or SESSION_STATE["session_workspace_map"].get(conv_id) or SESSION_STATE.get("selected_workspace") or AGY_GITLAB_DIR)
    ws_path = Path(ws_str) if ws_str else AGY_GITLAB_DIR
    allowed_ws_roots = (AGY_GITLAB_DIR.resolve(), (AGY_DATA_DIR / "worktrees").resolve())
    ws_ok = ws_path.is_dir() and _is_strict_child(ws_path, allowed_ws_roots)
    if conv_id:
        pin_session_context(conv_id, workspace=str(ws_path.resolve()) if ws_ok else "", mode="PINNED (VISION)", last_tool="inspect_visual_artifacts", set_default=False)

    eff_limit = max(1, min(int(limit or (1 if targets.strip() and "," not in targets and "-" not in targets else 2)), 4))
    catalog = _build_visual_catalog(conv_id, ws_path, batch_folder=batch_folder)
    selected = _select_targets(catalog, targets, conv_id, ws_path, offset=offset, limit=eff_limit)
    if not selected:
        return [TextContent(type="text", text=_compact_json({
            "ok": False, "conversation_id": conv_id, "total_available": len(catalog),
            "error": f"No matching visual artifacts found for targets='{targets}'.",
            "available_preview": [{"seq": c["seq"], "name": c["name"], "rel_path": c["rel_path"]} for c in catalog[:10]],
        }))]

    count = len(selected)
    per_img_budget = max(2_800, MAX_TOTAL_RAW_WEBP_BYTES // count)
    max_edge = 960 if count == 1 else (840 if count == 2 else (560 if count == 3 else 460))
    min_qual = 58 if count <= 2 else 22
    image_blocks: list[ImageContent] = []
    items_meta: list[dict[str, Any]] = []

    for item in selected:
        fpath: Path = item["abs_path"]
        if fpath.suffix.lower() == ".svg":
            if fpath.stat().st_size > MAX_SOURCE_IMAGE_BYTES:
                items_meta.append({"seq": item["seq"], "name": item["name"], "rel_path": item["rel_path"], "error": "SVG exceeds 45 MB limit."})
                continue
            with fpath.open("r", encoding="utf-8", errors="replace") as fh:
                svg_txt = fh.read(3500)
            items_meta.append({"seq": item["seq"], "name": item["name"], "rel_path": item["rel_path"], "format": "svg_xml_text", "svg_excerpt": svg_txt})
            continue
        try:
            webp_bytes, enc_meta = encode_image_to_webp_budget(
                fpath, budget_bytes=per_img_budget, max_edge=max_edge, region=region, min_quality=min_qual
            )
            image_blocks.append(McpImage(data=webp_bytes, format="webp").to_image_content())
            items_meta.append({
                "seq": item["seq"], "name": item["name"], "rel_path": item["rel_path"],
                "batch_folder": item["batch_folder"], "signed_url": item["signed_url"], **enc_meta,
            })
        except Exception as exc:
            items_meta.append({"seq": item["seq"], "name": item["name"], "rel_path": item["rel_path"], "error": str(exc)})

    next_off = (max(0, int(offset or 0)) + count) if not targets.strip() else None
    has_more = bool(next_off is not None and next_off < len(catalog))
    summary_payload: dict[str, Any] = {
        "ok": True, "conversation_id": conv_id, "returned_images": len(image_blocks),
        "total_available": len(catalog), "has_more": has_more,
        "next_offset": next_off if has_more else None,
        "zoom_tip": "Pass region='top'|'middle'|'bottom' or 'x,y,w,h' with 1-2 targets for retina-level text legibility.",
        "items": items_meta,
    }
    if count > 2 and (region or "full").strip().lower() == "full":
        summary_payload["zoom_warning"] = (
            "Multi-image (count>2) full-frame thumbnails compress small UI text to stay <20 KB. "
            "Pass limit=1 or limit=2 with region='top'|'middle'|'bottom' for crisp legibility."
        )
    summary_json = _compact_json(summary_payload)
    return [TextContent(type="text", text=summary_json), *image_blocks]


def run_multimodal_media_self_test(test_phrase: str, expected_hash: str) -> None:
    """Self-test public media URL resolution (zero PATH_SECRET leak) and <20 KB WebP ImageContent MCP wire delivery."""
    import agy_nexus.media as media_mod
    orig_pub, orig_dom, orig_sub, orig_drv = (os.environ.get(k) for k in ("AG_BRIDGE_PUBLIC_URL", "AG_BRIDGE_DOMAIN", "SUBDOMAIN_HASH", "_DERIVED_SECRETS_PUBLIC_URL"))
    orig_ver = media_mod._VERIFIED_REQUEST_ORIGIN
    try:
        media_mod._VERIFIED_REQUEST_ORIGIN = ""
        os.environ["AG_BRIDGE_PUBLIC_URL"] = "https://ag-test1234.example.net/secret_should_strip/mcp"
        assert get_public_base_url() == "https://ag-test1234.example.net", f"Expected stripped origin, got {get_public_base_url()}"
        os.environ["AG_BRIDGE_PUBLIC_URL"] = ""
        os.environ["SUBDOMAIN_HASH"] = "ab12cd34ef56"
        os.environ["AG_BRIDGE_DOMAIN"] = "example.net"
        assert get_public_base_url() == "https://ag-ab12cd34ef56.example.net"
        os.environ["AG_BRIDGE_DOMAIN"] = "example.com"
        os.environ["_DERIVED_SECRETS_PUBLIC_URL"] = "https://ag-derived99.example.net"
        assert get_public_base_url() == "https://ag-derived99.example.net"
        os.environ["_DERIVED_SECRETS_PUBLIC_URL"] = ""
        record_verified_public_origin([(b"host", b"evil.lan")], client_ip="10.0.0.10")
        assert media_mod._VERIFIED_REQUEST_ORIGIN == ""
        record_verified_public_origin([(b"host", b"workstation.lan:8765"), (b"x-forwarded-host", b"ag-proxy99.example.net")], client_ip="10.0.0.10")
        assert media_mod._VERIFIED_REQUEST_ORIGIN == "https://ag-proxy99.example.net"
        assert not _resolve_workspace_str("/etc").startswith("/etc")
    finally:
        media_mod._VERIFIED_REQUEST_ORIGIN = orig_ver
        for k, v in zip(("AG_BRIDGE_PUBLIC_URL", "AG_BRIDGE_DOMAIN", "SUBDOMAIN_HASH", "_DERIVED_SECRETS_PUBLIC_URL"), (orig_pub, orig_dom, orig_sub, orig_drv)):
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    tmp_cid = "00000000-0000-0000-0000-000000000099"
    tmp_bdir = AGY_BRAIN_DIR / tmp_cid / "scratch" / "uploads_20261111_120000"
    orig_hash = cfg.PASS_HASH
    cfg.PASS_HASH = expected_hash
    try:
        tmp_bdir.mkdir(parents=True, exist_ok=True)
        for idx in (1, 2):
            im = PilImage.new("RGBA", (1080, 2400), (14, 18, 26, 255))
            dr = ImageDraw.Draw(im)
            for y in range(0, 2400, 48):
                dr.rectangle([24, y + 8, 1056, y + 38], fill=(30 + (y % 90), 90 + (idx * 30), 160, 255))
            buf = io.BytesIO()
            im.save(buf, format="PNG")
            (tmp_bdir / f"{idx:02d}_mobile_shot.png").write_bytes(buf.getvalue())

        blocks_single = inspect_visual_artifacts(targets="#01", session_identifier=tmp_cid, region="top", spoken_passphrase=test_phrase)
        assert len(blocks_single) == 2 and isinstance(blocks_single[1], ImageContent) and blocks_single[1].mime_type == "image/webp"
        blocks_pair = inspect_visual_artifacts(targets="1-2", session_identifier=tmp_cid, spoken_passphrase=test_phrase)
        assert len(blocks_pair) == 3 and all(isinstance(b, ImageContent) for b in blocks_pair[1:])
        from agy_nexus.tools_workspace import ask_workspace_readonly
        fb_blocks = ask_workspace_readonly(question="Inspect #01", file_subpath="image:#01@top", session_identifier=tmp_cid, spoken_passphrase=test_phrase)
        assert isinstance(fb_blocks, list) and len(fb_blocks) == 2 and isinstance(fb_blocks[1], ImageContent)
        from starlette.testclient import TestClient
        with TestClient(mcp.http_app(path="/mcp", stateless_http=True, json_response=True)) as client:
            r = client.post("/mcp", headers={"Accept": "application/json, text/event-stream"}, json={
                "jsonrpc": "2.0", "id": 77, "method": "tools/call",
                "params": {"name": "inspect_visual_artifacts", "arguments": {"targets": "1-2", "session_identifier": tmp_cid, "spoken_passphrase": test_phrase}},
            })
            assert r.status_code == 200 and len(r.content) <= 20480, f"HTTP wire response failed or exceeded 20 KB: status={r.status_code} bytes={len(r.content)}"
            content_arr = r.json()["result"]["content"]
            assert len(content_arr) == 3 and content_arr[1]["type"] == "image" and content_arr[1]["mimeType"] == "image/webp"
    finally:
        cfg.PASS_HASH = orig_hash
        shutil.rmtree(AGY_BRAIN_DIR / tmp_cid, ignore_errors=True)
