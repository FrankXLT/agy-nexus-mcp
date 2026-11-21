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
from agy_nexus.polyglot_lang_outliners import (
    _clean_jsonc,
    _clean_one_liner,
    _file_top_summary,
    _fmt_item_line,
    _json_val_desc,
    _leading_comment_summary,
    _outline_html_css,
    outline_json,
    outline_markdown,
    outline_yaml,
)

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
