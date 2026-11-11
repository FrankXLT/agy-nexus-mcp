#!/usr/bin/env python3
"""
CLI utility to initialize or rotate ag-bridge-mcp runtime secrets and configurable
session / context-window budgets outside the Git repository (~/.config/ag-bridge-mcp/secrets.env).
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import os
import re
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path


def normalize_phrase(phrase: str) -> str:
    """Strip punctuation, spaces, and casing, then return SHA-256 hex digest."""
    clean = re.sub(r"[^a-z0-9]", "", (phrase or "").lower())
    return hashlib.sha256(clean.encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize or rotate ag-bridge-mcp secrets and configuration.")
    parser.add_argument("--passphrase", help="Spoken voice passphrase for deadbolt authentication (prompts if omitted)")
    parser.add_argument(
        "--env-file",
        default=str(Path.home() / ".config/ag-bridge-mcp/secrets.env"),
        help="Target secrets file path (default: ~/.config/ag-bridge-mcp/secrets.env)",
    )
    parser.add_argument("--domain", default=os.getenv("AG_BRIDGE_DOMAIN", "example.com"), help="Base domain (default: example.com)")
    parser.add_argument("--ttl", type=int, default=7200, help="Deadbolt session inactivity timeout in seconds (default: 7200)")
    parser.add_argument("--max-file-chars", type=int, default=15000, help="Max characters returned per file slice (default: 15000)")
    parser.add_argument("--max-diff-chars", type=int, default=15000, help="Max characters returned per git diff page (default: 15000)")
    parser.add_argument("--enforce-modular", default="true", help="Enforce <=300 line modular architecture standard (default: true)")
    parser.add_argument(
        "--keep-existing-urls",
        action="store_true",
        help="Retain existing SUBDOMAIN_HASH and PATH_SECRET when rotating passphrase",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Do not print generated secret tokens to stdout (only print masked confirmation)",
    )
    args = parser.parse_args()

    env_path = Path(args.env_file).expanduser().resolve()

    passphrase = args.passphrase
    if not passphrase:
        if sys.stdin.isatty():
            passphrase = getpass.getpass("Enter spoken voice passphrase for Antigravity deadbolt: ")
            confirm = getpass.getpass("Confirm voice passphrase: ")
            if passphrase != confirm:
                sys.exit("Error: Passphrases did not match.")
        else:
            sys.exit("Error: --passphrase required when stdin is not an interactive terminal.")

    passphrase = passphrase.strip()
    if not passphrase:
        sys.exit("Error: Passphrase cannot be empty.")

    pass_hash = normalize_phrase(passphrase)

    subdomain_hash = ""
    path_secret = ""
    host_bridge_token = ""

    if args.keep_existing_urls and env_path.is_file():
        try:
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("SUBDOMAIN_HASH="):
                    subdomain_hash = line.split("=", 1)[1].strip().strip("'\"")
                elif line.startswith("PATH_SECRET="):
                    path_secret = line.split("=", 1)[1].strip().strip("'\"")
                elif line.startswith("HOST_BRIDGE_TOKEN="):
                    host_bridge_token = line.split("=", 1)[1].strip().strip("'\"")
        except Exception:
            pass

    if not subdomain_hash:
        subdomain_hash = secrets.token_hex(6)       # 12 hex characters
    if not path_secret:
        path_secret = secrets.token_hex(24)         # 48 hex characters (192 bits)
    if not host_bridge_token:
        host_bridge_token = secrets.token_hex(32)   # 64 hex characters (256 bits)

    env_path.parent.mkdir(parents=True, exist_ok=True)
    full_url = f"https://ag-{subdomain_hash}.{args.domain}/{path_secret}/mcp"

    ts = datetime.now(timezone.utc).isoformat()
    content = (
        f"# ag-bridge-mcp runtime configuration & secrets\n"
        f"# Generated: {ts}\n"
        f"# Gemini Connected Apps URL: {full_url}\n\n"
        f"# --- Perimeter & Deadbolt Security ---\n"
        f"SUBDOMAIN_HASH={subdomain_hash}\n"
        f"PATH_SECRET={path_secret}\n"
        f"PASS_HASH={pass_hash}\n"
        f"HOST_BRIDGE_TOKEN={host_bridge_token}\n"
        f"TTL_SECONDS={args.ttl}\n"
        f"BIND_HOST=0.0.0.0\n"
        f"BIND_PORT=8765\n"
        f"HOST_BRIDGE_BIND_HOST=127.0.0.1\n"
        f"HOST_BRIDGE_BIND_PORT=8098\n\n"
        f"# --- Context Window & Pagination Budgets ---\n"
        f"MAX_FILE_CHARS={args.max_file_chars}\n"
        f"MAX_TOTAL_FILE_CHARS=24000\n"
        f"MAX_FILES_PER_CALL=6\n"
        f"MAX_DIFF_CHARS={args.max_diff_chars}\n"
        f"MAX_TRANSCRIPT_TURNS=10\n\n"
        f"# --- Modular Architecture & File Hygiene Standards ---\n"
        f"ENFORCE_MODULAR_HYGIENE={args.enforce_modular}\n"
        f"TARGET_FILE_LINES=300\n"
        f"HARD_MAX_FILE_LINES=400\n"
    )

    env_path.write_text(content, encoding="utf-8")
    os.chmod(env_path, 0o600)

    if args.quiet:
        print(f"[+] Secrets file initialized at {env_path} (mode 0600)")
        print(f"[+] Subdomain prefix: ag-{subdomain_hash[:4]}...{subdomain_hash[-4:]}.{args.domain}")
        print(f"[+] Capability path: /{path_secret[:6]}...{path_secret[-4:]}/mcp")
        print(f"[+] Deadbolt SHA-256: {pass_hash[:8]}...{pass_hash[-6:]}")
        return

    print("\n" + "=" * 70)
    print(" ag-bridge-mcp Configuration & Secrets Initialized ")
    print("=" * 70)
    print(f"[+] Secrets File:    {env_path} (mode: 600)")
    print(f"[+] Subdomain:       ag-{subdomain_hash}.{args.domain}")
    print(f"[+] Endpoint URL:    {full_url}")
    print(f"[+] Deadbolt Hash:   {pass_hash[:12]}...{pass_hash[-8:]}")
    print(f"[+] Deadbolt TTL:    {args.ttl}s")
    print(f"[+] File Slice Cap:  {args.max_file_chars} chars (line-range pagination enabled)")
    print(f"[+] Diff Page Cap:   {args.max_diff_chars} chars (offset & per-file pagination enabled)")
    print(f"[+] Modular Hygiene: {args.enforce_modular} (<= 300 lines/file target)")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
