#!/usr/bin/env python3
"""agy_nexus.ast_outline — Fast AST Symbol Outliner, Scope Undefined-Name Verifier & Caller Finder."""
from __future__ import annotations

import ast
import builtins
from pathlib import Path
import re
import subprocess
from typing import Any

PYTHON_BUILTINS = set(dir(builtins)) | {
    "__file__", "__name__", "__doc__", "__package__", "__all__",
    "__annotations__", "__spec__", "__loader__", "__cached__", "__path__",
    "WindowsError", "EnvironmentError", "IOError",
}

def _collect_scope_bindings(node: ast.AST) -> set[str]:
    names: set[str] = set()
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        names.update(a.arg for a in (node.args.posonlyargs + node.args.args + node.args.kwonlyargs))
        if node.args.vararg: names.add(node.args.vararg.arg)
        if node.args.kwarg: names.add(node.args.kwarg.arg)
    elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
        names.update(n.id for gen in node.generators for n in ast.walk(gen.target) if isinstance(n, ast.Name))
        names.update(n.target.id for n in ast.walk(node) if isinstance(n, ast.NamedExpr) and isinstance(n.target, ast.Name))
        return names

    body_nodes = getattr(node, "body", [])
    body_nodes = body_nodes if isinstance(body_nodes, list) else ([body_nodes] if body_nodes else [])

    def _walk_local(cur: ast.AST) -> None:
        if cur is not node and isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(cur.name); return
        if cur is not node and isinstance(cur, (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            names.update(n.target.id for n in ast.walk(cur) if isinstance(n, ast.NamedExpr) and isinstance(n.target, ast.Name))
            return
        if isinstance(cur, (ast.Import, ast.ImportFrom)):
            names.update((a.asname or (a.name if isinstance(cur, ast.ImportFrom) else a.name.split(".")[0])) for a in cur.names)
        elif isinstance(cur, ast.Name) and isinstance(cur.ctx, ast.Store):
            names.add(cur.id)
        elif isinstance(cur, ast.ExceptHandler) and cur.name:
            names.add(cur.name)
        elif hasattr(ast, "MatchAs") and isinstance(cur, (ast.MatchAs, ast.MatchStar)) and cur.name:
            names.add(cur.name)
        elif hasattr(ast, "TypeAlias") and isinstance(cur, ast.TypeAlias) and isinstance(cur.name, ast.Name):
            names.add(cur.name.id)
        elif isinstance(cur, ast.NamedExpr) and isinstance(cur.target, ast.Name):
            names.add(cur.target.id)
        for child in ast.iter_child_nodes(cur):
            _walk_local(child)

    for b in body_nodes: _walk_local(b)
    return names

def check_python_undefined_names(source_text: str, file_label: str = "") -> list[str]:
    try:
        tree = ast.parse(source_text, filename=file_label or "<string>")
    except Exception:
        return []
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and any(a.name == "*" for a in n.names):
            return []

    module_bindings = _collect_scope_bindings(tree) | {name for n in ast.walk(tree) if isinstance(n, ast.Global) for name in n.names}
    undefined: set[tuple[int, str]] = set()

    def _check_scope(scope_node: ast.AST, enclosing: set[str]) -> None:
        local_b = _collect_scope_bindings(scope_node)
        visible = enclosing | local_b | module_bindings | PYTHON_BUILTINS

        def _scan(node: ast.AST, cur_vis: set[str] | None = None) -> None:
            active_vis = cur_vis if cur_vis is not None else visible
            if node is not scope_node:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    for dec in node.decorator_list: _scan(dec, active_vis)
                    if isinstance(node, ast.ClassDef):
                        for b in (node.bases + [kw.value for kw in node.keywords]): _scan(b, active_vis)
                    else:
                        for d in (node.args.defaults + [kd for kd in node.args.kw_defaults if kd]): _scan(d, active_vis)
                    _check_scope(node, (enclosing | {scope_node.name}) if isinstance(scope_node, ast.ClassDef) else active_vis)
                    return
                elif isinstance(node, ast.Lambda):
                    for d in (node.args.defaults + [kd for kd in node.args.kw_defaults if kd]): _scan(d, active_vis)
                    _check_scope(node, active_vis); return
                elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                    comp_vis = set(active_vis)
                    for gen in node.generators:
                        _scan(gen.iter, comp_vis)
                        comp_vis.update(tn.id for tn in ast.walk(gen.target) if isinstance(tn, ast.Name))
                        for if_expr in gen.ifs: _scan(if_expr, comp_vis)
                    comp_vis.update(n.target.id for n in ast.walk(node) if isinstance(n, ast.NamedExpr) and isinstance(n.target, ast.Name))
                    if isinstance(node, ast.DictComp):
                        _scan(node.key, comp_vis); _scan(node.value, comp_vis)
                    else:
                        _scan(node.elt, comp_vis)
                    return

            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                if node.id not in active_vis: undefined.add((node.lineno, node.id))

            for field, value in ast.iter_fields(node):
                if field in ("annotation", "returns"): continue
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, ast.AST): _scan(item, active_vis)
                elif isinstance(value, ast.AST):
                    _scan(value, active_vis)

        _scan(scope_node, visible)

    _check_scope(tree, set())
    return [f"L{line}: {name}" for line, name in sorted(undefined, key=lambda x: (x[0], x[1]))]

def scan_package_undefined_names(pkg_dir: Path) -> dict[str, list[str]]:
    results: dict[str, list[str]] = {}
    if not pkg_dir.is_dir(): return results
    for py_file in sorted(pkg_dir.glob("*.py")):
        try:
            undefs = check_python_undefined_names(py_file.read_text(encoding="utf-8", errors="replace"), py_file.name)
            if undefs: results[py_file.name] = undefs
        except Exception: pass
    return results

def find_symbol_callers(symbol_name: str, ws_root: Path | None, max_refs: int = 8) -> dict[str, Any]:
    empty: dict[str, Any] = {"symbol": symbol_name, "caller_count": 0, "top_callers": []}
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]{2,64}$", symbol_name or "") or not ws_root or not Path(ws_root).is_dir():
        return empty
    try:
        proc = subprocess.run(["git", "-C", str(ws_root), "grep", "-n", "-I", "-w", symbol_name], capture_output=True, text=True, timeout=4, check=False)
        lines = [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]
        return {"symbol": symbol_name, "caller_count": len(lines), "top_callers": [line[:140] for line in lines[:max_refs]]}
    except Exception:
        return empty

def _fmt_func(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    pfx = "async def " if isinstance(node, ast.AsyncFunctionDef) else "def "
    args = [a.arg for a in (node.args.posonlyargs + node.args.args + node.args.kwonlyargs)]
    if node.args.vararg: args.append(f"*{node.args.vararg.arg}")
    if node.args.kwarg: args.append(f"**{node.args.kwarg.arg}")
    ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    return f"{pfx}{node.name}({', '.join(args)}){ret}"

def build_file_outline(
    file_path: Path, full_text: str | None = None, ws_root: Path | None = None,
    max_chars: int = 1400, include_callers: bool = False
) -> dict[str, Any]:
    if full_text is None:
        full_text = file_path.read_text(encoding="utf-8", errors="replace") if file_path.is_file() else ""
    lines, total_lines = full_text.splitlines(), len(full_text.splitlines())
    ext = file_path.suffix.lower()
    symbols, imports, undefined_names, top_callers = [], [], [], {}
    lang = "python" if ext == ".py" else ("javascript" if ext in (".js", ".mjs", ".cjs", ".jsx") else ("typescript" if ext in (".ts", ".tsx") else ext.lstrip(".")))

    if ext != ".py":
        from agy_nexus.polyglot_outline import build_polyglot_outline
        return build_polyglot_outline(file_path, full_text=full_text, max_chars=max_chars)

    try:
        tree = ast.parse(full_text, filename=file_path.name)
        for n in tree.body:
            if isinstance(n, (ast.Import, ast.ImportFrom)) and len(imports) < 15:
                imports.append(f"L{n.lineno:03d} {lines[n.lineno - 1].strip() if n.lineno <= len(lines) else ''}")
            elif isinstance(n, ast.ClassDef):
                span = f"L{n.lineno:03d}-L{getattr(n, 'end_lineno', n.lineno):03d}"
                bases = f"({', '.join(ast.unparse(b) for b in n.bases)})" if n.bases else ""
                symbols.append(f"{span} class {n.name}{bases}:")
                for m in n.body:
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        symbols.append(f"  L{m.lineno:03d}-L{getattr(m, 'end_lineno', m.lineno):03d} {_fmt_func(m)}")
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.append(f"L{n.lineno:03d}-L{getattr(n, 'end_lineno', n.lineno):03d} {_fmt_func(n)}")
        undefined_names = check_python_undefined_names(full_text, file_path.name)
    except Exception: pass

    if sum(len(s) + 1 for s in symbols) > max_chars:
        trimmed, curr = [], 0
        for s in symbols:
            if curr + len(s) + 30 > max_chars:
                trimmed.append("... [symbols truncated]"); break
            trimmed.append(s); curr += len(s) + 1
        symbols = trimmed

    if include_callers and ws_root:
        for s in symbols[:5]:
            m_name = re.search(r"\b(?:class|def)\s+([a-zA-Z_][a-zA-Z0-9_]+)", s)
            if m_name: top_callers[m_name.group(1)] = find_symbol_callers(m_name.group(1), ws_root, max_refs=4)

    parts = [f"# Outline: {file_path.name} ({lang}, {total_lines} lines, {len(symbols)} symbols)"]
    if imports: parts.append("## Imports\n" + "\n".join(imports))
    if symbols: parts.append("## Symbols\n" + "\n".join(symbols))
    if undefined_names: parts.append("## Undefined Names (Potential Bugs)\n" + "\n".join(undefined_names))
    if top_callers:
        parts.append("## Symbol Callers\n" + "\n".join(f"- {sym}: {c.get('caller_count', 0)} callers" for sym, c in top_callers.items()))

    out: dict[str, Any] = {
        "file": file_path.name, "language": lang, "total_lines": total_lines,
        "symbol_count": len(symbols), "symbols": symbols, "formatted_outline": "\n\n".join(parts),
    }
    if imports: out["imports"] = imports
    if ext == ".py": out["undefined_names"] = undefined_names
    if include_callers and top_callers: out["top_callers"] = top_callers
    return out

build_ast_outline = build_file_outline
