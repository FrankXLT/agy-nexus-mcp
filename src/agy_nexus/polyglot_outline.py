#!/usr/bin/env python3
"""agy_nexus.polyglot_outline — Unified Polyglot Semantic Outliner & Caller Finder.

Extracts exact line spans (Lstart-Lend), line counts, signatures, and 1-liner
semantic docstrings/comments across Python, JS/TS/JSX/TSX/Vue, Markdown, JSON/JSONC,
YAML, TOML, HTML, CSS/SCSS, Shell, SQL, Go, and Rust with zero external dependencies.
"""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any

from agy_nexus.hygiene import is_sensitive_filename

LONG_FUNCTION_LINES = int(os.getenv("LONG_FUNCTION_LINES", "100"))

EXT_LANG: dict[str, str] = {
    ".py": "python", ".pyi": "python",
    ".md": "markdown", ".markdown": "markdown",
    ".json": "json", ".jsonc": "jsonc",
    ".yaml": "yaml", ".yml": "yaml", ".toml": "toml",
    ".css": "css", ".scss": "scss",
    ".html": "html", ".htm": "html", ".vue": "vue",
    ".sh": "shell", ".bash": "shell", ".zsh": "shell",
    ".sql": "sql", ".go": "go", ".rs": "rust",
    **{e: "javascript" for e in (".js", ".mjs", ".cjs", ".jsx")},
    **{e: "typescript" for e in (".ts", ".tsx")},
}


def _clean_one_liner(raw: str, max_len: int = 110) -> str:
    if not raw:
        return ""
    for line in raw.splitlines():
        s = re.sub(r"^[\s#/*>\-]+|[\s*/]+$", "", line).strip()
        if not s or s.startswith(("!", "eslint-", "prettier-", "noqa", "type:", "@param", "@return")):
            continue
        s = re.sub(r"\s+", " ", s)
        return (s[: max_len - 1].rstrip() + "…") if len(s) > max_len else s
    return ""


def _leading_comment_summary(lines: list[str], start_line: int) -> str:
    """Extract a 1-liner comment or JSDoc immediately above start_line (1-indexed)."""
    idx = start_line - 2
    collected: list[str] = []
    in_block = False
    steps = 0
    while idx >= 0 and steps < 8:
        s = lines[idx].strip()
        steps += 1
        idx -= 1
        if not s:
            if collected:
                break
            continue
        if s.startswith("@") and not s.startswith("/**"):
            continue
        if in_block:
            collected.append(s)
            if "/*" in s:
                break
            continue
        if s.endswith("*/"):
            collected.append(s)
            if "/*" in s:
                break
            in_block = True
            continue
        if s.startswith(("#", "//", "--")):
            if s.startswith("#!"):
                break
            collected.append(s)
            continue
        break
    if not collected:
        return ""
    collected.reverse()
    return _clean_one_liner("\n".join(collected))


def _file_top_summary(lines: list[str], lang: str, fallback: str = "") -> str:
    for raw in lines[:18]:
        s = raw.strip()
        if not s or s.startswith("#!"):
            continue
        if lang == "markdown" and s.startswith("#"):
            return _clean_one_liner(s.lstrip("#").strip())
        if s.startswith(("#", "//", "/*", "--")):
            cleaned = _clean_one_liner(s)
            if cleaned:
                return cleaned
        if not s.startswith(('"""', "'''", "---")):
            break
    return fallback


def _fmt_item_line(item: dict[str, Any], indent: int = 0) -> str:
    pad = "  " * indent
    sp = f"L{item['start_line']:03d}-L{item['end_line']:03d}"
    lc = f" ({item['lines']}L)" if item.get("lines", 0) >= 15 else ""
    summ = f" — {item['summary']}" if item.get("summary") else ""
    return f"{pad}{sp}{lc} {item['signature']}{summ}"


def _fmt_py_func(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    pfx = "async def " if isinstance(node, ast.AsyncFunctionDef) else "def "
    args = [a.arg for a in (node.args.posonlyargs + node.args.args + node.args.kwonlyargs)]
    if node.args.vararg:
        args.append(f"*{node.args.vararg.arg}")
    if node.args.kwarg:
        args.append(f"**{node.args.kwarg.arg}")
    sig_args = ", ".join(args)
    if len(sig_args) > 64:
        sig_args = sig_args[:61] + "..."
    ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    return f"{pfx}{node.name}({sig_args}){ret}"


def outline_python(lines: list[str], full_text: str, filename: str = "<python>") -> dict[str, Any]:
    imports: list[str] = []
    items: list[dict[str, Any]] = []
    formatted: list[str] = []
    try:
        tree = ast.parse(full_text, filename=filename)
    except SyntaxError as exc:
        err = f"L{exc.lineno or 1}: {exc.msg}"
        imp, syms, raw_items = outline_code(".py", lines)
        return {
            "summary": f"SyntaxError ({err})", "imports": imp, "symbols": syms,
            "symbol_items": raw_items, "syntax_error": err,
        }

    mod_doc = _clean_one_liner(ast.get_docstring(tree) or "") or _file_top_summary(lines, "python")
    for n in tree.body:
        if isinstance(n, (ast.Import, ast.ImportFrom)) and len(imports) < 15:
            imports.append(f"L{n.lineno:03d} {lines[n.lineno - 1].strip() if n.lineno <= len(lines) else ''}")
        elif isinstance(n, ast.ClassDef):
            st, en = n.lineno, getattr(n, "end_lineno", n.lineno) or n.lineno
            bases = f"({', '.join(ast.unparse(b) for b in n.bases)})" if n.bases else ""
            doc = _clean_one_liner(ast.get_docstring(n) or "") or _leading_comment_summary(lines, st)
            c_item = {
                "name": n.name, "kind": "class", "start_line": st, "end_line": en,
                "lines": en - st + 1, "signature": f"class {n.name}{bases}", "summary": doc,
            }
            items.append(c_item)
            formatted.append(_fmt_item_line(c_item, 0))
            for m in n.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    mst, men = m.lineno, getattr(m, "end_lineno", m.lineno) or m.lineno
                    mdoc = _clean_one_liner(ast.get_docstring(m) or "") or _leading_comment_summary(lines, mst)
                    m_item = {
                        "name": f"{n.name}.{m.name}", "kind": "method", "start_line": mst, "end_line": men,
                        "lines": men - mst + 1, "signature": _fmt_py_func(m), "summary": mdoc,
                    }
                    items.append(m_item)
                    formatted.append(_fmt_item_line(m_item, 1))
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            st, en = n.lineno, getattr(n, "end_lineno", n.lineno) or n.lineno
            doc = _clean_one_liner(ast.get_docstring(n) or "") or _leading_comment_summary(lines, st)
            f_item = {
                "name": n.name, "kind": "function", "start_line": st, "end_line": en,
                "lines": en - st + 1, "signature": _fmt_py_func(n), "summary": doc,
            }
            items.append(f_item)
            formatted.append(_fmt_item_line(f_item, 0))

    return {
        "summary": mod_doc, "imports": imports, "symbols": formatted,
        "symbol_items": items, "syntax_error": None,
    }


def outline_markdown(lines: list[str]) -> tuple[str, list[str], list[dict[str, Any]]]:
    raw_entries: list[dict[str, Any]] = []
    fence_char: str | None = None
    fence_start, fence_lang, n = 0, "", len(lines)
    for i, raw in enumerate(lines, 1):
        s = raw.strip()
        if s.startswith(("```", "~~~")):
            if fence_char is None:
                fence_char, fence_start = s[:3], i
                fence_lang = s[3:].strip().split()[0].lower() if s[3:].strip() else ""
            elif fence_char == s[:3]:
                raw_entries.append({"type": "c", "start": fence_start, "end": i, "lang": fence_lang})
                fence_char = None
        elif fence_char is None and (m := re.match(r"^(#{1,6})\s+(.*)$", s)):
            raw_entries.append({"type": "h", "start": i, "end": n, "lvl": len(m.group(1)), "t": m.group(2).strip()})
    if fence_char is not None:
        raw_entries.append({"type": "c", "start": fence_start, "end": n, "lang": fence_lang})

    headings = [it for it in raw_entries if it["type"] == "h"]
    for idx, h in enumerate(headings):
        for nxt in headings[idx + 1 :]:
            if nxt["lvl"] <= h["lvl"]:
                h["end"] = max(h["start"], nxt["start"] - 1)
                break

    formatted: list[str] = []
    sym_items: list[dict[str, Any]] = []
    for it in raw_entries:
        st, en = it["start"], it["end"]
        sp = f"L{st:03d}-L{en:03d}"
        if it["type"] == "h":
            prose = ""
            for ln in lines[st : min(en, st + 6)]:
                ls = ln.strip()
                if ls and not ls.startswith(("#", "```", "~~~", "---", "|", "<!--")):
                    prose = _clean_one_liner(ls, 90)
                    break
            sig = f"{'#' * it['lvl']} {it['t']}"
            sym_items.append({
                "name": it["t"], "kind": f"h{it['lvl']}", "start_line": st, "end_line": en,
                "lines": en - st + 1, "signature": sig, "summary": prose,
            })
            formatted.append(f"{'  ' * (it['lvl'] - 1)}{sp} {sig}{f' — {prose}' if prose else ''}")
        else:
            lbl = f"[code:{it['lang']}]" if it["lang"] else "[code]"
            formatted.append(f"{sp} {lbl}")
    top_sum = sym_items[0]["summary"] or sym_items[0]["name"] if sym_items else _file_top_summary(lines, "markdown")
    return top_sum, formatted, sym_items


def _clean_jsonc(text: str) -> str:
    out, i, n, in_s, q_c = [], 0, len(text), False, ""
    while i < n:
        c = text[i]
        if in_s:
            out.append(c)
            if c == "\\" and i + 1 < n:
                i += 1
                out.append(text[i])
            elif c == q_c:
                in_s = False
        elif text[i : i + 2] == "/*":
            end = text.find("*/", i + 2)
            if end == -1:
                break
            out.append("\n" * text[i : end + 2].count("\n"))
            i = end + 1
        elif text[i : i + 2] == "//":
            end = text.find("\n", i + 2)
            if end == -1:
                break
            i = end - 1
        elif c in ('"', "'"):
            in_s, q_c = True, c
            out.append(c)
        else:
            out.append(c)
        i += 1
    return re.sub(r",\s*([\]}])", r"\1", "".join(out))


def _json_val_desc(val: Any) -> str:
    if isinstance(val, bool):
        return "bool"
    if isinstance(val, (int, float, str)):
        return type(val).__name__
    if isinstance(val, dict):
        return f"dict[{len(val)} keys]"
    if isinstance(val, list):
        if val and isinstance(val[0], dict):
            return f"list[{len(val)} items] of {{{', '.join(list(val[0].keys())[:5])}}}"
        return f"list[{len(val)} items]"
    return "null" if val is None else type(val).__name__


def outline_json(lines: list[str]) -> tuple[str, list[str], list[dict[str, Any]]]:
    try:
        parsed: Any = json.loads(_clean_jsonc("\n".join(lines)))
    except Exception:
        parsed = None
    keys: list[dict[str, Any]] = []
    stack: list[tuple[str, int | None]] = []
    in_s, q_c, in_b, cur_top, pending_owner = False, "", False, "", None

    for l_idx, line in enumerate(lines, 1):
        i, n = 0, len(line)
        while i < n:
            ch = line[i]
            if in_b:
                if line[i : i + 2] == "*/":
                    in_b, i = False, i + 1
            elif in_s:
                if ch == "\\" and i + 1 < n:
                    i += 1
                elif ch == q_c:
                    in_s = False
            elif line[i : i + 2] == "/*":
                in_b, i = True, i + 1
            elif line[i : i + 2] == "//":
                break
            elif ch in ('"', "'"):
                depth, eq = len(stack), i + 1
                while eq < n:
                    if line[eq] == "\\" and eq + 1 < n:
                        eq += 2
                        continue
                    if line[eq] == ch:
                        break
                    eq += 1
                if eq < n and line[eq] == ch:
                    j = eq + 1
                    while j < n and line[j] in " \t":
                        j += 1
                    if j < n and line[j] == ":":
                        k_name, k_idx, st = line[i + 1 : eq], len(keys), [s[0] for s in stack]
                        if depth == 1 and st == ["{"]:
                            cur_top = k_name
                            desc = _json_val_desc(parsed[k_name]) if isinstance(parsed, dict) and k_name in parsed else ""
                            keys.append({"lvl": 1, "name": k_name, "start": l_idx, "end": l_idx, "desc": desc})
                            pending_owner, i = k_idx, j
                        elif depth == 2 and st == ["{", "{"]:
                            sub = parsed.get(cur_top) if isinstance(parsed, dict) else None
                            desc = _json_val_desc(sub.get(k_name)) if isinstance(sub, dict) and k_name in sub else ""
                            keys.append({"lvl": 2, "name": k_name, "start": l_idx, "end": l_idx, "desc": desc})
                            pending_owner, i = k_idx, j
                        else:
                            in_s, q_c = True, ch
                    else:
                        in_s, q_c = True, ch
                else:
                    in_s, q_c = True, ch
            elif ch in ("{", "["):
                stack.append((ch, pending_owner))
                pending_owner = None
            elif ch in ("}", "]") and stack:
                _, owner = stack.pop()
                if owner is not None and owner < len(keys):
                    keys[owner]["end"] = l_idx
            i += 1

    sym_items = [
        {
            "name": k["name"], "kind": "json_key", "start_line": k["start"], "end_line": k["end"],
            "lines": k["end"] - k["start"] + 1, "signature": f'"{k["name"]}"', "summary": k["desc"],
        }
        for k in keys
    ]
    formatted = [
        f"{'  ' if k['lvl'] == 2 else ''}L{k['start']:03d}-L{k['end']:03d} \"{k['name']}\"{': ' + k['desc'] if k['desc'] else ''}"
        for k in keys
    ]
    top_names = [k["name"] for k in keys if k["lvl"] == 1][:6]
    summary = f"Keys: {', '.join(top_names)}" if top_names else (_json_val_desc(parsed) if parsed is not None else "")
    return summary, formatted, sym_items


def outline_yaml(lines: list[str]) -> tuple[str, list[str], list[dict[str, Any]]]:
    entries: list[dict[str, Any]] = []
    n, cur_child_ind = len(lines), 2
    sec_re = re.compile(r"secret|token|password|passwd|api_key|apikey|private_key|bearer", re.I)
    for idx, raw in enumerate(lines, 1):
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        ind = len(raw) - len(raw.lstrip(" "))
        if ind == 0 and (m := re.match(r"^([a-zA-Z0-9_.-]+):\s*(.*)$", s)):
            k = m.group(1)
            entries.append({"lvl": 1, "ind": 0, "start": idx, "end": idx, "name": k, "lbl": f"{k}:", "summary": _leading_comment_summary(lines, idx)})
            cur_child_ind = 0
        elif ind > 0:
            if cur_child_ind == 0:
                cur_child_ind = ind
            m_seq = re.match(r"^-\s+(alias|id|name|service|platform|action):\s*(.*)$", s)
            m_key = re.match(r"^([a-zA-Z0-9_.-]+):\s*(.*)$", s)
            if ind == cur_child_ind and m_seq:
                tag, val = m_seq.group(1), m_seq.group(2).strip()
                safe_v = "[REDACTED]" if sec_re.search(val) else val[:64]
                entries.append({"lvl": 2, "ind": ind, "start": idx, "end": idx, "name": safe_v or tag, "lbl": f"- {tag}: {safe_v}", "summary": _leading_comment_summary(lines, idx)})
            elif ind == cur_child_ind and m_key:
                k = m_key.group(1)
                entries.append({"lvl": 2, "ind": ind, "start": idx, "end": idx, "name": k, "lbl": f"{k}:", "summary": _leading_comment_summary(lines, idx)})

    for i, e in enumerate(entries):
        end = n
        for nxt in entries[i + 1 :]:
            if nxt["ind"] <= e["ind"]:
                end = nxt["start"] - 1
                break
        while end > e["start"] and not lines[end - 1].strip():
            end -= 1
        e["end"] = max(e["start"], end)

    sym_items = [
        {"name": e["name"], "kind": "yaml_key", "start_line": e["start"], "end_line": e["end"], "lines": e["end"] - e["start"] + 1, "signature": e["lbl"], "summary": e["summary"]}
        for e in entries
    ]
    formatted = [
        ("  " if e["lvl"] == 2 else "") + f"L{e['start']:03d}-L{e['end']:03d} {e['lbl']}" + (f" — {e['summary']}" if e["summary"] else "")
        for e in entries
    ]
    top_keys = [e["name"] for e in entries if e["lvl"] == 1][:6]
    top_sum = _file_top_summary(lines, "yaml", f"YAML keys: {', '.join(top_keys)}" if top_keys else "")
    return top_sum, formatted, sym_items


def _outline_html_css(ext: str, lines: list[str]) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    imports: list[str] = []
    sym_items: list[dict[str, Any]] = []
    if ext in (".html", ".htm"):
        s_pat = re.compile(r"<script[^>]+src=[\"']([^\"']+)[\"']")
        l_pat = re.compile(r"<link[^>]+href=[\"']([^\"']+)[\"']")
        tag_open = re.compile(r"<((?:header|main|footer|nav|section|dialog|form|script|style)\b|div\b[^>]*\bid=[\"']([^\"']+)[\"'])", re.I)
        tag_close = re.compile(r"</(header|main|footer|nav|section|dialog|form|script|style|div)>", re.I)
        tag_stack: list[tuple[str, str, int]] = []
        plain_divs = 0
        for idx, line in enumerate(lines, 1):
            if len(imports) < 15:
                if sm := s_pat.search(line):
                    imports.append(f'L{idx:03d} <script src="{sm.group(1)}">')
                elif lm := l_pat.search(line):
                    imports.append(f'L{idx:03d} <link href="{lm.group(1)}">')
            for m in tag_open.finditer(line):
                lbl = f'<div id="{m.group(2)}">' if m.group(2) else f"<{m.group(1).split()[0].lower()}>"
                if line.rstrip().endswith("/>"):
                    sym_items.append({"name": lbl, "kind": "element", "start_line": idx, "end_line": idx, "lines": 1, "signature": lbl, "summary": ""})
                else:
                    tag_stack.append((m.group(1).split()[0].lower(), lbl, idx))
            if re.search(r"<div\b(?!.*id=)", line, re.I) and not line.rstrip().endswith("/>"):
                plain_divs += len(re.findall(r"<div\b(?!.*id=)", line, re.I))
            for cm in tag_close.finditer(line):
                c_tag = cm.group(1).lower()
                if c_tag == "div" and plain_divs > 0:
                    plain_divs -= 1
                    continue
                for s_i in range(len(tag_stack) - 1, -1, -1):
                    if tag_stack[s_i][0] == c_tag:
                        _, lbl, s_idx = tag_stack.pop(s_i)
                        sym_items.append({"name": lbl, "kind": "element", "start_line": s_idx, "end_line": idx, "lines": idx - s_idx + 1, "signature": lbl, "summary": ""})
                        break
        while tag_stack:
            _, lbl, s_idx = tag_stack.pop()
            sym_items.append({"name": lbl, "kind": "element", "start_line": s_idx, "end_line": len(lines), "lines": len(lines) - s_idx + 1, "signature": lbl, "summary": ""})
    else:
        cur_depth = 0
        open_rules: list[tuple[int, str, int]] = []
        for idx, line in enumerate(lines, 1):
            s = line.strip()
            sc = re.sub(r"/\*.*?\*/|//.*$|([\"'])(?:\\.|[^\\])*?\1", "", s)
            if "{" in sc and (decl := s.split("{")[0].strip()):
                open_rules.append((cur_depth, decl, idx))
            cur_depth += sc.count("{") - sc.count("}")
            if "}" in sc and open_rules:
                for r_i in range(len(open_rules) - 1, -1, -1):
                    rd, rdecl, rs = open_rules[r_i]
                    if cur_depth <= rd:
                        sym_items.append({
                            "name": rdecl, "kind": "css_rule", "start_line": rs, "end_line": idx,
                            "lines": idx - rs + 1, "signature": rdecl, "summary": _leading_comment_summary(lines, rs),
                            "indent": 1 if rd > 0 else 0,
                        })
                        open_rules.pop(r_i)
    sym_items.sort(key=lambda x: x["start_line"])
    formatted = [_fmt_item_line(it, it.get("indent", 0)) for it in sym_items]
    return imports, formatted, sym_items


def outline_code(ext: str, lines: list[str]) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    if ext in (".html", ".htm", ".css", ".scss"):
        return _outline_html_css(ext, lines)

    imports: list[str] = []
    sym_items: list[dict[str, Any]] = []
    imp_pat = re.compile(r"^\s*(?:import\s+|export\s+[^=]+from\s+|const\s+[^=]+\s*=\s*require\(|use\s+|package\s+)")
    sym_pat = re.compile(
        r"^\s*(?:export\s+(?:default\s+)?)?(?:pub\s+)?(?:async\s+)?"
        r"(?:(function)\*?\s+([a-zA-Z0-9_$]+)|(class|interface|type|enum|struct|trait)\s+([a-zA-Z0-9_$]+)"
        r"|(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[a-zA-Z0-9_$]+)\s*=>"
        r"|(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*=\s*(?:async\s+)?function\b"
        r"|(func|fn)\s+(?:\([^)]+\)\s*)?([a-zA-Z0-9_]+)"
        r"|([a-zA-Z_][a-zA-Z0-9_]*)\s*\(\)\s*\{)"
    )
    cur_depth = 0
    active: list[tuple[int, str, str, str, int, bool]] = []
    for idx, line in enumerate(lines, 1):
        s = line.strip()
        if len(imports) < 15 and imp_pat.match(s):
            imports.append(f"L{idx:03d} {s[:100]}")
        if m := sym_pat.match(s):
            name = m.group(2) or m.group(4) or m.group(5) or m.group(6) or m.group(8) or m.group(9) or "symbol"
            kind = "class" if m.group(3) in ("class", "struct", "trait") else (m.group(3) or "function")
            decl = s.split("{")[0].strip().rstrip(";")
            active.append((cur_depth, name, kind, decl, idx, "{" in s))
        sc = re.sub(r"/\*.*?\*/|//.*$|([\"'`])(?:\\.|[^\\])*?\1", "", s)
        co, cc = sc.count("{"), sc.count("}")
        if active and not active[-1][5] and "{" in s:
            d, nm, kd, dec, st, _ = active.pop()
            active.append((d, nm, kd, dec, st, True))
        cur_depth += co - cc
        if active:
            for a_i in range(len(active) - 1, -1, -1):
                bd, nm, kd, bdecl, bs, has_b = active[a_i]
                if (has_b and cur_depth <= bd) or (not has_b and (";" in s or co > 0)):
                    sym_items.append({
                        "name": nm, "kind": kd, "start_line": bs, "end_line": idx,
                        "lines": idx - bs + 1, "signature": bdecl, "summary": _leading_comment_summary(lines, bs),
                    })
                    active.pop(a_i)
    sym_items.sort(key=lambda x: x["start_line"])
    formatted = [_fmt_item_line(it, 0) for it in sym_items]
    return imports, formatted, sym_items


def find_symbol_callers(symbol_name: str, ws_root: Path | None, max_refs: int = 8) -> dict[str, Any]:
    empty: dict[str, Any] = {"symbol": symbol_name, "caller_count": 0, "top_callers": []}
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]{2,64}$", symbol_name or "") or not ws_root or not Path(ws_root).is_dir():
        return empty
    root = Path(ws_root).resolve()
    has_git = any((p / ".git").exists() for p in (root, *root.parents[:4]))
    try:
        if has_git:
            cmd = ["git", "-c", "safe.directory=*", "-C", str(root), "grep", "-n", "-I", "-w", symbol_name, "--", "."]
        else:
            cmd = [
                "grep", "-rnIw",
                "--exclude-dir=.git", "--exclude-dir=node_modules", "--exclude-dir=__pycache__",
                "--exclude-dir=.venv", "--exclude-dir=venv", "--exclude-dir=dist", "--exclude-dir=build",
                "--exclude=.env*", "--exclude=*.env", "--exclude=secrets.env*",
                "--exclude=config.json*", "--exclude=mcp_config.json*",
                symbol_name, ".",
            ]
        proc = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True, timeout=1.5, check=False)
        lines = [
            ln.lstrip("./").strip()
            for ln in (proc.stdout or "").splitlines()
            if ln.strip() and not is_sensitive_filename(ln.lstrip("./").split(":", 1)[0])
        ]
        return {"symbol": symbol_name, "caller_count": len(lines), "top_callers": [ln[:140] for ln in lines[:max_refs]]}
    except Exception:
        return empty


def build_polyglot_outline(
    file_path: Path,
    full_text: str | None = None,
    ws_root: Path | None = None,
    max_chars: int = 3800,
    include_callers: bool = False,
) -> dict[str, Any]:
    if full_text is None:
        full_text = file_path.read_text(encoding="utf-8", errors="replace") if file_path.is_file() else ""
    lines = full_text.splitlines()
    total_lines = len(lines)
    ext = file_path.suffix.lower()
    lang = EXT_LANG.get(ext, ext.lstrip(".") or "text")
    imports: list[str] = []
    syntax_error: str | None = None

    if ext in (".py", ".pyi"):
        py_res = outline_python(lines, full_text, filename=file_path.name)
        summary = py_res["summary"]
        imports = py_res["imports"]
        symbols = py_res["symbols"]
        symbol_items = py_res["symbol_items"]
        syntax_error = py_res["syntax_error"]
    elif ext in (".md", ".markdown"):
        summary, symbols, symbol_items = outline_markdown(lines)
    elif ext in (".json", ".jsonc"):
        summary, symbols, symbol_items = outline_json(lines)
    elif ext in (".yaml", ".yml"):
        summary, symbols, symbol_items = outline_yaml(lines)
    else:
        imports, symbols, symbol_items = outline_code(ext, lines)
        summary = _file_top_summary(lines, lang)

    long_functions = [
        {
            "name": it["name"], "kind": it["kind"], "start_line": it["start_line"],
            "end_line": it["end_line"], "lines": it["lines"],
        }
        for it in symbol_items
        if it.get("kind") in ("function", "method") and int(it.get("lines", 0)) > LONG_FUNCTION_LINES
    ]

    shown_symbols = list(symbols)
    if sum(len(s) + 1 for s in shown_symbols) > max_chars:
        trimmed: list[str] = []
        curr = 0
        for s in shown_symbols:
            if curr + len(s) + 30 > max_chars:
                trimmed.append("... [symbols truncated]")
                break
            trimmed.append(s)
            curr += len(s) + 1
        shown_symbols = trimmed

    top_callers: dict[str, Any] = {}
    if include_callers and ws_root:
        for it in symbol_items[:5]:
            base_sym = str(it.get("name") or "").split(".")[-1]
            if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]{2,64}$", base_sym):
                top_callers[base_sym] = find_symbol_callers(base_sym, ws_root, max_refs=4)

    hdr = f"# Outline: {file_path.name} ({lang}, {total_lines} lines, {len(symbol_items)} symbols)"
    if summary:
        hdr += f"\n> {summary}"
    parts = [hdr]
    if imports:
        parts.append("## Imports\n" + "\n".join(imports))
    if shown_symbols:
        parts.append("## Symbols\n" + "\n".join(shown_symbols))
    if long_functions:
        parts.append("## Long Functions (>100L)\n" + "\n".join(
            f"- L{lf['start_line']:03d}-L{lf['end_line']:03d} ({lf['lines']}L) {lf['name']}" for lf in long_functions
        ))
    if top_callers:
        parts.append("## Symbol Callers\n" + "\n".join(
            f"- {sym}: {c.get('caller_count', 0)} callers" for sym, c in top_callers.items()
        ))

    out: dict[str, Any] = {
        "file": file_path.name,
        "language": lang,
        "summary": summary,
        "total_lines": total_lines,
        "symbol_count": len(symbol_items),
        "symbols": shown_symbols,
        "symbol_items": symbol_items,
        "long_functions": long_functions,
        "formatted_outline": "\n\n".join(parts),
    }
    if imports:
        out["imports"] = imports
    if syntax_error:
        out["syntax_error"] = syntax_error
    if include_callers and top_callers:
        out["top_callers"] = top_callers
    return out


build_file_outline = build_polyglot_outline
build_ast_outline = build_polyglot_outline
