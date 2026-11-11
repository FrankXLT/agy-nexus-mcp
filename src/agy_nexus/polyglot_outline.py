#!/usr/bin/env python3
"""agy_nexus.polyglot_outline — Polyglot structural line-span outliner for Markdown, JSON, YAML, and Code."""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

EXT_LANG = {
    ".md": "markdown", ".markdown": "markdown", ".json": "json", ".jsonc": "jsonc",
    ".yaml": "yaml", ".yml": "yaml", ".css": "css", ".scss": "scss", ".html": "html",
    ".htm": "html", ".py": "python", ".vue": "vue",
    **{e: "javascript" for e in (".js", ".mjs", ".cjs", ".jsx")},
    **{e: "typescript" for e in (".ts", ".tsx")},
}

def outline_markdown(lines: list[str]) -> list[str]:
    items, fence_char, fence_start, fence_lang, n = [], None, 0, "", len(lines)
    for i, raw in enumerate(lines, 1):
        s = raw.strip()
        if s.startswith("```") or s.startswith("~~~"):
            if fence_char is None:
                fence_char, fence_start = s[:3], i
                fence_lang = s[3:].strip().split()[0].lower() if s[3:].strip() else ""
            elif fence_char == s[:3]:
                items.append({"type": "c", "start": fence_start, "end": i, "lang": fence_lang})
                fence_char = None
        elif fence_char is None and (m := re.match(r"^(#{1,6})\s+(.*)$", s)):
            items.append({"type": "h", "start": i, "end": n, "lvl": len(m.group(1)), "t": m.group(2).strip()})
    if fence_char is not None: items.append({"type": "c", "start": fence_start, "end": n, "lang": fence_lang})

    headings = [it for it in items if it["type"] == "h"]
    for idx, h in enumerate(headings):
        for nxt in headings[idx + 1:]:
            if nxt["lvl"] <= h["lvl"]:
                h["end"] = max(h["start"], nxt["start"] - 1); break

    out = []
    for it in items:
        sp = f"L{it['start']:03d}-L{it['end']:03d}"
        if it["type"] == "h": out.append(f"{'  ' * (it['lvl'] - 1)}{sp} {'#' * it['lvl']} {it['t']}")
        else: out.append(f"{sp} [code:{it['lang']}]" if it["lang"] else f"{sp} [code]")
    return out

def _clean_jsonc(text: str) -> str:
    out, i, n, in_s, q_c = [], 0, len(text), False, ""
    while i < n:
        c = text[i]
        if in_s:
            out.append(c)
            if c == "\\" and i + 1 < n: i += 1; out.append(text[i])
            elif c == q_c: in_s = False
        elif text[i:i+2] == "/*":
            end = text.find("*/", i + 2); out.append("\n" * text[i:end+2].count("\n")) if end != -1 else None
            if end == -1: break
            i = end + 1
        elif text[i:i+2] == "//":
            end = text.find("\n", i + 2)
            if end == -1: break
            i = end - 1
        elif c in ('"', "'"): in_s, q_c = True, c; out.append(c)
        else: out.append(c)
        i += 1
    return re.sub(r",\s*([\]}])", r"\1", "".join(out))

def _json_val_desc(val: Any) -> str:
    if isinstance(val, bool): return "bool"
    if isinstance(val, (int, float, str)): return type(val).__name__
    if isinstance(val, dict): return f"dict[{len(val)} keys]"
    if isinstance(val, list):
        if val and isinstance(val[0], dict):
            return f"list[{len(val)} items] of {{{', '.join(list(val[0].keys())[:5])}}}"
        return f"list[{len(val)} items]"
    return "null" if val is None else type(val).__name__

def outline_json(lines: list[str]) -> list[str]:
    try: parsed: Any = json.loads(_clean_jsonc("\n".join(lines)))
    except Exception: parsed = None
    keys, stack = [], []
    in_s, q_c, in_b, cur_top, pending_owner = False, "", False, "", None

    for l_idx, line in enumerate(lines, 1):
        i, n = 0, len(line)
        while i < n:
            ch = line[i]
            if in_b:
                if line[i:i+2] == "*/": in_b = False; i += 1
            elif in_s:
                if ch == "\\" and i + 1 < n: i += 1
                elif ch == q_c: in_s = False
            elif line[i:i+2] == "/*": in_b, i = True, i + 1
            elif line[i:i+2] == "//": break
            elif ch in ('"', "'"):
                depth, eq = len(stack), i + 1
                while eq < n:
                    if line[eq] == "\\" and eq + 1 < n: eq += 2; continue
                    if line[eq] == ch: break
                    eq += 1
                if eq < n and line[eq] == ch:
                    j = eq + 1
                    while j < n and line[j] in " \t": j += 1
                    if j < n and line[j] == ":":
                        k_name, k_idx, st = line[i+1:eq], len(keys), [s[0] for s in stack]
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
                        else: in_s, q_c = True, ch
                    else: in_s, q_c = True, ch
                else: in_s, q_c = True, ch
            elif ch in ("{", "["):
                stack.append((ch, pending_owner)); pending_owner = None
            elif ch in ("}", "]") and stack:
                _, owner = stack.pop()
                if owner is not None and owner < len(keys): keys[owner]["end"] = l_idx
            i += 1
    return [f"{'  ' if k['lvl'] == 2 else ''}L{k['start']:03d}-L{k['end']:03d} \"{k['name']}\"{': ' + k['desc'] if k['desc'] else ''}" for k in keys]

def outline_yaml(lines: list[str]) -> list[str]:
    entries, n, cur_child_ind = [], len(lines), 2
    for idx, raw in enumerate(lines, 1):
        s = raw.strip()
        if not s or s.startswith("#"): continue
        ind = len(raw) - len(raw.lstrip(" "))
        if ind == 0 and (m := re.match(r"^([a-zA-Z0-9_-]+):\s*(.*)$", s)):
            k, v = m.group(1), m.group(2).strip()
            entries.append({"lvl": 1, "ind": 0, "start": idx, "end": idx, "lbl": f"{k}: {v}" if v else f"{k}:"})
            cur_child_ind = 0
        elif ind > 0:
            if cur_child_ind == 0: cur_child_ind = ind
            m_seq, m_key = re.match(r"^-\s+(alias|id|name|service|platform|action):\s*(.*)$", s), re.match(r"^([a-zA-Z0-9_-]+):\s*(.*)$", s)
            if ind == cur_child_ind and m_seq:
                tag, val = m_seq.group(1), m_seq.group(2).strip()
                extra = f" (alias: {m_nxt.group(1)})" if tag == "id" and idx < n and (m_nxt := re.match(r"^(?:alias|name):\s*['\"]?([^'\"]+)['\"]?", lines[idx].strip())) else ""
                entries.append({"lvl": 2, "ind": ind, "start": idx, "end": idx, "lbl": f"- {tag}: {val}{extra}"})
            elif ind == cur_child_ind and m_key:
                k, v = m_key.group(1), m_key.group(2).strip()
                entries.append({"lvl": 2, "ind": ind, "start": idx, "end": idx, "lbl": f"{k}: {v}" if v else f"{k}:"})

    for i, e in enumerate(entries):
        end = n
        for nxt in entries[i + 1:]:
            if nxt["ind"] <= e["ind"]: end = nxt["start"] - 1; break
        while end > e["start"] and not lines[end - 1].strip(): end -= 1
        e["end"] = max(e["start"], end)
    return [f"{'  ' if e['lvl'] == 2 else ''}L{e['start']:03d}-L{e['end']:03d} {e['lbl']}" for e in entries]

def outline_code(ext: str, lines: list[str]) -> tuple[list[str], list[str]]:
    imports, symbols = [], []
    if ext in (".html", ".htm"):
        s_pat, l_pat = re.compile(r"<script[^>]+src=[\"']([^\"']+)[\"']"), re.compile(r"<link[^>]+(?:href=[\"']([^\"']+)[\"']|rel=[\"']stylesheet[\"'])")
        tag_open, tag_close = re.compile(r"<((?:header|main|footer|nav|section|form|script|style)\b|div\b[^>]*\bid=[\"']([^\"']+)[\"'])", re.I), re.compile(r"</(header|main|footer|nav|section|form|script|style|div)>", re.I)
        tag_stack, plain_divs = [], 0
        for idx, line in enumerate(lines, 1):
            if len(imports) < 15:
                if (sm := s_pat.search(line)): imports.append(f"L{idx:03d} <script src=\"{sm.group(1)}\">")
                elif (lm := l_pat.search(line)) and lm.group(1): imports.append(f"L{idx:03d} <link href=\"{lm.group(1)}\">")
            for m in tag_open.finditer(line):
                lbl = f"<div id=\"{m.group(2)}\">" if m.group(2) else f"<{m.group(1).split()[0].lower()}>"
                if line.rstrip().endswith("/>"): symbols.append(f"L{idx:03d}-L{idx:03d} {lbl}")
                else: tag_stack.append((m.group(1).split()[0].lower(), lbl, idx))
            if re.search(r"<div\b(?!.*id=)", line, re.I) and not line.rstrip().endswith("/>"): plain_divs += len(re.findall(r"<div\b(?!.*id=)", line, re.I))
            for cm in tag_close.finditer(line):
                c_tag = cm.group(1).lower()
                if c_tag == "div" and plain_divs > 0: plain_divs -= 1; continue
                for s_i in range(len(tag_stack) - 1, -1, -1):
                    if tag_stack[s_i][0] == c_tag:
                        _, lbl, s_idx = tag_stack.pop(s_i); symbols.append(f"L{s_idx:03d}-L{idx:03d} {lbl}"); break
        while tag_stack:
            _, lbl, s_idx = tag_stack.pop(); symbols.append(f"L{s_idx:03d}-L{len(lines):03d} {lbl}")
    elif ext in (".css", ".scss"):
        cur_depth, open_rules = 0, []
        for idx, line in enumerate(lines, 1):
            s = line.strip()
            sc = re.sub(r"/\*.*?\*/|//.*$|([\"'])(?:\\.|[^\\])*?\1", "", s)
            if "{" in sc and (decl := s.split("{")[0].strip()): open_rules.append((cur_depth, decl, idx))
            cur_depth += sc.count("{") - sc.count("}")
            if "}" in sc and open_rules:
                for r_i in range(len(open_rules) - 1, -1, -1):
                    rd, rdecl, rs = open_rules[r_i]
                    if cur_depth <= rd:
                        symbols.append(f"{'  ' if rd > 0 else ''}L{rs:03d}-L{idx:03d} {rdecl}"); open_rules.pop(r_i)
    else:
        imp_pat = re.compile(r"^\s*(?:import\s+|export\s+[^=]+from\s+|const\s+[^=]+\s*=\s*require\()")
        sym_pat = re.compile(r"^\s*(?:export\s+(?:default\s+)?)?(?:async\s+)?(?:function\*?\s+[a-zA-Z0-9_$]+|class\s+[a-zA-Z0-9_$]+|(?:const|let|var)\s+[a-zA-Z0-9_$]+\s*=\s*(?:async\s*)?(?:\([^)]*\)|[a-zA-Z0-9_$]+)\s*=>|(?:const|let|var)\s+[a-zA-Z0-9_$]+\s*=\s*(?:async\s+)?function\b)")
        cur_depth, active_syms = 0, []
        for idx, line in enumerate(lines, 1):
            s = line.strip()
            if len(imports) < 15 and imp_pat.match(s): imports.append(f"L{idx:03d} {s[:100]}")
            if sym_pat.match(s): active_syms.append((cur_depth, s.split("{")[0].strip(), idx, "{" in s))
            sc = re.sub(r"/\*.*?\*/|//.*$|([\"'`])(?:\\.|[^\\])*?\1", "", s)
            co, cc = sc.count("{"), sc.count("}")
            if active_syms and not active_syms[-1][3] and "{" in s:
                d, dec, st, _ = active_syms.pop(); active_syms.append((d, dec, st, True))
            cur_depth += co - cc
            if active_syms:
                for a_i in range(len(active_syms) - 1, -1, -1):
                    bd, bdecl, bs, has_b = active_syms[a_i]
                    if (has_b and cur_depth <= bd) or (not has_b and (";" in s or co > 0)):
                        symbols.append(f"L{bs:03d}-L{idx:03d} {bdecl}"); active_syms.pop(a_i)
    return imports, sorted(symbols, key=lambda s: int(m.group(1)) if (m := re.search(r"L(\d+)", s)) else 0)

def build_polyglot_outline(
    file_path: Path, full_text: str | None = None, max_chars: int = 3800
) -> dict[str, Any]:
    if full_text is None:
        full_text = file_path.read_text(encoding="utf-8", errors="replace") if file_path.is_file() else ""
    lines, total_lines = full_text.splitlines(), len(full_text.splitlines())
    ext, lang = file_path.suffix.lower(), EXT_LANG.get(file_path.suffix.lower(), file_path.suffix.lower().lstrip("."))
    imports: list[str] = []

    if ext in (".md", ".markdown"): symbols = outline_markdown(lines)
    elif ext in (".json", ".jsonc"): symbols = outline_json(lines)
    elif ext in (".yaml", ".yml"): symbols = outline_yaml(lines)
    elif ext == ".py":
        try:
            from agy_nexus.ast_outline import build_file_outline
            res = build_file_outline(file_path, full_text=full_text, max_chars=max_chars)
            return {"file": file_path.name, "language": "python", "total_lines": total_lines,
                "symbol_count": res.get("symbol_count", len(res.get("symbols", []))),
                "symbols": res.get("symbols", []), "imports": res.get("imports", []),
                "formatted_outline": res.get("formatted_outline", "")}
        except Exception: imports, symbols = outline_code(ext, lines)
    else: imports, symbols = outline_code(ext, lines)

    if sum(len(s) + 1 for s in symbols) > max_chars:
        trimmed, curr = [], 0
        for s in symbols:
            if curr + len(s) + 30 > max_chars: trimmed.append("... [symbols truncated]"); break
            trimmed.append(s); curr += len(s) + 1
        symbols = trimmed

    parts = [f"# Outline: {file_path.name} ({lang}, {total_lines} lines, {len(symbols)} symbols)"]
    if imports: parts.append("## Imports\n" + "\n".join(imports))
    if symbols: parts.append("## Symbols\n" + "\n".join(symbols))

    return {
        "file": file_path.name, "language": lang, "total_lines": total_lines,
        "symbol_count": len(symbols), "symbols": symbols, "imports": imports,
        "formatted_outline": "\n\n".join(parts),
    }
