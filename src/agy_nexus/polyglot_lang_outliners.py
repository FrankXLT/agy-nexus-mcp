#!/usr/bin/env python3
"""agy_nexus.polyglot_lang_outliners — Markup, Config, and Comment-Summary Outliners.

Extracts exact Lstart-Lend spans and 1-liner summaries for Markdown, JSON/JSONC,
YAML, HTML, and CSS/SCSS alongside shared leading-comment extractors.
"""
from __future__ import annotations

import json
import re
from typing import Any


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


def outline_markdown(lines: list[str]) -> tuple[str, list[str], list[dict[str, Any]]]:
    """Extract Markdown heading hierarchy and fenced code block spans."""
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
    """Extract top/second-level JSON and JSONC keys with line spans and type descriptors."""
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
    """Extract YAML key spans with automatic scalar secret redaction."""
    entries: list[dict[str, Any]] = []
    n, cur_child_ind, sens_parent = len(lines), 2, False
    sec_re = re.compile(r"secret|token|password|passwd|api_key|apikey|private_key|bearer|ghp_|gho_|github_pat_|sk-|akia|aiza|eyj[a-z0-9_-]{8,}|://[^:\s]+:[^@\s]+@", re.I)
    sec_key_re = re.compile(r"secret|token|password|passwd|api_?key|private_?key|credential|auth", re.I)
    for idx, raw in enumerate(lines, 1):
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        ind = len(raw) - len(raw.lstrip(" "))
        if ind == 0 and (m := re.match(r"^([a-zA-Z0-9_.-]+):\s*(.*)$", s)):
            k = m.group(1)
            sens_parent = bool(sec_key_re.search(k))
            entries.append({"lvl": 1, "ind": 0, "start": idx, "end": idx, "name": k, "lbl": f"{k}:", "summary": _leading_comment_summary(lines, idx)})
            cur_child_ind = 0
        elif ind > 0:
            if cur_child_ind == 0:
                cur_child_ind = ind
            m_seq = re.match(r"^-\s+(alias|id|name|service|platform|action):\s*(.*)$", s)
            m_key = re.match(r"^([a-zA-Z0-9_.-]+):\s*(.*)$", s)
            if ind == cur_child_ind and m_seq:
                tag, val = m_seq.group(1), m_seq.group(2).strip()
                safe_v = "[REDACTED]" if (sens_parent or sec_re.search(val)) else val[:64]
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
    """Extract HTML landmark/id elements and CSS/SCSS rule spans."""
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
