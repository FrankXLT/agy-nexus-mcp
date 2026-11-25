#!/usr/bin/env python3
"""
Host Antigravity Language Server Quota Snapshot Exporter for AGY-Nexus MCP.

Probes running loopback `language_server` Connect-RPC listeners (`https://` self-signed TLS and `http://`)
and writes sanitized, zero-PII 0600 quota buckets + reset timestamps to `${AGY_BG_DIR}/live_quota_snapshot.json`
so unprivileged Docker containers (`ag-bridge-mcp`) see live quota without `pid: host`.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agy_nexus.ls_quota_probe import probe_local_language_server, write_quota_snapshot  # noqa: E402


def _default_bg_dir() -> Path:
    env_bg = os.getenv("AGY_BG_DIR", "").strip()
    if env_bg:
        return Path(env_bg).expanduser()
    env_data = os.getenv("AGY_DATA_DIR", "").strip()
    base = Path(env_data).expanduser() if env_data else (Path.home() / ".gemini" / "antigravity")
    return base / "sidecar_data" / "ag-bridge-bg"


def render_systemd_units(repo_root: Path) -> tuple[str, str]:
    """Build user systemd service & 60s timer unit contents for host quota synchronization."""
    service_txt = "\n".join([
        "[Unit]",
        "Description=AGY-Nexus Host Antigravity Language Server Quota Snapshot Exporter",
        "After=default.target",
        "",
        "[Service]",
        "Type=oneshot",
        f"WorkingDirectory={repo_root}",
        f"ExecStart=/usr/bin/env python3 {repo_root / 'scripts' / 'sync_host_quota.py'}",
        "PrivateTmp=true",
        "ProtectSystem=full",
        "ProtectHome=read-only",
        "ReadWritePaths=%h/.gemini/antigravity/sidecar_data",
        "",
        "[Install]",
        "WantedBy=default.target",
        "",
    ])
    timer_txt = "\n".join([
        "[Unit]",
        "Description=Refresh AGY-Nexus Live Language Server Quota Snapshot Every 60s",
        "",
        "[Timer]",
        "OnBootSec=15s",
        "OnUnitActiveSec=60s",
        "AccuracySec=5s",
        "",
        "[Install]",
        "WantedBy=timers.target",
        "",
    ])
    return service_txt, timer_txt


def install_systemd_user_units(repo_root: Path) -> dict[str, Any]:
    """Install and enable user systemd service + 60s timer under ~/.config/systemd/user/."""
    unit_dir = Path.home() / ".config" / "systemd" / "user"
    unit_dir.mkdir(parents=True, exist_ok=True)
    svc_txt, tmr_txt = render_systemd_units(repo_root)
    svc_path = unit_dir / "agy-quota-sync.service"
    tmr_path = unit_dir / "agy-quota-sync.timer"
    svc_path.write_text(svc_txt, encoding="utf-8")
    tmr_path.write_text(tmr_txt, encoding="utf-8")
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True, timeout=5.0)
    subprocess.run(["systemctl", "--user", "enable", "--now", "agy-quota-sync.timer"], check=True, timeout=5.0)
    subprocess.run(["systemctl", "--user", "start", "agy-quota-sync.service"], check=True, timeout=5.0)
    return {"installed": True, "service": str(svc_path), "timer": str(tmr_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync local Antigravity Language Server quota to live_quota_snapshot.json.")
    parser.add_argument("--bg-dir", default="", help="Override AGY_BG_DIR output directory.")
    parser.add_argument("--json", action="store_true", help="Print full sanitized JSON snapshot.")
    parser.add_argument("--install-systemd", action="store_true", help="Install & enable 60s user systemd timer.")
    args = parser.parse_args()

    if args.install_systemd:
        info = install_systemd_user_units(REPO_ROOT)
        if not args.json:
            print(f"[quota-sync] Installed & enabled {info['timer']}")

    bg_dir = Path(args.bg_dir).expanduser() if args.bg_dir else _default_bg_dir()
    live = probe_local_language_server()
    snap = write_quota_snapshot(bg_dir, live)
    if args.json:
        print(json.dumps(snap, indent=2))
    else:
        pools = snap.get("pools") or {}
        g5 = ((pools.get("google") or {}).get("bucket_5h") or {}).get("used_pct")
        gw = ((pools.get("google") or {}).get("bucket_weekly") or {}).get("used_pct")
        c5 = ((pools.get("claude") or {}).get("bucket_5h") or {}).get("used_pct")
        state = "LIVE" if snap.get("ls_alive") else "IDE_OFFLINE"
        print(f"[quota-sync] {state} | G-5h:{g5}% G-Wk:{gw}% | Partner-5h:{c5}% | models={len(snap.get('client_model_configs') or [])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
