#!/usr/bin/env python3
"""agy_nexus.workflow_baseline — Project Workflow Discovery, Quality Linting & Intent Retention.

Discovers established project workflows (`docs/WORKFLOWS.md`, etc.), formats them for
Gemini session context (< 20 KB wire ceiling), evaluates plain-language handoff quality,
and extracts the user goal and workflow for baton continuity across session rollovers.
"""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any

# Standard workflow documentation locations in priority order
WORKFLOW_DOC_CANDIDATES = (
    "docs/WORKFLOWS.md",
    "docs/workflows.md",
    "WORKFLOWS.md",
    "docs/USE_CASES.md",
    "docs/use_cases.md",
    "SPEC.md",
    "spec.md",
)


def discover_project_workflows(
    workspace_path: Path | str,
    max_chars: int = 3500,
) -> dict[str, Any]:
    """Inspect workspace for established user workflows in docs/WORKFLOWS.md or README.md."""
    if not workspace_path:
        return {"found": False, "source_file": "", "raw_content": "", "workflow_titles": []}
    ws = Path(workspace_path)
    if not ws.is_dir():
        return {"found": False, "source_file": "", "raw_content": "", "workflow_titles": []}

    # 1. Search candidate workflow documentation files
    for rel in WORKFLOW_DOC_CANDIDATES:
        target = ws / rel
        if target.is_file():
            try:
                text = target.read_text(encoding="utf-8", errors="replace").strip()
                if text:
                    titles = [
                        re.sub(r"^[#\s\d.-]+", "", line).strip()
                        for line in text.splitlines()
                        if line.startswith(("## ", "### ", "#### ")) and any(
                            kw in line.lower() for kw in ("workflow", "scenario", "flow", "journey", "step", "use case")
                        )
                    ]
                    if not titles:
                        titles = [
                            re.sub(r"^[#\s\d.-]+", "", line).strip()
                            for line in text.splitlines()
                            if line.startswith("## ") and not line.startswith("###")
                        ][:8]
                    content_slice = text[:max_chars] if len(text) > max_chars else text
                    return {
                        "found": True,
                        "source_file": rel,
                        "raw_content": content_slice,
                        "is_truncated": len(text) > max_chars,
                        "workflow_titles": titles[:12],
                    }
            except Exception:
                continue

    # 2. Fall back to scanning README.md for a Workflow or Use Cases section
    readme = ws / "README.md"
    if readme.is_file():
        try:
            r_text = readme.read_text(encoding="utf-8", errors="replace")
            # Look for a workflow / user journey section
            match = re.search(
                r"(?i)(?:^##+\s+(?:.*workflow|.*user\s+journey|.*use\s+case|.*workflows).*?\n)(.*?)(?=\n##+\s+|\Z)",
                r_text,
                re.DOTALL | re.MULTILINE,
            )
            if match:
                sec_text = match.group(0).strip()
                titles = [
                    re.sub(r"^[#\s\d.-]+", "", line).strip()
                    for line in sec_text.splitlines()
                    if line.startswith(("### ", "#### "))
                ]
                content_slice = sec_text[:max_chars] if len(sec_text) > max_chars else sec_text
                return {
                    "found": True,
                    "source_file": "README.md",
                    "raw_content": content_slice,
                    "is_truncated": len(sec_text) > max_chars,
                    "workflow_titles": titles[:12],
                }
        except Exception:
            pass

    return {"found": False, "source_file": "", "raw_content": "", "workflow_titles": []}


def format_workflow_baseline_for_wire(
    wf_data: dict[str, Any],
    max_chars: int = 1500,
) -> str:
    """Format discovered workflows into compact Markdown for tool payloads (< 20 KB ceiling)."""
    if not wf_data.get("found") or not wf_data.get("raw_content"):
        return ""
    src = wf_data.get("source_file", "docs/WORKFLOWS.md")
    raw = str(wf_data.get("raw_content", "")).strip()
    titles = wf_data.get("workflow_titles", [])
    header = f"**Established Workflows (`{src}`)**:"
    if titles:
        bullet_list = "\n".join(f"- {t}" for t in titles[:6])
    total = f"{header}\n\n{raw}"
    if len(total) <= max_chars:
        return total
    suffix = "\n... [compacted for wire ceiling]"
    budget = max(0, max_chars - len(header) - len(suffix) - 2)
    return f"{header}\n\n{raw[:budget]}{suffix}"


def evaluate_handoff_quality(
    research_markdown: str,
    is_closeout: bool = False,
) -> dict[str, Any]:
    """Evaluate handoff for plain-English user workflow context vs. raw line-number patch directives."""
    text = (research_markdown or "").strip()
    if not text or is_closeout:
        return {"has_goal_or_why": True, "has_workflow": True, "advisory": "", "quality_score": 1.0}

    lower = text.lower()
    has_goal = any(kw in lower for kw in ("goal", "why", "user", "problem", "purpose", "intent", "who"))
    has_workflow = any(kw in lower for kw in ("workflow", "scenario", "step", "flow", "journey", "click", "screen", "posture"))
    
    # Check if the text heavily focuses on line numbers without workflow explanation
    line_number_matches = len(re.findall(r"\b(?:l\d+|\bline\s+\d+|lines\s+\d+)\b", lower))
    word_count = len(text.split())
    line_focus_ratio = (line_number_matches / max(1, word_count)) * 100

    advisories: list[str] = []
    score = 1.0

    if not has_goal:
        advisories.append("Lacks explicit 'User Goal & Why' section explaining what the user wants to accomplish.")
        score -= 0.3
    if not has_workflow:
        advisories.append("Lacks step-by-step 'End-to-End User Workflows' (what the user clicks, sees, or expects across viewports).")
        score -= 0.3
    if line_focus_ratio > 1.5 and not has_workflow:
        advisories.append("Over-indexes on line-number edits without explaining the user experience or underlying workflow.")
        score -= 0.2

    advisory_msg = ""
    if advisories:
        advisory_msg = (
            "Handoff Quality Advisory: " + " ".join(advisories) +
            " Grounding handoffs in plain-English user workflows reduces follow-up rework passes by >40%."
        )

    return {
        "has_goal_or_why": has_goal,
        "has_workflow": has_workflow,
        "advisory": advisory_msg,
        "quality_score": max(0.2, round(score, 2)),
    }


def extract_user_intent_from_handoff(
    handoff_content: str,
    max_chars: int = 1500,
) -> str:
    """Extract user goal and workflow summary from a handoff for rollover baton continuity."""
    if not handoff_content:
        return ""
    
    # Strip wrapping markers if present
    text = handoff_content
    if "<!-- BEGIN_USER_HANDOFF_BODY -->" in text:
        text = text.split("<!-- BEGIN_USER_HANDOFF_BODY -->", 1)[1]
    if "<!-- END_USER_HANDOFF_BODY -->" in text:
        text = text.split("<!-- END_USER_HANDOFF_BODY -->", 1)[0]
    text = text.strip()

    # Look for User Goal / Why or plain English summary sections
    sections: list[str] = []
    lines = text.splitlines()
    capturing = False
    captured_lines: list[str] = []

    for line in lines:
        if line.startswith(("# ", "## ")):
            l_lower = line.lower()
            if any(kw in l_lower for kw in ("goal", "why", "intent", "overview", "workflow", "scenario")):
                capturing = True
                captured_lines.append(line)
                continue
            elif capturing and any(kw in l_lower for kw in ("skill", "modular architecture", "execution lifecycle", "verification")):
                capturing = False
                break
            elif capturing and line.startswith("# "):
                capturing = False
        if capturing:
            captured_lines.append(line)
            if len("\n".join(captured_lines)) > max_chars:
                break

    if captured_lines:
        res = "\n".join(captured_lines).strip()
        return res[:max_chars] if len(res) > max_chars else res

    # Fallback to the first 800 characters of the body
    clean_lines = [l for l in lines if not l.startswith("<!--") and not l.startswith("> [!")]
    fallback = "\n".join(clean_lines[:25]).strip()
    return fallback[:max_chars] if len(fallback) > max_chars else fallback
