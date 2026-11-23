#!/usr/bin/env python3
"""agy_nexus.workflow_baseline — Project Workflow Discovery, Quality Linting & Intent Retention.

Parses Common Terms glossaries and numbered WF-01..WF-NN flows (`docs/WORKFLOWS.md`),
formats full structured wire indexes (< 20 KB ceiling), evaluates plain-language handoff quality,
and extracts user goals/workflows for baton continuity across session rollovers.
"""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any

WORKFLOW_DOC_CANDIDATES = (
    "docs/WORKFLOWS.md",
    "docs/workflows.md",
    "WORKFLOWS.md",
    "docs/USE_CASES.md",
    "docs/use_cases.md",
    "SPEC.md",
    "spec.md",
)

PRIMARY_WORKFLOW_FILES = {"docs/WORKFLOWS.md", "docs/workflows.md", "WORKFLOWS.md"}

_TERM_RE = re.compile(r"^\s*[-*]\s+\*{0,2}([^:*—\n]+?)\*{0,2}\s*(?::|—|--)\s*(.+)$")
_WF_HEADING_RE = re.compile(
    r"^(#{2,3})\s+(?:Workflow\s+(\d+)\s*:\s*)?(WF-\d+)?(?:\s*[—:-]\s*)?(.*)$",
    re.IGNORECASE,
)
_WF_ANY_TAG_RE = re.compile(r"\bWF[-_ ]?(\d{1,2})\b", re.IGNORECASE)


def _clean_md_inline(text: str) -> str:
    return re.sub(r"[*_]+", "", (text or "")).strip()


def _parse_common_terms(text: str) -> list[dict[str, str]]:
    """Extract term->meaning pairs from Common Terms sections."""
    lines = text.splitlines()
    terms: list[dict[str, str]] = []
    in_section = False
    for line in lines:
        s = line.strip()
        if re.match(r"^#{2,3}\s+.*Common\s+Terms\b", s, re.IGNORECASE):
            in_section = True
            continue
        if in_section and (s.startswith("## ") or s == "---"):
            break
        if not in_section:
            continue
        m = _TERM_RE.match(line)
        if m:
            term = _clean_md_inline(m.group(1)).strip("` ")[:60]
            meaning = _clean_md_inline(m.group(2))[:180]
            if term and meaning:
                terms.append({"term": term, "meaning": meaning})
    return terms[:16]


def _summarize_section(body_lines: list[str]) -> str:
    """Extract a crisp 1-line summary from a workflow section body."""
    cleaned = [re.sub(r"^#+\s*", "", ln).strip() for ln in body_lines]
    skip_headings = {"user goal", "why it matters", "end-to-end journey", "architectural invariants"}
    bullets: list[str] = []
    for ln in cleaned:
        low = ln.lower().strip(":")
        if not ln or low in skip_headings or ln.startswith("|") or ln == "---":
            continue
        txt = re.sub(r"^\d+\.\s+|^\-\s+", "", ln).strip()
        txt = _clean_md_inline(txt)
        if txt:
            bullets.append(txt)
            if len(bullets) == 1 and len(txt) >= 48:
                break
    joined = " ".join(bullets[:2]).strip()
    return joined[:160].rstrip(" ,;:-") + ("..." if len(joined) > 160 else "")


def _parse_workflow_sections(text: str) -> tuple[list[dict[str, str]], dict[str, str]]:
    """Extract WF-01..WF-NN workflows with titles, summaries, and full Markdown sections."""
    lines = text.splitlines()
    has_numbered = bool(re.search(r"^#{2,3}\s+.*(?:\bWF[-_ ]?0*[1-9]\d?\b|Workflow\s+\d+\s*:)", text, re.I | re.M))
    entries: list[tuple[str, str, list[str]]] = []
    cur_id, cur_title, cur_buf = "", "", []

    for line in lines:
        stripped = line.strip()
        m = _WF_HEADING_RE.match(stripped)
        m_wf_any = _WF_ANY_TAG_RE.search(stripped) if m else None
        wf_num_any = int(m_wf_any.group(1)) if m_wf_any else 0
        legacy_kw = (not has_numbered) and m and m.group(1) == "##" and any(k in stripped.lower() for k in ("workflow", "use case", "journey"))
        is_wf_hdr = bool(m and ((wf_num_any >= 1) or m.group(2) or legacy_kw))
        if is_wf_hdr and m:
            if cur_id:
                entries.append((cur_id, cur_title, cur_buf))
            if wf_num_any >= 1:
                cur_id = f"WF-{wf_num_any:02d}"
            elif m.group(2) and int(m.group(2)) >= 1:
                cur_id = f"WF-{int(m.group(2)):02d}"
            else:
                cur_id = f"WF-{len(entries) + 1:02d}"
            title_src = _WF_ANY_TAG_RE.sub("", stripped.lstrip("# ")).strip(" :—-")
            cur_title = _clean_md_inline(m.group(4) or title_src or stripped.lstrip("# "))
            cur_buf = [line]
        elif cur_id:
            if line.startswith("## "):
                entries.append((cur_id, cur_title, cur_buf))
                cur_id, cur_title, cur_buf = "", "", []
            else:
                cur_buf.append(line)
    if cur_id:
        entries.append((cur_id, cur_title, cur_buf))

    workflows: list[dict[str, str]] = []
    sections: dict[str, str] = {}
    for wid, title, buf in entries[:20]:
        body = "\n".join(buf).strip()
        sections[wid] = body
        workflows.append({
            "id": wid,
            "title": title,
            "summary": _summarize_section(buf[1:]),
        })
    return workflows, sections


def _extract_legacy_titles(text: str, workflows: list[dict[str, str]]) -> list[str]:
    if workflows:
        return [f"{w['id']} — {w['title']}" if w["id"] not in w["title"] else w["title"] for w in workflows][:12]
    titles = [
        re.sub(r"^[#\s\d.-]+", "", ln).strip()
        for ln in text.splitlines()
        if ln.startswith(("## ", "### ", "#### "))
        and any(kw in ln.lower() for kw in ("workflow", "scenario", "flow", "journey", "step", "use case"))
    ]
    if not titles:
        titles = [
            re.sub(r"^[#\s\d.-]+", "", ln).strip()
            for ln in text.splitlines()
            if ln.startswith("## ") and not ln.startswith("###")
        ][:8]
    return titles[:12]


def discover_project_workflows(workspace_path: Path | str, max_chars: int = 3500) -> dict[str, Any]:
    """Inspect workspace for docs/WORKFLOWS.md, returning workflow_status, WF-XX index, and Common Terms."""
    empty = {
        "found": False, "has_workflows_doc": False, "workflow_status": "MISSING_BASELINE",
        "source_file": "", "raw_content": "", "workflow_titles": [], "workflows": [],
        "common_terms": [], "sections": {},
    }
    if not workspace_path:
        return empty
    ws = Path(workspace_path)
    if not ws.is_dir():
        return empty
    ws_res = ws.resolve()
    from agy_nexus.hygiene import is_sensitive_filename

    for rel in WORKFLOW_DOC_CANDIDATES:
        target = ws / rel
        if not target.is_file():
            continue
        try:
            t_res = target.resolve()
            if not t_res.is_relative_to(ws_res) or is_sensitive_filename(target.name) or is_sensitive_filename(t_res.name):
                continue
            text = t_res.read_text(encoding="utf-8", errors="replace").strip()
        except Exception:
            continue
        if not text:
            continue
        workflows, sections = _parse_workflow_sections(text)
        terms = _parse_common_terms(text)
        has_wf_doc = rel in PRIMARY_WORKFLOW_FILES
        titles = _extract_legacy_titles(text, workflows)
        return {
            "found": True,
            "has_workflows_doc": has_wf_doc,
            "workflow_status": "READY" if (has_wf_doc and (workflows or text)) else "MISSING_BASELINE",
            "source_file": rel,
            "raw_content": text[:max_chars] if len(text) > max_chars else text,
            "is_truncated": len(text) > max_chars,
            "workflow_titles": titles,
            "workflows": workflows,
            "common_terms": terms,
            "sections": sections,
        }

    readme = ws / "README.md"
    if readme.is_file():
        try:
            r_res = readme.resolve()
            if not r_res.is_relative_to(ws_res) or is_sensitive_filename(r_res.name):
                return empty
            r_text = r_res.read_text(encoding="utf-8", errors="replace")
            match = re.search(
                r"(?i)(?:^##+\s+(?:.*workflow|.*user\s+journey|.*use\s+case|.*workflows).*?\n)(.*?)(?=\n##+\s+|\Z)",
                r_text, re.DOTALL | re.MULTILINE,
            )
            if match:
                sec_text = match.group(0).strip()
                titles = [
                    re.sub(r"^[#\s\d.-]+", "", line).strip()
                    for line in sec_text.splitlines()
                    if line.startswith(("### ", "#### "))
                ]
                return {
                    "found": True, "has_workflows_doc": False, "workflow_status": "MISSING_BASELINE",
                    "source_file": "README.md",
                    "raw_content": sec_text[:max_chars] if len(sec_text) > max_chars else sec_text,
                    "is_truncated": len(sec_text) > max_chars, "workflow_titles": titles[:12],
                    "workflows": [], "common_terms": [], "sections": {},
                }
        except Exception:
            pass
    return empty


def format_workflow_baseline_for_wire(wf_data: dict[str, Any], max_chars: int = 1800) -> str:
    """Format Common Terms + full WF-01..WF-NN index without cutting off inside doc preamble."""
    status = str(wf_data.get("workflow_status") or "MISSING_BASELINE")
    if not wf_data.get("found"):
        return f"**Workflow Status**: `{status}` — No `docs/WORKFLOWS.md` baseline found."
    src = wf_data.get("source_file", "docs/WORKFLOWS.md")
    header = f"**Established Workflows (`{src}`)**:\n**Workflow Status**: `{status}`"
    workflows = list(wf_data.get("workflows") or [])
    terms = list(wf_data.get("common_terms") or [])
    if not workflows and not terms:
        raw = str(wf_data.get("raw_content", "")).strip()
        total = f"{header}\n\n{raw}"
        if len(total) <= max_chars:
            return total
        suffix = "\n... [compacted for wire ceiling]"
        return f"{header}\n\n{raw[:max(0, max_chars - len(header) - len(suffix) - 2)]}{suffix}"

    lines = [header]
    if terms:
        lines.append("\n**Common Terms**:")
        t_budget = max(80, min(140, (max_chars // 3) // max(1, len(terms))))
        for item in terms:
            meaning = item["meaning"][:t_budget].rstrip() + ("..." if len(item["meaning"]) > t_budget else "")
            lines.append(f"- **{item['term']}**: {meaning}")
    if workflows:
        lines.append("\n**Workflow Index**:")
        used = len("\n".join(lines)) + (len(workflows) * 48)
        per_sum = max(0, min(110, (max_chars - used - 40) // max(1, len(workflows))))
        for w in workflows:
            summ = w["summary"][:per_sum].rstrip() + ("..." if per_sum and len(w["summary"]) > per_sum else "")
            line = f"- **{w['id']}** — {w['title']}" + (f": {summ}" if per_sum >= 24 and summ else "")
            lines.append(line)
    out = "\n".join(lines)
    if len(out) <= max_chars:
        return out
    # Drop summaries before ever truncating a WF-XX heading or Common Term name
    compact = [header]
    if terms:
        compact.append("**Common Terms**: " + "; ".join(f"**{t['term']}**" for t in terms))
    if workflows:
        compact.append("**Workflow Index**:\n" + "\n".join(f"- **{w['id']}** — {w['title']}" for w in workflows))
    res = "\n".join(compact)
    return res[:max_chars] if len(res) > max_chars else res


def evaluate_handoff_quality(research_markdown: str, is_closeout: bool = False) -> dict[str, Any]:
    """Evaluate handoff for genuine Goal & Why + User Interaction prose vs bare code-only dumps."""
    text = (research_markdown or "").strip()
    if not text or is_closeout:
        return {
            "has_goal_or_why": True, "has_workflow": True, "is_code_only_dump": False,
            "is_plain_language_valid": True, "advisory": "", "quality_score": 1.0,
        }

    lower = text.lower()
    prose = re.sub(r"```[\s\S]*?```", " ", lower)
    prose = re.sub(r"\b[\w./-]+\.(?:py|js|ts|tsx|css|html|json|yaml|yml|sql|sh)\b", " ", prose)
    prose = re.sub(r"\b[a-z]+_[a-z0-9_]+\b", " ", prose)

    has_goal_hdr = bool(re.search(r"(?im)^#{1,3}\s+.*(?:user\s+goal|who\s*&\s*goal|goal|why\s+it\s+matters|problem|purpose|intent|overview)\b", text))
    has_goal_prose = bool(re.search(
        r"\b(?:the\s+user\s+(?:wants|needs|can)|so\s+(?:users?|gemini|they)\s+can|allows?\s+(?:the\s+)?users?\s+to|why\s+it\s+matters|goal\s*:|purpose\s*:|who\s*:)",
        prose,
    ))
    has_goal = has_goal_hdr or has_goal_prose

    has_wf_hdr = bool(re.search(r"(?im)^#{1,3}\s+.*(?:workflow|what\s+the\s+user\s+sees|user\s+interaction|end-to-end|journey|taps|expects|scenario)\b", text))
    has_wf_prose = bool(re.search(
        r"\b(?:sees?|clicks?|taps?|expects?|navigates?|visual\s+confirmation|when\s+checking|while\s+\w+ing|empty\s+state|error\s+state|on\s+(?:mobile|tablet|desktop)|wf-\d+)\b",
        prose,
    ))
    has_workflow = has_wf_hdr or has_wf_prose

    line_refs = len(re.findall(r"(?:\b(?:l\d+|line\s+\d+|lines\s+\d+-\d+)\b|:\d{2,4}\b)", lower))
    file_refs = len(re.findall(r"\b[\w./-]+\.(?:py|js|ts|tsx|css|html|sql)\b", lower))
    code_markers = line_refs + file_refs
    words = len(prose.split())
    is_code_only_dump = (not has_goal or not has_workflow) and (code_markers >= 1 or words < 18)

    advisories: list[str] = []
    score = 1.0
    if not has_goal:
        advisories.append("Lacks explicit 'User Goal & Why' section explaining what the user wants to accomplish.")
        score -= 0.35
    if not has_workflow:
        advisories.append("Lacks step-by-step 'End-to-End User Workflows' (what the user clicks, sees, or expects across viewports).")
        score -= 0.35
    if is_code_only_dump and (line_refs or file_refs >= 2):
        advisories.append("Reads like a bare file/line patch dump without plain-language workflow grounding.")
        score -= 0.2

    advisory_msg = ""
    if advisories:
        advisory_msg = (
            "Handoff Quality Advisory: " + " ".join(advisories)
            + " Grounding handoffs in plain-language user workflows prevents follow-up rework."
        )
    return {
        "has_goal_or_why": has_goal,
        "has_workflow": has_workflow,
        "is_code_only_dump": is_code_only_dump,
        "is_plain_language_valid": bool(has_goal and has_workflow),
        "advisory": advisory_msg,
        "quality_score": max(0.1, round(score, 2)),
    }


def extract_user_intent_from_handoff(handoff_content: str, max_chars: int = 1500) -> str:
    """Extract user goal and workflow summary from a handoff for rollover baton continuity."""
    if not handoff_content:
        return ""
    text = handoff_content
    if "<!-- BEGIN_USER_HANDOFF_BODY -->" in text:
        text = text.split("<!-- BEGIN_USER_HANDOFF_BODY -->", 1)[1]
    if "<!-- END_USER_HANDOFF_BODY -->" in text:
        text = text.split("<!-- END_USER_HANDOFF_BODY -->", 1)[0]
    text = text.strip()

    capturing = False
    captured_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith(("# ", "## ")):
            l_lower = line.lower()
            if any(kw in l_lower for kw in ("goal", "why", "intent", "overview", "workflow", "scenario", "common terms")):
                capturing = True
                captured_lines.append(line)
                continue
            if capturing and any(kw in l_lower for kw in ("skill", "modular architecture", "execution lifecycle", "verification")):
                break
            if capturing and line.startswith("# "):
                capturing = False
        if capturing:
            captured_lines.append(line)
            if len("\n".join(captured_lines)) > max_chars:
                break

    if captured_lines:
        res = "\n".join(captured_lines).strip()
        return res[:max_chars] if len(res) > max_chars else res
    clean_lines = [ln for ln in text.splitlines() if not ln.startswith("<!--") and not ln.startswith("> [!")]
    fallback = "\n".join(clean_lines[:25]).strip()
    return fallback[:max_chars] if len(fallback) > max_chars else fallback
