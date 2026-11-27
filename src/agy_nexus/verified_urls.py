"""Verified HTTPS URL extraction, relative showcase expansion, GitHub PR/CI linking, and pill labeling."""

from __future__ import annotations

import ipaddress, json, re, subprocess, urllib.parse
from collections.abc import Sequence
from pathlib import Path

from agy_nexus import config as cfg
from agy_nexus.virtual_uris import resolve_transcript_file

_FORGE_HOSTS = frozenset({
    "github.com", "api.github.com", "raw.githubusercontent.com", "gist.github.com",
    "ghcr.io", "pypi.org", "www.pypi.org", "npmjs.com", "www.npmjs.com", "gitlab.com", "bitbucket.org",
})
_NON_REPO_OWNERS = frozenset({
    "features", "topics", "explore", "marketplace", "sponsors", "orgs",
    "users", "login", "signup", "settings", "about", "pricing", "site", "security",
})
_SENSITIVE_QS_KEYS = frozenset({
    "token", "access_token", "api_key", "apikey", "secret", "client_secret", "auth",
    "password", "passphrase", "sig", "signature", "jwt", "bearer",
    "x-amz-signature", "x-amz-credential", "x-amz-security-token",
})
_HTML_EXTS = (".html", ".htm", ".xhtml")
_ASSET_EXTS = (
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".ico", ".css", ".js", ".mjs",
    ".json", ".xml", ".yaml", ".yml", ".md", ".txt", ".py", ".sh", ".pdf", ".zip", ".whl", ".tar", ".gz",
    *_HTML_EXTS,
)
_URL_RE = re.compile(r"https://[^\s<>\"'`\]\[]+", flags=re.IGNORECASE)
_REL_SUBPATH_RE = re.compile(r"(?:^|[\s(\[`\"'])(\./|/)?(demo|docs)/(?:#([A-Za-z0-9_-]+))?(?=$|[\s)\]`\"'.!,;:?])")
_REL_OVERVIEW_RE = re.compile(r"(?:^|[\s(\[`\"'])\./(?=$|[\s)\]`\"'.,;:!?])")
_NUMERIC_LABEL_RE = re.compile(r"^(?:0x[0-9a-f]+|0[0-7]*|[1-9][0-9]*)$")
_PR_PATS = (re.compile(r"\b(?:PR|Pull\s+Request)\s*#?(\d{1,7})\b", flags=re.IGNORECASE), re.compile(r"(?:^|[\s(\[`])/?pull/(\d{1,7})\b", flags=re.IGNORECASE))
_CI_PATS = (
    re.compile(r"\b(?:CI|GitHub\s+Actions|Actions|workflow)\s+run(?:\s+id)?(?:\s*[:#]\s*|\s+)(\d{1,15})\b", flags=re.IGNORECASE),
    re.compile(r"\brun\s+#(\d{1,15})\b", flags=re.IGNORECASE),
    re.compile(r"\brun\s+id\s*[:#]?\s*(\d{1,15})\b", flags=re.IGNORECASE),
    re.compile(r"(?:^|[\s(\[`])/?actions/runs/(\d{1,15})\b", flags=re.IGNORECASE),
)


def normalize_github_remote_url(raw_url: str) -> str:
    """Normalize HTTPS/SSH GitHub remote URLs into https://github.com/<owner>/<repo>."""
    s = (raw_url or "").strip()
    if not s or any(ch.isspace() for ch in s):
        return ""
    scp = re.match(r"^(?:[A-Za-z0-9._-]+@)?github\.com:(.+)$", s, flags=re.IGNORECASE)
    if scp:
        path = scp.group(1)
    else:
        p = urllib.parse.urlsplit(s)
        if p.scheme.lower() not in ("https", "http", "ssh", "git") or (p.hostname or "").lower() != "github.com":
            return ""
        path = p.path
    parts = [seg for seg in path.strip("/").split("/") if seg]
    if len(parts) < 2:
        return ""
    owner, raw_repo = parts[0], parts[1]
    repo = raw_repo[:-4] if raw_repo.endswith(".git") else raw_repo
    if not owner or not repo or owner in (".", "..") or repo in (".", "..") or owner.lower() in _NON_REPO_OWNERS:
        return ""
    return f"https://github.com/{owner}/{repo}"


def resolve_repo_github_url(ws_path: str | Path) -> str:
    """Inspect ws_path git remotes (read-only) and return normalized GitHub repo URL or ''."""
    if not ws_path:
        return ""
    try:
        resolved = Path(ws_path).expanduser().resolve()
    except Exception:
        return ""
    if not resolved.is_dir() or resolved in {Path("/").resolve(), Path.home().resolve(), *cfg.get_umbrella_roots()}:
        return ""
    try:
        r1 = subprocess.run(["git", "-c", "safe.directory=*", "remote", "get-url", "origin"], cwd=str(resolved), capture_output=True, text=True, timeout=2, check=False)
        if r1.returncode == 0 and r1.stdout.strip():
            if norm := normalize_github_remote_url(r1.stdout.strip()):
                return norm
        r2 = subprocess.run(["git", "-c", "safe.directory=*", "remote", "-v"], cwd=str(resolved), capture_output=True, text=True, timeout=2, check=False)
        if r2.returncode == 0:
            for line in r2.stdout.splitlines():
                for tok in line.split():
                    if "github.com" in tok.lower() and (norm := normalize_github_remote_url(tok)):
                        return norm
    except Exception:
        return ""
    return ""


def _clean_extracted_url(raw: str) -> str:
    url = raw.strip().split("](", 1)[0].split("(file://", 1)[0].rstrip(".,:;'\"`]>}*")
    while url.endswith(")") and url.count("(") < url.count(")"):
        url = url[:-1].rstrip(".,:;'\"`]>}*")
    return url


def _is_public_host(raw_host: str) -> bool:
    if not raw_host or "%" in raw_host:
        return False
    host = raw_host.rstrip(".").lower()
    if not host or host in ("localhost", "localhost.localdomain", "host.docker.internal") or host.endswith((".lan", ".local", ".internal", ".home.arpa", ".localhost")):
        return False
    try:
        ip = ipaddress.ip_address(host)
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
            ip = ip.ipv4_mapped
        return ip.is_global
    except ValueError:
        labels = host.split(".")
        if len(labels) < 2 or any(not lbl for lbl in labels):
            return False
        if all(_NUMERIC_LABEL_RE.match(lbl) for lbl in labels) or _NUMERIC_LABEL_RE.match(labels[-1]):
            return False
        return True


def _has_sensitive_params(query: str, fragment: str) -> bool:
    pairs = list(urllib.parse.parse_qsl(query, keep_blank_values=True))
    if "=" in fragment:
        frag_qs = fragment.split("?", 1)[1] if "?" in fragment else fragment
        pairs.extend(urllib.parse.parse_qsl(frag_qs, keep_blank_values=True))
    return any(k.strip().lower() in _SENSITIVE_QS_KEYS or v.strip().lower() in _SENSITIVE_QS_KEYS for k, v in pairs)


def _is_allowed_https_url(url: str) -> bool:
    if not url or len(url) > 512 or any(ord(ch) < 32 or ord(ch) == 127 or ch.isspace() for ch in url):
        return False
    try:
        p = urllib.parse.urlsplit(url)
        _ = p.port
        host = (p.hostname or "").rstrip(".").lower()
    except ValueError:
        return False
    if p.scheme.lower() != "https" or p.username or p.password or not _is_public_host(p.hostname or ""):
        return False
    path_dec = urllib.parse.unquote(p.path or "/").lower()
    if (
        any(seg in path_dec for seg in ("/web/media/", "/web/gallery/", "/praxis/", "/polyglot/"))
        or path_dec in ("/web", "/web/media", "/web/gallery", "/mcp", "/praxis", "/polyglot")
        or path_dec.startswith(("/mcp/", "/web/"))
        or re.search(r"/[0-9a-f]{32,}/mcp(?:/|$)", path_dec)
    ):
        return False
    if _has_sensitive_params(p.query, p.fragment):
        return False
    if ((host == "google.com" or host.endswith(".google.com")) and path_dec.startswith(("/search", "/url"))) or (
        host == "vertexaisearch.cloud.google.com" and path_dec.startswith("/grounding-api-redirect")
    ):
        return False
    secrets = [
        s for s in (cfg.PATH_SECRET, cfg.PASS_HASH, cfg.get_host_bridge_token(), cfg.get_praxis_mcp_token(), cfg.get_polyglot_mcp_token())
        if s and len(s) >= 8
    ]
    url_low, url_unq_low = url.lower(), urllib.parse.unquote(url).lower()
    if any(sec.lower() in url_low or sec.lower() in url_unq_low for sec in secrets):
        return False
    if any(bad in url_low or bad in url_unq_low for bad in ("file://", "/home/", "/users/", "](", "[", "]")):
        return False
    if (
        host == "api.github.com"
        or (host == "github.com" and path_dec.startswith(("/login", "/oauth")))
        or re.match(r"^(?:ag|sync)-[0-9a-f]{10,}\.", host)
        or path_dec.endswith((".git", "/webhook", "/github-webhook-sync", "/callback"))
    ):
        return False
    return not ((host == "developers.google.com" and path_dec.startswith("/crawling/")) or "static.modelcontextprotocol.io/schemas" in url_low or host == "json-schema.org" or host.endswith(".json-schema.org"))


def _extract_showcase_root(url: str) -> tuple[str, bool]:
    p = urllib.parse.urlsplit(url)
    host = (p.hostname or "").rstrip(".").lower()
    if host in _FORGE_HOSTS:
        return "", False
    is_primary = host.endswith(".github.io") or host == "projects.oaworkbench.org"
    path = p.path or "/"
    last_seg = path.rstrip("/").rsplit("/", 1)[-1].lower()
    if is_primary and last_seg.endswith(_HTML_EXTS):
        path = path.rsplit("/", 1)[0] + "/"
        last_seg = path.rstrip("/").rsplit("/", 1)[-1].lower()
    for suffix in ("/demo/", "/demo", "/docs/", "/docs"):
        if path.endswith(suffix):
            return f"https://{p.netloc}{path[:-len(suffix)]}/", is_primary
    if last_seg.endswith(_ASSET_EXTS) or (not is_primary and not (path == "/" or path.endswith("/"))):
        return "", False
    return f"https://{p.netloc}{path if path.endswith('/') else path + '/'}", is_primary


def _canonicalize_url(url: str, showcase_roots: set[str]) -> tuple[str, str]:
    p = urllib.parse.urlsplit(url)
    host = (p.hostname or "").rstrip(".").lower()
    path = p.path or ""
    if host == "github.com":
        path = path.rstrip("/")
        canon = urllib.parse.urlunsplit(("https", p.netloc, path, p.query, p.fragment))
    else:
        last_seg = path.rstrip("/").rsplit("/", 1)[-1]
        if "." not in last_seg and (
            path.endswith(("/demo", "/docs")) or (f"https://{p.netloc.lower()}{path.rstrip('/')}/" in showcase_roots and not path.endswith("/"))
        ):
            path = f"{path}/"
        canon = urllib.parse.urlunsplit(("https", p.netloc, path, p.query, p.fragment))
    dedup_key = urllib.parse.urlunsplit(("https", p.netloc.lower(), path, p.query, p.fragment))
    return canon, dedup_key


def _expand_relative_and_github(texts: Sequence[str], showcase_roots: list[str], allow_bare: bool, gh_repo: str) -> list[str]:
    expanded: list[str] = []
    for raw_text in texts:
        if not raw_text:
            continue
        text = str(raw_text)
        for root in showcase_roots:
            for m in _REL_SUBPATH_RE.finditer(text):
                prefix, sub, frag = m.group(1) or "", m.group(2).lower(), m.group(3)
                if not allow_bare and prefix != "./":
                    continue
                expanded.append(f"{root}{sub}/#{frag}" if frag else f"{root}{sub}/")
            if _REL_OVERVIEW_RE.search(text):
                expanded.append(root)
        if gh_repo:
            for pat in _PR_PATS:
                expanded.extend(f"{gh_repo}/pull/{m.group(1)}" for m in pat.finditer(text) if int(m.group(1)) > 0)
            for pat in _CI_PATS:
                expanded.extend(f"{gh_repo}/actions/runs/{m.group(1)}" for m in pat.finditer(text) if int(m.group(1)) > 0)
    return expanded


def extract_verified_urls_from_texts(texts: Sequence[str], *, repo_github_url: str = "", max_urls: int = 16) -> list[str]:
    """Extract, expand, filter, and deduplicate verified HTTPS URLs from session texts."""
    if max_urls <= 0:
        return []
    explicit = [c for raw in texts if raw for m in _URL_RE.finditer(str(raw)) if _is_allowed_https_url(c := _clean_extracted_url(m.group(0)))]
    primary_roots, secondary_roots = [], []
    for u in explicit:
        root, is_primary = _extract_showcase_root(u)
        tgt = primary_roots if is_primary else secondary_roots
        if root and all(r.lower() != root.lower() for r in tgt):
            tgt.append(root)
    showcase_roots = primary_roots or secondary_roots
    gh_repo = normalize_github_remote_url(repo_github_url) or next((c for u in explicit if (c := normalize_github_remote_url(u))), "")
    result, seen, root_set = [], set(), {r.lower() for r in showcase_roots}
    for raw_u in [*explicit, *_expand_relative_and_github(texts, showcase_roots, bool(primary_roots), gh_repo)]:
        canon, key = _canonicalize_url(raw_u, root_set)
        if key not in seen:
            seen.add(key)
            result.append(canon)
            if len(result) >= max_urls:
                break
    return result


def _safe_read_brain_md(sdir: Path, name: str) -> str:
    """Safely read a regular non-symlink Markdown file strictly inside sdir."""
    p = sdir / name
    try:
        sdir_res = sdir.resolve()
        if p.is_symlink() or not p.is_file():
            return ""
        res = p.resolve()
        if res == sdir_res or not res.is_relative_to(sdir_res):
            return ""
        return res.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _read_latest_planner_response(session_dir: Path) -> str:
    tpath = resolve_transcript_file(session_dir)
    if not tpath:
        return ""
    try:
        sdir_res = session_dir.resolve()
        if tpath.is_symlink() or not tpath.is_file():
            return ""
        t_res = tpath.resolve()
        if t_res == sdir_res or not t_res.is_relative_to(sdir_res):
            return ""
        size = t_res.stat().st_size
        if size > 2 * 1024 * 1024:
            with t_res.open("rb") as fh:
                fh.seek(max(0, size - 1024 * 1024))
                raw_bytes = fh.read()
            nl = raw_bytes.find(b"\n")
            content_str = (raw_bytes[nl + 1:] if nl != -1 else raw_bytes).decode("utf-8", errors="replace")
        else:
            content_str = _safe_read_brain_md(session_dir, str(t_res.relative_to(sdir_res)))
        for line in reversed(content_str.splitlines()):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except Exception:
                continue
            if isinstance(entry, dict) and (entry.get("type") or entry.get("role") or "") in ("PLANNER_RESPONSE", "assistant", "model"):
                if text := str(entry.get("content") or entry.get("text") or "").strip():
                    return text
    except OSError:
        return ""
    return ""


def extract_verified_urls_for_session(
    conv_id: str, ws_path: str = "", *, brain_dir: Path | None = None,
    raw_latest_assistant: str = "", raw_walkthrough: str = "", raw_task: str = "", max_urls: int = 16,
) -> list[str]:
    """Load missing raw session texts and extract deduplicated verified HTTPS URLs."""
    eff_brain = (brain_dir or cfg.AGY_BRAIN_DIR).resolve()
    safe_cid = re.sub(r"[^a-zA-Z0-9_-]", "", conv_id or "")
    cand = (eff_brain / safe_cid).resolve() if safe_cid and safe_cid == conv_id else None
    sdir = cand if (cand and cand != eff_brain and cand.is_relative_to(eff_brain) and cand.is_dir()) else None
    walk_txt = raw_walkthrough or (_safe_read_brain_md(sdir, "walkthrough.md") if sdir else "")
    task_txt = raw_task or (_safe_read_brain_md(sdir, "task.md") if sdir else "")
    latest_txt = raw_latest_assistant or (_read_latest_planner_response(sdir) if sdir else "")
    repo_gh = resolve_repo_github_url(ws_path) if ws_path else ""
    return extract_verified_urls_from_texts([latest_txt, walk_txt, task_txt], repo_github_url=repo_gh, max_urls=max_urls)


def describe_verified_url(url: str) -> dict[str, str]:
    """Return pill label and kind metadata for a verified HTTPS URL."""
    try:
        p = urllib.parse.urlsplit(url)
    except ValueError:
        return {"url": url, "label": "Link", "kind": "link"}
    host = (p.hostname or "").lower()
    clean_path = (p.path or "/").rstrip("/")
    parts = [seg for seg in clean_path.split("/") if seg]
    if host == "github.com":
        if len(parts) >= 4 and parts[2] == "pull" and parts[3].isdigit():
            return {"url": url, "label": f"PR #{parts[3]}", "kind": "pr"}
        if len(parts) >= 5 and parts[2] == "actions" and parts[3] == "runs" and parts[4].isdigit():
            return {"url": url, "label": f"CI Run #{parts[4]}", "kind": "ci_run"}
        if len(parts) >= 5 and parts[2] == "releases" and parts[3] == "tag":
            return {"url": url, "label": f"Release {urllib.parse.unquote(parts[4])}", "kind": "release"}
        if len(parts) >= 4 and parts[2] == "commit":
            return {"url": url, "label": f"Commit {parts[3][:7]}", "kind": "commit"}
        if len(parts) == 2:
            return {"url": url, "label": "GitHub Repo", "kind": "github_repo"}
    if clean_path.endswith("/demo"):
        return {"url": url, "label": "Demo", "kind": "demo"}
    if clean_path.endswith("/docs"):
        return {"url": url, "label": "Docs", "kind": "docs"}
    if (host.endswith(".github.io") or host == "projects.oaworkbench.org") and len(parts) <= 1:
        return {"url": url, "label": "Overview", "kind": "overview"}
    if not parts:
        return {"url": url, "label": host or "Overview", "kind": "overview"}
    short_path = "/".join(parts)
    return {"url": url, "label": f"{host}/{short_path[:29] + '...' if len(short_path) > 32 else short_path}", "kind": "link"}
