#!/usr/bin/env python3
"""Check or apply SHA-256 parity between repo agents/*.md and ~/.gemini/config/agents/*.md."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = REPO_ROOT / "agents"
DEFAULT_TARGET_DIR = Path(os.getenv("AGY_CONFIG_DIR", "").strip() or str(Path.home() / ".gemini/config")).expanduser() / "agents"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_agent_sync(
    source_dir: Path = DEFAULT_SOURCE_DIR,
    target_dir: Path = DEFAULT_TARGET_DIR,
) -> dict[str, Any]:
    """Compute per-file SHA-256 parity between tracked repo agents/*.md and installed global agents."""
    rows: list[dict[str, Any]] = []
    synced = pending = 0
    if source_dir.is_dir():
        for src in sorted(source_dir.glob("*.md")):
            if src.name.upper() == "README.MD":
                continue
            dst = target_dir / src.name
            src_sha = _sha256_file(src)
            if dst.is_file():
                dst_sha = _sha256_file(dst)
                status = "SYNCED" if src_sha == dst_sha else "PENDING_SYNC"
            else:
                dst_sha = ""
                status = "PENDING_SYNC"
            if status == "SYNCED":
                synced += 1
            else:
                pending += 1
            rows.append({
                "file": src.name,
                "name": src.stem,
                "status": status,
                "repo_sha256": src_sha[:12],
                "global_sha256": dst_sha[:12] if dst_sha else "",
            })
    overall = "SYNCED" if pending == 0 and synced > 0 else ("PENDING_SYNC" if pending > 0 else "EMPTY")
    return {
        "ok": True,
        "overall_status": overall,
        "total": len(rows),
        "synced_count": synced,
        "pending_count": pending,
        "agents": rows,
    }


def apply_agent_sync(
    source_dir: Path = DEFAULT_SOURCE_DIR,
    target_dir: Path = DEFAULT_TARGET_DIR,
) -> dict[str, Any]:
    """Explicitly atomically copy tracked repo agents/*.md to target_dir when requested via --apply."""
    if source_dir.resolve() == target_dir.resolve():
        raise ValueError("source_dir and target_dir must not resolve to the same directory")
    target_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for src in sorted(source_dir.glob("*.md")):
        if src.name.upper() == "README.MD":
            continue
        dst = target_dir / src.name
        if not dst.is_file() or _sha256_file(src) != _sha256_file(dst):
            raw = src.read_bytes()
            fd, tmp_name = tempfile.mkstemp(prefix=f".{src.name}.", dir=str(target_dir))
            try:
                os.fchmod(fd, 0o644)
                with os.fdopen(fd, "wb") as fh:
                    fd = -1
                    fh.write(raw)
                os.replace(tmp_name, dst)
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
            copied.append(src.name)
    report = check_agent_sync(source_dir, target_dir)
    report["copied"] = copied
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Check or apply SHA-256 parity for tracked agents/*.md.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="Report SHA-256 parity (never mutates files, exits 0)")
    mode.add_argument("--apply", action="store_true", help="Explicitly sync repo agents/*.md to global agents dir")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--target-dir", type=Path, default=DEFAULT_TARGET_DIR)
    args = parser.parse_args()

    res = apply_agent_sync(args.source_dir, args.target_dir) if args.apply else check_agent_sync(args.source_dir, args.target_dir)
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print(f"Agent Sync Parity: {res['overall_status']} ({res['synced_count']}/{res['total']} synced, {res['pending_count']} pending)")
        for item in res["agents"]:
            print(f"  - {item['file']:22s} {item['status']:12s} repo={item['repo_sha256']} global={item['global_sha256'] or 'missing'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
