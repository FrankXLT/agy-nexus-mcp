#!/usr/bin/env python3
"""agy_nexus.media_discovery — Session Ownership Windowing, Symlink-Safe Walkers & Git Status Media Discovery."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
import struct
import subprocess
from typing import Any
import urllib.parse

import agy_nexus.config as cfg
from agy_nexus.hygiene import is_sensitive_filename

SKIP_MEDIA_DIRS: frozenset[str] = frozenset({
    ".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
})
VISUAL_FOLDER_PREFIXES: tuple[str, ...] = (
    "screenshot", "proof", "capture", "artifact", "pilot",
)
VISUAL_FOLDER_EXACT: frozenset[str] = frozenset({"scratch", "assets"})


def is_visual_folder_name(name: str) -> bool:
    """Return True when folder name matches visual discovery conventions."""
    low = (name or "").lower()
    return low in VISUAL_FOLDER_EXACT or low.startswith(VISUAL_FOLDER_PREFIXES)


def walk_media_tree(
    root_dir: Path,
    max_depth: int,
    allow_dot_dirs: frozenset[str] = frozenset(),
) -> list[Path]:
    """Collect candidate files from root_dir down to max_depth subdirectories without following symlinks."""
    files: list[Path] = []
    stack: list[tuple[Path, int]] = [(root_dir, 0)]
    while stack:
        cur_dir, depth = stack.pop()
        try:
            for entry in cur_dir.iterdir():
                if entry.is_symlink():
                    continue
                if entry.is_file():
                    files.append(entry)
                elif entry.is_dir() and depth < max_depth:
                    name = entry.name
                    if name in SKIP_MEDIA_DIRS:
                        continue
                    if name.startswith(".") and name not in allow_dot_dirs:
                        continue
                    stack.append((entry, depth + 1))
        except Exception:
            continue
    return files


def count_brain_visual_captures(
    conv_id: str,
    extensions: dict[str, bytes] | frozenset[str] | set[str],
    brain_root: Path | None = None,
) -> int:
    """Fast count of valid non-sensitive visual files inside brain/<conv_id>/ for tree badges."""
    safe_cid = re.sub(r"[^a-zA-Z0-9_-]", "", conv_id or "")
    if not safe_cid:
        return 0
    base_root = (brain_root or cfg.AGY_BRAIN_DIR).resolve()
    brain_dir = (base_root / safe_cid).resolve()
    if brain_dir == base_root or not brain_dir.is_relative_to(base_root) or not brain_dir.is_dir():
        return 0
    cnt = 0
    for fpath in walk_media_tree(brain_dir, max_depth=3, allow_dot_dirs=frozenset({".user_uploaded"})):
        try:
            if fpath.is_symlink() or is_sensitive_filename(fpath.name):
                continue
            rp = fpath.resolve()
            if rp != brain_dir and rp.is_relative_to(brain_dir) and rp.suffix.lower() in extensions:
                if not is_sensitive_filename(rp.name):
                    cnt += 1
        except Exception:
            continue
    return cnt


def collect_git_status_media(ws_path: Path, extensions: dict[str, bytes]) -> list[Path]:
    """Query git status --porcelain -uall -z (1.5s cap) to detect uncommitted/untracked repo media."""
    if not (ws_path / ".git").exists():
        return []
    out: list[Path] = []
    try:
        proc = subprocess.run(
            ["git", "-c", "safe.directory=*", "-C", str(ws_path), "status", "--porcelain", "-uall", "-z"],
            capture_output=True, text=True, timeout=1.5, check=False,
        )
        if proc.returncode != 0 or not proc.stdout:
            return out
        tokens = proc.stdout.split("\0")
        idx = 0
        while idx < len(tokens):
            rec = tokens[idx]
            if len(rec) < 4:
                idx += 1
                continue
            xy, rel_p = rec[:2], rec[3:]
            idx += 2 if xy[0] in ("R", "C") else 1
            if not any(ch in xy for ch in ("?", "A", "M", "R", "C")):
                continue
            p_obj = Path(rel_p)
            if p_obj.suffix.lower() not in extensions:
                continue
            if any(pt in SKIP_MEDIA_DIRS for pt in p_obj.parts):
                continue
            out.append(ws_path / rel_p)
    except Exception:
        return out
    return out


def collect_repo_folder_media(ws_path: Path) -> list[Path]:
    """Collect media files from ws_path root and matched visual folders (top-level, docs/*, sidecar assets)."""
    files: list[Path] = []
    try:
        for entry in ws_path.iterdir():
            if entry.is_file():
                files.append(entry)
            elif entry.is_dir() and not entry.is_symlink() and not entry.name.startswith("."):
                if entry.name not in SKIP_MEDIA_DIRS and is_visual_folder_name(entry.name):
                    files.extend(walk_media_tree(entry, max_depth=2))
    except Exception:
        pass
    docs_dir = ws_path / "docs"
    if docs_dir.is_dir() and not docs_dir.is_symlink():
        try:
            for entry in docs_dir.iterdir():
                if entry.is_dir() and not entry.is_symlink() and not entry.name.startswith("."):
                    if entry.name not in SKIP_MEDIA_DIRS and is_visual_folder_name(entry.name):
                        files.extend(walk_media_tree(entry, max_depth=2))
        except Exception:
            pass
    sidecar_assets = ws_path / "sidecars/ag-bridge-mcp/docs/assets"
    if sidecar_assets.is_dir() and not sidecar_assets.is_symlink():
        files.extend(walk_media_tree(sidecar_assets, max_depth=2))
    return files


def parse_iso_epoch(raw_ts: str) -> float:
    """Convert SQLite/ISO timestamp text into UTC epoch seconds, returning 0.0 for sentinels/invalid values."""
    txt = str(raw_ts or "").strip()
    if not txt or txt.startswith("0001-"):
        return 0.0
    try:
        norm = re.sub(r"(\.\d{6})\d+", r"\1", txt.replace("Z", "+00:00"))
        if " " in norm[:12]:
            norm = norm.replace(" ", "T", 1)
        dt = datetime.fromisoformat(norm)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        ts = dt.timestamp()
        return ts if ts > 315360000.0 else 0.0
    except Exception:
        return 0.0


def format_relative_age(iso_str: str = "", ts: float = 0.0, *, now_ts: float | None = None) -> str:
    """Convert ISO-8601 timestamp or epoch seconds into compact relative age (e.g. '4m ago', '2h ago', '3d ago')."""
    eff_ts = float(ts or 0.0)
    if eff_ts <= 0.0:
        eff_ts = parse_iso_epoch(iso_str)
    if eff_ts <= 0.0:
        return "recent"
    ref_ts = float(now_ts) if now_ts is not None else datetime.now(timezone.utc).timestamp()
    diff_s = max(0, int(ref_ts - eff_ts))
    if diff_s < 60:
        return f"{diff_s}s ago"
    if diff_s < 3600:
        return f"{diff_s // 60}m ago"
    if diff_s < 86400:
        return f"{diff_s // 3600}h ago"
    return f"{diff_s // 86400}d ago"


def _transcript_start_epoch(brain_dir: Path | None) -> float:
    if brain_dir is None or not brain_dir.is_dir():
        return 0.0
    for rel in (".system_generated/logs/transcript.jsonl", ".system_generated/logs/transcript_full.jsonl"):
        tf = brain_dir / rel
        if not tf.is_file():
            continue
        try:
            with tf.open("r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line_s = line.strip()
                    if not line_s:
                        continue
                    obj = json.loads(line_s)
                    ts = parse_iso_epoch(str(obj.get("created_at") or ""))
                    if ts > 0.0:
                        return ts
                    break
        except Exception:
            continue
    return 0.0


def _brain_mtime_span(brain_dir: Path | None) -> tuple[float, float]:
    if brain_dir is None or not brain_dir.is_dir():
        return 0.0, 0.0
    mtimes: list[float] = []
    try:
        for entry in brain_dir.iterdir():
            if not entry.is_symlink() and not entry.name.startswith("."):
                mtimes.append(entry.stat().st_mtime)
    except Exception:
        pass
    return (min(mtimes), max(mtimes)) if mtimes else (0.0, 0.0)


def _uris_include_workspace(raw_uris: str, target_ws_str: str) -> bool:
    if not raw_uris or not target_ws_str:
        return False
    try:
        uris = json.loads(raw_uris)
    except Exception:
        return False
    if not isinstance(uris, list):
        return False
    for u in uris:
        norm = urllib.parse.unquote(re.sub(r"^file://(?:localhost)?", "", str(u or ""), flags=re.IGNORECASE)).rstrip("/")
        if not norm:
            continue
        if norm == target_ws_str:
            return True
        try:
            if str(Path(norm).resolve()) == target_ws_str:
                return True
        except Exception:
            continue
    return False


def resolve_session_ownership_window(
    conv_id: str,
    ws_res: Path,
    brain_dir: Path | None = None,
    db_file: Path | None = None,
) -> tuple[bool, float, float]:
    """Determine if conv_id is latest main session on ws_res and compute its [start_ts, end_ts+600s] active window."""
    ws_str = str(ws_res)
    eff_db = db_file if db_file is not None else cfg.AGY_DB_FILE
    main_rows: list[tuple[str, float, float]] = []
    self_row: tuple[str, float, float] | None = None

    eff_root = brain_dir.parent if (brain_dir and conv_id and brain_dir.name == conv_id) else cfg.AGY_BRAIN_DIR
    seen_cids: set[str] = set()
    if eff_db and eff_db.is_file():
        try:
            cols = "conversation_id, workspace_uris, last_modified_time, last_user_input_time, parent_conversation_id"
            with closing(sqlite3.connect(f"file:{eff_db}?mode=ro", uri=True, timeout=3)) as conn:
                rows_recent = conn.execute(
                    f"SELECT {cols} FROM conversation_summaries ORDER BY last_modified_time DESC LIMIT 500"
                ).fetchall()
                rows_sentinel = conn.execute(
                    f"SELECT {cols} FROM conversation_summaries "
                    "WHERE (last_modified_time IS NULL OR last_modified_time = '' OR last_modified_time LIKE '0001-%') "
                    "ORDER BY rowid DESC LIMIT 200"
                ).fetchall()
            for r_cid, r_uris, r_lmt, r_luit, r_parent in [*rows_recent, *rows_sentinel]:
                cid_s = str(r_cid or "")
                if not cid_s or cid_s in seen_cids or not _uris_include_workspace(str(r_uris or ""), ws_str):
                    continue
                seen_cids.add(cid_s)
                lmt_ts = parse_iso_epoch(str(r_lmt or ""))
                if lmt_ts <= 0.0 and eff_root and re.match(r"^[a-zA-Z0-9_-]{1,64}$", cid_s):
                    s_dir = brain_dir if (brain_dir and cid_s == conv_id) else (eff_root / cid_s)
                    if s_dir and not s_dir.is_symlink() and s_dir.is_dir():
                        try:
                            if s_dir.resolve().is_relative_to(eff_root.resolve()):
                                lmt_ts = float(s_dir.stat().st_mtime)
                        except OSError:
                            pass
                luit_ts = parse_iso_epoch(str(r_luit or ""))
                item = (cid_s, lmt_ts, luit_ts)
                if not str(r_parent or "").strip():
                    main_rows.append(item)
                if cid_s == conv_id:
                    self_row = item
            main_rows.sort(key=lambda it: it[1], reverse=True)
        except Exception:
            pass

    if not main_rows and self_row is None:
        return (True, 0.0, 0.0) if not (eff_db and eff_db.is_file()) else (bool(conv_id), 0.0, 0.0)

    is_latest = bool(conv_id and main_rows and main_rows[0][0] == conv_id)
    end_ts = self_row[1] if self_row else 0.0
    prev_end = 0.0
    if conv_id and main_rows:
        for idx, m_item in enumerate(main_rows):
            if m_item[0] == conv_id and idx + 1 < len(main_rows):
                prev_end = main_rows[idx + 1][1]
                break

    tr_start = _transcript_start_epoch(brain_dir)
    bm_min, bm_max = _brain_mtime_span(brain_dir)
    if end_ts <= 0.0:
        end_ts = bm_max
    own_cands = [ts for ts in (tr_start, bm_min, self_row[2] if self_row else 0.0) if ts > 0.0]
    if own_cands:
        start_ts = min(own_cands) - 60.0
        if prev_end > 0.0 and (end_ts <= 0.0 or prev_end <= end_ts):
            start_ts = max(start_ts, prev_end)
    elif prev_end > 0.0:
        start_ts = prev_end
    elif end_ts > 0.0:
        start_ts = max(0.0, end_ts - 86400.0)
    else:
        start_ts = 0.0
    win_end = (end_ts + 600.0) if end_ts > 0.0 else 0.0
    return is_latest, start_ts, win_end


def classify_repo_media(
    rp: Path,
    ws_res: Path,
    git_uncommitted_realpaths: set[str],
    has_git: bool,
    is_latest: bool,
    win_start: float,
    win_end: float,
    mtime: float,
) -> str:
    """Classify a repository visual file as 'session' or 'repo_asset' using session ownership and git status."""
    in_window = win_end > 0.0 and (win_start <= mtime <= win_end)
    if str(rp) in git_uncommitted_realpaths:
        return "session" if (is_latest or in_window) else "repo_asset"
    if has_git:
        return "repo_asset"
    rel_parts = [p.lower() for p in rp.relative_to(ws_res).parts]
    if len(rel_parts) <= 1 or "assets" in rel_parts[:-1]:
        return "repo_asset"
    return "session" if (is_latest or in_window) else "repo_asset"


def _parse_jpeg_dims(fh: Any) -> tuple[int, int] | None:
    """Scan up to 256 KB of JPEG SOFn segment headers for (width, height) without pixel decoding."""
    sof_markers = frozenset((0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF))
    fh.seek(0)
    buf = fh.read(262144)
    pos, total, markers = 2, len(buf), 0
    while pos < total and markers < 96:
        ff_idx = buf.find(b"\xff", pos)
        if ff_idx < 0:
            return None
        pos = ff_idx + 1
        while pos < total and buf[pos] == 0xFF:
            pos += 1
        if pos >= total:
            return None
        code = buf[pos]
        pos += 1
        markers += 1
        if code in (0xD8, 0x00, 0x01) or (0xD0 <= code <= 0xD7):
            continue
        if code in (0xD9, 0xDA):
            return None
        if pos + 2 > total:
            return None
        seg_len = struct.unpack(">H", buf[pos : pos + 2])[0]
        if seg_len < 2:
            return None
        if code in sof_markers:
            if seg_len < 7 or pos + 7 > total:
                return None
            h, w = struct.unpack(">HH", buf[pos + 3 : pos + 7])
            return (w, h) if (w > 0 and h > 0) else None
        pos += seg_len
    return None


def read_image_dimensions_fast(file_path: Path) -> tuple[int, int] | None:
    """Read (width, height) from PNG/JPEG/WebP/GIF headers in <2ms with lazy Pillow fallback (zero pixel decoding)."""
    try:
        with file_path.open("rb") as fh:
            hdr = fh.read(32)
            if len(hdr) >= 24 and hdr[:8] == b"\x89PNG\r\n\x1a\n" and hdr[12:16] == b"IHDR":
                w, h = struct.unpack(">II", hdr[16:24])
                return (w, h) if (w > 0 and h > 0) else None
            if len(hdr) >= 10 and hdr[:6] in (b"GIF87a", b"GIF89a"):
                w, h = struct.unpack("<HH", hdr[6:10])
                return (w, h) if (w > 0 and h > 0) else None
            if len(hdr) >= 30 and hdr[:4] == b"RIFF" and hdr[8:12] == b"WEBP":
                chunk = hdr[12:16]
                if chunk == b"VP8 " and hdr[23:26] == b"\x9d\x01\x2a":
                    w, h = struct.unpack("<HH", hdr[26:30])
                    w, h = (w & 0x3FFF, h & 0x3FFF)
                    return (w, h) if (w > 0 and h > 0) else None
                if chunk == b"VP8L" and hdr[20] == 0x2F:
                    bits = int.from_bytes(hdr[21:25], "little")
                    return ((bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1)
                if chunk == b"VP8X":
                    return (1 + int.from_bytes(hdr[24:27], "little"), 1 + int.from_bytes(hdr[27:30], "little"))
            if len(hdr) >= 2 and hdr[:2] == b"\xff\xd8":
                dims = _parse_jpeg_dims(fh)
                if dims:
                    return dims
    except Exception:
        pass
    try:
        from PIL import Image as PilImage
        if not PilImage.MAX_IMAGE_PIXELS or PilImage.MAX_IMAGE_PIXELS > 40_000_000:
            PilImage.MAX_IMAGE_PIXELS = 40_000_000
        with PilImage.open(file_path) as im:
            return int(im.size[0]), int(im.size[1])
    except Exception:
        return None

