#!/usr/bin/env python3
"""Antigravity Agents, Skills, Plugins & Rules Inventory and Scope-Isolation Engine."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

CUSTOMIZATION_SCOPE_POLICY: dict[str, Any] = {
    "policy_name": "Antigravity Customization Scope-Isolation Standard",
    "core_rule": (
        "Modifying or creating GLOBAL skills (~/.gemini/config/skills/*), GLOBAL agent roles "
        "(~/.gemini/config/agents/*), or GLOBAL rules (~/.gemini/config/GEMINI.md, ~/.gemini/config/rules/*) "
        "MUST happen in a dedicated chat session outside of feature projects (create_new_session=True, "
        "workspace_path='antigravity-config'). Inside a feature project's chat session, only activate existing "
        "global skills or edit project-specific customizations (<workspace>/.agents/* or <workspace>/GEMINI.md)."
    ),
    "allowed_in_project_session": [
        "Activate existing global/plugin/builtin skills via send_handoff_and_resume(activate_skills='...')",
        "Recommend or dispatch existing agent roles via send_handoff_and_resume(target_agent_role='...')",
        "Create or edit project-only skills, rules, or visual locks inside <workspace>/.agents/*, <workspace>/GEMINI.md, or <workspace>/.visual-lock.json",
    ],
    "requires_dedicated_non_project_session": [
        "Creating, refactoring, or updating global skills in ~/.gemini/config/skills/* (or antigravity-config)",
        "Creating or updating global subagent role definitions in ~/.gemini/config/agents/*",
        "Editing global policy directives in ~/.gemini/config/GEMINI.md or ~/.gemini/config/rules/*",
    ],
    "how_to_spawn_global_customization_session": (
        "Call send_handoff_and_resume(research_markdown='...', resume_headless=True, "
        "create_new_session=True, workspace_path='antigravity-config', customization_edit_scope='global')"
    ),
}


def parse_markdown_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Parse YAML-style frontmatter between --- delimiters and return (metadata_dict, markdown_body)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end_idx = next((i for i in range(1, min(len(lines), 60)) if lines[i].strip() == "---"), -1)
    if end_idx == -1:
        return {}, text

    meta: dict[str, Any] = {}
    list_key: str | None = None
    for line in lines[1:end_idx]:
        raw = line.rstrip()
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        if raw.lstrip().startswith("- ") and list_key and isinstance(meta.get(list_key), list):
            meta[list_key].append(raw.lstrip()[2:].strip().strip("\"'"))
        elif ":" in raw and not raw.startswith(" "):
            k, v = raw.split(":", 1)
            key, val = k.strip(), v.strip().strip("\"'")
            if not val:
                meta[key], list_key = [], key
            else:
                list_key = None
                meta[key] = (val.lower() == "true") if val.lower() in ("true", "false") else val
    return meta, "\n".join(lines[end_idx + 1 :]).strip()


def collect_agents_inventory(config_dir: Path, workspace_dir: Path | None = None) -> list[dict[str, Any]]:
    """Collect structured metadata for all global and workspace-scoped Antigravity agent definitions."""
    agents: list[dict[str, Any]] = []
    sources: list[tuple[str, Path, bool]] = []
    if (config_dir / "agents").is_dir():
        sources.append(("global", config_dir / "agents", False))
    if workspace_dir and (workspace_dir / ".agents" / "agents").is_dir():
        sources.append(("workspace", workspace_dir / ".agents" / "agents", True))

    for scope, folder, editable_in_proj in sources:
        for fpath in sorted(folder.glob("*.md")):
            try:
                meta, body = parse_markdown_frontmatter(fpath.read_text(encoding="utf-8", errors="replace"))
                desc = str(meta.get("description") or "").strip() or " ".join(
                    [l.strip() for l in body.splitlines() if l.strip() and not l.startswith("#")]
                )
                agents.append({
                    "name": str(meta.get("name") or fpath.stem),
                    "scope": scope,
                    "editable_in_project": editable_in_proj,
                    "model": str(meta.get("model") or "inherit"),
                    "target_model": str(meta.get("targetModel") or ""),
                    "difficulty": str(meta.get("difficultyLevel") or ""),
                    "tools": meta.get("tools") if isinstance(meta.get("tools"), list) else [],
                    "description": desc[:140],
                })
            except Exception:
                continue
    return agents


def collect_skills_inventory(
    config_dir: Path,
    data_dir: Path,
    workspace_dir: Path | None = None,
    scope_filter: str = "core",
) -> list[dict[str, Any]]:
    """Collect skills across workspace (.agents/skills), user global, builtin, and (when scope_filter='all' or 'plugin') installed plugins."""
    skills: list[dict[str, Any]] = []
    candidates: list[tuple[str, Path, bool]] = []
    sf = (scope_filter or "core").strip().lower()
    if workspace_dir and workspace_dir.is_dir():
        candidates.extend(("workspace", p, True) for p in sorted((workspace_dir / ".agents" / "skills").glob("*/SKILL.md")))
    if (config_dir / "skills").is_dir():
        candidates.extend(("user_global", p, False) for p in sorted((config_dir / "skills").glob("*/SKILL.md")))
    if (data_dir / "builtin" / "skills").is_dir():
        candidates.extend(("builtin", p, False) for p in sorted((data_dir / "builtin" / "skills").glob("*/SKILL.md")))
    if sf != "core" and (config_dir / "plugins").is_dir():
        candidates.extend((f"plugin:{p.parents[2].name}", p, False) for p in sorted((config_dir / "plugins").glob("*/skills/*/SKILL.md")))

    for scope, skill_md, editable_in_proj in candidates:
        if sf not in ("all", "core", "") and sf not in scope.lower():
            continue
        try:
            meta, body = parse_markdown_frontmatter(skill_md.read_text(encoding="utf-8", errors="replace"))
            skill_dir = skill_md.parent
            desc = str(meta.get("description") or "").strip() or " ".join(
                [l.strip() for l in body.splitlines() if l.strip() and not l.startswith("#")]
            )
            skills.append({
                "name": str(meta.get("name") or skill_dir.name),
                "scope": scope,
                "editable_in_project": editable_in_proj,
                "description": desc[:140],
            })
        except Exception:
            continue
    return skills[:40]


def collect_plugin_bundles_summary(config_dir: Path) -> list[dict[str, Any]]:
    """Return a compact summary of installed plugins and their skill names so the default inventory stays <10 KB."""
    bundles: list[dict[str, Any]] = []
    plugins_dir = config_dir / "plugins"
    if not plugins_dir.is_dir():
        return bundles
    for pdir in sorted(plugins_dir.iterdir()):
        if not pdir.is_dir():
            continue
        skill_names = sorted(s.parent.name for s in pdir.glob("skills/*/SKILL.md"))
        if skill_names:
            preview = skill_names[:8] + ([f"... (+{len(skill_names) - 8} more; use skill_scope_filter='plugin:{pdir.name}')"] if len(skill_names) > 8 else [])
            bundles.append({
                "plugin": pdir.name,
                "skills_count": len(skill_names),
                "skills_preview": preview,
            })
    return bundles


def collect_rules_inventory(config_dir: Path, workspace_dir: Path | None = None) -> dict[str, Any]:
    """Collect global GEMINI.md sections, global rules/*.md, and workspace-specific rules/locks."""
    global_gemini_md = config_dir / "GEMINI.md"
    global_sections = (
        [l[3:].strip() for l in global_gemini_md.read_text(encoding="utf-8", errors="replace").splitlines() if l.startswith("## ")]
        if global_gemini_md.is_file()
        else []
    )
    rules_dir = config_dir / "rules"
    global_rule_files = [
        {"name": rf.stem, "scope": "user_global", "editable_in_project_session": False, "path": str(rf)}
        for rf in (sorted(rules_dir.glob("*.md")) if rules_dir.is_dir() else [])
    ]
    ws_cust: dict[str, Any] = {
        "workspace_path": str(workspace_dir) if workspace_dir else "",
        "has_workspace_gemini_md": False,
        "workspace_gemini_sections": [],
        "workspace_rule_files": [],
        "workspace_skill_files": [],
        "workspace_agent_files": [],
        "has_visual_lock_json": False,
    }
    if workspace_dir and workspace_dir.is_dir():
        ws_gemini = workspace_dir / "GEMINI.md"
        if ws_gemini.is_file():
            ws_cust["has_workspace_gemini_md"] = True
            ws_cust["workspace_gemini_sections"] = [
                l[3:].strip() for l in ws_gemini.read_text(encoding="utf-8", errors="replace").splitlines() if l.startswith("## ")
            ]
        ws_cust["workspace_rule_files"] = [
            str(p) for g in (".agents/rules/*.md", ".gemini/rules/*.md") for p in sorted(workspace_dir.glob(g))
        ]
        ws_cust["workspace_skill_files"] = [str(p) for p in sorted(workspace_dir.glob(".agents/skills/*/SKILL.md"))]
        ws_cust["workspace_agent_files"] = [str(p) for p in sorted(workspace_dir.glob(".agents/agents/*.md"))]
        ws_cust["has_visual_lock_json"] = (workspace_dir / ".visual-lock.json").is_file()
    return {
        "global_gemini_md_path": str(global_gemini_md) if global_gemini_md.is_file() else "",
        "global_gemini_sections": global_sections,
        "global_rule_files": global_rule_files,
        "workspace_customizations": ws_cust,
    }


def evaluate_session_customization_scope(workspace_str: str, config_dir: Path, gitlab_dir: Path) -> dict[str, Any]:
    """Evaluate whether the currently selected session/workspace is suitable for editing global skills/rules/agents."""
    ws_clean = (workspace_str or "").strip()
    ws_path = Path(ws_clean).resolve() if ws_clean and Path(ws_clean).exists() else None
    ag_cfg_repo = (gitlab_dir / "antigravity-config").resolve()
    is_global = bool(ws_path and (ws_path in (ag_cfg_repo, config_dir.resolve()) or ws_path.name == "antigravity-config"))
    proj_label = ws_path.name if ws_path else (ws_clean or "antigravity-config")
    return {
        "current_workspace": ws_clean or str(ag_cfg_repo),
        "is_global_config_session": is_global,
        "can_edit_global_skills_and_rules_here": is_global,
        "can_edit_project_local_customizations_here": True,
        "guidance": (
            "Current session is bound to 'antigravity-config' (outside feature projects); safe to modify global skills, agent roles, and global rules."
            if is_global
            else (
                f"Current session is bound to project '{proj_label}'. Keep this project session clean: ONLY edit "
                "project-specific rules/skills under '<workspace>/.agents/*' here, or activate existing global skills via activate_skills. "
                "To create or modify GLOBAL skills, agent roles, or global GEMINI.md rules, use a dedicated chat session outside this project "
                "(create_new_session=True, workspace_path='antigravity-config')."
            )
        ),
    }


def resolve_customization_file(query: str, config_dir: Path, data_dir: Path, workspace_dir: Path | None = None) -> Path | None:
    """Resolve shorthand ('skill:agy-nexus-stats', 'agent:argon-sentinel', 'rule:GEMINI.md', or name) to a Path."""
    q = (query or "").strip()
    if not q:
        return None
    prefix = ""
    if ":" in q and not q.startswith("/"):
        p_cand, rest = q.split(":", 1)
        if p_cand.lower() in ("skill", "skills", "agent", "agents", "rule", "rules"):
            prefix, q = p_cand.lower().rstrip("s"), rest.strip()

    q_slug = q.lower().removesuffix(".md").strip("/")
    if q.lower() in ("gemini.md", "global:gemini.md") or (prefix == "rule" and q_slug == "gemini"):
        if workspace_dir and q.lower() == "workspace:gemini.md" and (workspace_dir / "GEMINI.md").is_file():
            return (workspace_dir / "GEMINI.md").resolve()
        return (config_dir / "GEMINI.md").resolve() if (config_dir / "GEMINI.md").is_file() else None

    if prefix in ("", "agent"):
        for folder in (([workspace_dir / ".agents" / "agents"] if workspace_dir else []) + [config_dir / "agents"]):
            if (folder / f"{q_slug}.md").is_file():
                return (folder / f"{q_slug}.md").resolve()
    if prefix in ("", "skill"):
        for sroot in (([workspace_dir / ".agents" / "skills"] if workspace_dir else []) + [config_dir / "skills", data_dir / "builtin" / "skills"]):
            if (sroot / q_slug / "SKILL.md").is_file():
                return (sroot / q_slug / "SKILL.md").resolve()
        if (config_dir / "plugins").is_dir():
            for p_cand in (config_dir / "plugins").glob(f"*/skills/{q_slug}/SKILL.md"):
                if p_cand.is_file():
                    return p_cand.resolve()
    if prefix in ("", "rule"):
        for rfolder in (([workspace_dir / ".agents" / "rules", workspace_dir / ".gemini" / "rules"] if workspace_dir else []) + [config_dir / "rules"]):
            if (rfolder / f"{q_slug}.md").is_file():
                return (rfolder / f"{q_slug}.md").resolve()
    return None


def build_interjection_directive(
    activate_skills: str,
    target_agent_role: str,
    customization_edit_scope: str,
    research_markdown: str,
    workspace_str: str,
    config_dir: Path,
    data_dir: Path,
    gitlab_dir: Path,
) -> tuple[str, dict[str, Any]]:
    """Build markdown interjection directives for activated skills/agents and enforce scope isolation."""
    ws_path = Path(workspace_str).resolve() if workspace_str and Path(workspace_str).exists() else None
    scope_eval = evaluate_session_customization_scope(workspace_str, config_dir, gitlab_dir)
    edit_scope = (customization_edit_scope or "none").strip().lower()

    resolved_skills = [
        {"name": s.strip(), "path": str(p) if (p := resolve_customization_file(f"skill:{s.strip()}", config_dir, data_dir, ws_path)) else f"(unresolved: {s.strip()})"}
        for s in re.split(r"[,;\n]+", activate_skills or "") if s.strip()
    ]
    ag_clean = target_agent_role.strip()
    ag_path = resolve_customization_file(f"agent:{ag_clean}", config_dir, data_dir, ws_path) if ag_clean else None
    resolved_agent = str(ag_path) if ag_path else ag_clean

    touches_global = bool(re.search(r"(\.gemini/config/(skills|agents|rules|GEMINI\.md)|antigravity-config/\.gemini/config)", research_markdown))
    scope_warning = (
        f"SCOPE-ISOLATION WARNING: Modifying global skills, agent roles, or global rules (~/.gemini/config/*) should NOT happen inside project session '{scope_eval['current_workspace']}'. Use a dedicated session outside this project (create_new_session=True, workspace_path='antigravity-config') unless the change is strictly project-local (<workspace>/.agents/*)."
        if (edit_scope == "global" or touches_global) and not scope_eval["is_global_config_session"]
        else ""
    )
    sections: list[str] = []
    if resolved_skills or resolved_agent or edit_scope in ("project", "global") or scope_warning:
        sections.append("\n---\n\n## Antigravity Skill, Agent Role & Customization Scope Directive\n")
        if resolved_skills:
            sections.append("### Mandatory Activated Skills (Read Before Executing)")
            sections.extend(f"- **`{sk['name']}`**: Read `{sk['path']}` via `view_file` and follow its instructions." for sk in resolved_skills)
        if resolved_agent:
            sections.append(f"\n### Recommended Agent Role Dispatch\n- **Primary Role**: `{ag_clean}` (`{resolved_agent}`)")
        if scope_warning:
            sections.append(f"\n> [!WARNING]\n> **{scope_warning}**\n> Do NOT modify `~/.gemini/config/*` global files inside this feature project workspace. Keep any rule/skill creation strictly inside `<workspace>/.agents/` or defer global changes to an `antigravity-config` session.")
        elif edit_scope == "project":
            sections.append("\n- **Customization Scope (`project`)**: Place any new or updated project-specific rules/skills strictly inside `<workspace>/.agents/rules/` or `<workspace>/.agents/skills/` so global configurations remain untouched.")
    return ("\n".join(sections) + "\n" if sections else ""), {
        "activated_skills": resolved_skills,
        "target_agent_role": ag_clean,
        "customization_edit_scope": edit_scope,
        "is_global_config_session": scope_eval["is_global_config_session"],
        "scope_isolation_warning": scope_warning,
    }
