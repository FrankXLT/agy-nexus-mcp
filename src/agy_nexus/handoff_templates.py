#!/usr/bin/env python3
"""
agy_nexus.handoff_templates — Proportional Execution Lifecycle & Security-Boundary Classifiers.
"""
from __future__ import annotations

import re

_NEGATED_SECURITY_RE = re.compile(
    r"\b(?:non-(?:security|auth)|not\s+(?:touching|modifying|changing)\s+(?:(?:the|any|global|ui|css|layout)\s+){0,2}(?:security|auth|deadbolt|middleware))\b",
    re.IGNORECASE,
)

_SECURITY_SYMBOL_RE = re.compile(
    r"(?:middleware\.py|bridge_security\.py|bucket_api\.py|uploads\.py|media\.py|webhook_proxy\.py|"
    r"secrets\.env|PASS_HASH|PATH_SECRET|PRAXIS_MCP_TOKEN|POLYGLOT_MCP_TOKEN|HOST_BRIDGE_TOKEN|"
    r"verify_passphrase|verify_bridge_token|is_unlocked|is_client_ip_allowed|deadbolt|hmac)",
    re.IGNORECASE,
)

_SECURITY_KEYWORD_RE = re.compile(
    r"\b(?:auth|authentication|authorization|rbac|csrf|xss|sqli|ssrf|jwt|oauth|security|"
    r"passphrase|traversal|symlink|sandbox|cwe-\d+|command\s+injection)\b",
    re.IGNORECASE,
)

_DUAL_REVIEW_CONTEXT_RE = re.compile(
    r"\b(?:publish_to_github|release_closeout|release\s+closeout)\b|"
    r"\b(?:security|auth|authentication|authorization|rbac|csrf|xss|sqli|ssrf|jwt|oauth|passphrase)\s+"
    r"(?:audit|review|fix|gate|guard|boundary|bypass|flow|token|hash|hmac|middleware|check|policy|hardening|bug|vulnerability|model|layer|isolation|issue|route|endpoint|leak)\b|"
    r"\b(?:path\s+traversal|symlink\s+(?:escape|bypass|guard)|command\s+injection|fix\s+(?:xss|sqli|csrf|ssrf))\b|"
    r"\b(?:audit|review|harden|bypass|fix|enforce)\s+(?:[\w-]+\s+)?(?:security|authentication|authorization|xss|sqli|csrf|ssrf)\b",
    re.IGNORECASE,
)


def _strip_negated_security_phrases(text: str) -> str:
    return _NEGATED_SECURITY_RE.sub(" ", text or "")


def touches_security_boundary(body_clean: str) -> bool:
    """Return True when handoff text indicates security, auth, deadbolt, crypto, or middleware scope."""
    cleaned = _strip_negated_security_phrases(body_clean)
    return bool(_SECURITY_SYMBOL_RE.search(cleaned) or _SECURITY_KEYWORD_RE.search(cleaned))


def should_inject_dual_review(research_markdown: str, handoff_mode: str = "") -> bool:
    """Return True only when release closeout, publishing, or genuine security/auth/deadbolt boundaries are in scope."""
    if (handoff_mode or "").strip().lower() in ("release_closeout", "closeout"):
        return True
    cleaned = _strip_negated_security_phrases(research_markdown)
    return bool(_SECURITY_SYMBOL_RE.search(cleaned) or _DUAL_REVIEW_CONTEXT_RE.search(cleaned))


_DELIVERABLE_ITEM_RE = re.compile(
    r"(?:^|\n)\s*(?:\d{1,2}[.)]|[-*]\s*\[\s*[xX ]?\s*\]|#{2,3}\s+\d{1,2}\.)\s+",
)


def count_deliverables(body_clean: str) -> int:
    """Count numbered/checkbox/section deliverables in a handoff specification."""
    return len(_DELIVERABLE_ITEM_RE.findall(body_clean or ""))


def resolve_execution_mode_with_reason(
    raw_exec_mode: str,
    eff_handoff_mode: str,
    body_clean: str,
    allow_chained_publish: bool,
    resume_headless: bool,
) -> tuple[str, bool, str]:
    """Resolve effective execution_mode plus (coerced_from_fast, advisory_reason)."""
    mode_norm = (raw_exec_mode or "auto").strip().lower()
    sec_hit = touches_security_boundary(body_clean)
    deliv_count = count_deliverables(body_clean)
    heavy_feature = (
        eff_handoff_mode == "feature_update"
        and (len(body_clean or "") > 2200 or deliv_count >= 3 or sec_hit)
    )
    if mode_norm == "plan":
        return "plan", False, ""
    if mode_norm == "fast":
        if eff_handoff_mode == "new_project":
            return "plan", True, "Coerced execution_mode='fast' -> 'plan' for new_project architecture."
        if heavy_feature:
            return (
                "plan",
                True,
                f"Coerced execution_mode='fast' -> 'plan' for multi-deliverable/complex feature_update (chars={len(body_clean or '')}, deliverables={deliv_count}).",
            )
        return "fast", False, ""
    if eff_handoff_mode == "new_project":
        return "plan", False, ""
    if allow_chained_publish and resume_headless and not heavy_feature and not sec_hit:
        return "fast", False, ""
    if eff_handoff_mode == "release_closeout" and not sec_hit:
        return "fast", False, ""
    if (
        eff_handoff_mode == "bug_or_visual_fix"
        and len(body_clean or "") < 6500
        and not sec_hit
    ):
        return "fast", False, ""
    return "plan", False, ""


def resolve_effective_execution_mode(
    raw_exec_mode: str,
    eff_handoff_mode: str,
    body_clean: str,
    allow_chained_publish: bool,
    resume_headless: bool,
) -> str:
    """Resolve 'auto' execution mode proportionally to task scope and security risk."""
    eff_mode, _, _ = resolve_execution_mode_with_reason(
        raw_exec_mode, eff_handoff_mode, body_clean, allow_chained_publish, resume_headless
    )
    return eff_mode


def is_surgical_fast_path(eff_exec_mode: str, eff_handoff_mode: str, body_clean: str) -> bool:
    """Return True when a compact non-security bugfix/closeout qualifies for Main-Chat fast-path execution."""
    return (
        eff_exec_mode == "fast"
        and eff_handoff_mode in ("bug_or_visual_fix", "release_closeout")
        and not touches_security_boundary(body_clean)
    )


_CANONICAL_ROLE_ALLOWLIST = (
    "`flash-scout`, `argon-architect`, `flash-surgeon`, `hydrogen-surgeon`, "
    "`neon-surgeon`, `argon-surgeon`, `flash-auditor`, `argon-sentinel`, "
    "`carbon-sentinel`, `claude-specialist`, `claude-sentinel`, `pool-failover`"
)

_THIN_COORDINATOR_LAW = (
    "**Thin-Coordinator Law**: Main Chat (`Gemini 4 Carbon`) stays a lightweight `< 250`-step coordinator and MUST obey the **12-role Canonical Subagent Role Allowlist** "
    f"({_CANONICAL_ROLE_ALLOWLIST}). "
    "Never invent task-prefixed or ad-hoc `TypeName`s (e.g., `wave1-argon-sentinel`, `diff-auditor`) or fall back to built-in `\"research\"` / `\"self\"`. "
    "If any canonical role is missing from `<subagents>`, register that exact canonical role via `define_subagent` before `invoke_subagent`."
)


def build_execution_lifecycle_footer(eff_exec_mode: str, eff_handoff_mode: str, body_clean: str) -> str:
    """Return proportional Tier 1 Surgical Fast-Path or Tier 2 Full 4-Step Dual-Review footer."""
    if is_surgical_fast_path(eff_exec_mode, eff_handoff_mode, body_clean):
        verify_step = (
            "3. **Release Gate & Verification**: Run `pytest` + `--self-test` directly (or 1 bounded `flash-auditor` pass) and perform concise `argon-sentinel` + `carbon-sentinel` pre-release verification on unreviewed diffs before publishing/closing out.\n"
            if eff_handoff_mode == "release_closeout"
            else "3. **Fast Verification**: Run `pytest` + `--self-test` directly (or 1 quick `flash-auditor` pass) — **skipping** `argon-sentinel` + `carbon-sentinel` Multi-Agent Dual-Review unless `4+` source modules or security/auth boundaries change.\n"
        )
        return (
            "\n---\n\n"
            "## Surgical Fast-Path Lifecycle (`fast` Mode — Thin-Coordinator Direct)\n\n"
            f"- {_THIN_COORDINATOR_LAW}\n\n"
            "1. **Direct Scout (`polyglot_outline` / `view_file`)**: Read attached `SKILL.md` contracts and inspect target spans directly in **Main Chat (`Gemini 4 Carbon`)** via `agy-praxis-mcp` / `serena`. Do **NOT** spawn `flash-scout` or surgeons when `< 3` files are touched.\n"
            "2. **Surgical Edit (`<= 500L`/file)**: Apply edits directly in Main Chat (`<= 500` lines/file, `650L` ceiling, functions `<= 100` lines), update `docs/WORKFLOWS.md` if behavior changed, and preserve `PWA_ASSETS` + `web/sw.js` parity if `web/` changed.\n"
            + verify_step
            + "4. **Local Restart & Preview**: Restart `ag-bridge-mcp` whenever Python/web files change, run 1 concise browser check when `web/` UI changed, and halt at local staging if `allow_chained_publish=False`.\n"
        )
    return (
        "\n---\n\n"
        "## Mandatory 4-Step Execution Lifecycle & Thin-Coordinator Verification Gate\n\n"
        f"- {_THIN_COORDINATOR_LAW}\n\n"
        "1. **Scout (`agy-praxis-mcp` / Serena LSP / `flash-scout`)**: Read attached `SKILL.md` contracts first. Use `agy-praxis-mcp` (`polyglot_map`, `polyglot_search`, `polyglot_outline`) or `serena` LSP directly when `< 3` files; delegate reconnaissance across `3+` unfamiliar modules to `flash-scout` (`model='flash'`, `20–50` steps) to locate connected routes, static allowlists (e.g., `PWA_ASSETS`), caches, and responsive containers.\n"
        "2. **Implement (Parallel Surgeon Dispatch Matrix)**: Delegate multi-file work (`1–2` owned files per dispatch, `40–80` target steps, hard `<= 120` cap, `<= 500L`/file, `650L` ceiling, functions `<= 100L`):\n"
        "   - `flash-surgeon` (`model='flash'`): mechanical edits, tests, docs, version bumps, cohesive splits.\n"
        "   - `hydrogen-surgeon` (`model='flash'`, `targetModel: \"Gemini 4 Hydrogen\"`): default everyday `2–4` file feature and API wiring.\n"
        "   - `neon-surgeon` (`model='pro'`, `targetModel: \"Gemini 4 Neon\"`): Quiet UI CSS geometry, client state, SVG/ECharts charts.\n"
        "   - `argon-surgeon` (`model='pro'`, `targetModel: \"Gemini 4 Argon\"`): `1–2` complex concurrency, state-machine, or algorithmic files.\n"
        "   - `argon-architect` (`model='pro'`): 1M+ context blueprinting & `OWNED_FILES` task splits when needed.\n"
        "   Update `docs/WORKFLOWS.md` whenever behavior changes.\n"
        "3. **Audit (`flash-auditor` & Tab 1 Intra-Google Dual-Review)**: Invoke `flash-auditor` (`model='flash'`, `40–80` steps) for bounded-flag test/lint/self-test verification. Run Tab 1 Intra-Google Dual-Review pairing `argon-sentinel` (`model='pro'`) + `carbon-sentinel` (`model='inherit'`) — strictly shell-free read-only scoped to `review_diff.patch` + touched `Lstart-Lend` spans (`0%` Partner quota; never `\"research\"` or `claude-sentinel` on Gemini tabs!). Escalate Strike-2 blockers via a `<3k` brief to Tab 2 (`claude-specialist` / Mode B `claude-sentinel`).\n"
        "4. **Visual & Preview Gate**: If any `.html`, `.css`, or frontend `.js` files were modified, run `~/.gemini/config/skills/visual-architecture-system/scripts/verify_visual_contract.py` against the local page and save desktop + mobile screenshots to the session artifact directory. Test actual user click-through flows (logged-out/locked state, unlocked state, and `390px` / `900px` / `1440px` widths on target app's real port) rather than just checking if selectors exist in HTML. When `allow_chained_publish=False`, halt at local staging + preview without pushing or redeploying (restarting the local `ag-bridge-mcp` service/container whenever Python/web files change so fixes take effect in memory immediately).\n"
    )


def build_existing_session_lifecycle_text(
    eff_exec_mode: str,
    eff_handoff_mode: str,
    body_clean: str,
    gate_directive: str,
) -> str:
    """Return proportional lifecycle instructions for follow-up wakeup prompts on existing sessions."""
    if is_surgical_fast_path(eff_exec_mode, eff_handoff_mode, body_clean):
        return (
            "Follow the Surgical Fast-Path Lifecycle (Thin-Coordinator Direct):\n"
            f"- {_THIN_COORDINATOR_LAW}\n"
            "1. Scout: Read attached SKILL.md contracts and inspect target spans directly via polyglot_outline / view_file / serena (skip flash-scout and surgeons when < 3 files).\n"
            "2. Implement: Apply surgical edits directly in Main Chat (<= 500L/file, 650L ceiling, functions <= 100L) and update docs/WORKFLOWS.md if behavior changed.\n"
            "3. Verify: Run pytest + --self-test directly (or 1 quick flash-auditor pass) — skip argon-sentinel + carbon-sentinel Multi-Agent Dual-Review unless 4+ source modules or security/auth boundaries change.\n"
            f"4. Gate: {gate_directive}"
        )
    return (
        "Follow the Mandatory 4-Step Execution Lifecycle (Thin-Coordinator Hybrid):\n"
        f"- {_THIN_COORDINATOR_LAW}\n"
        "1. Scout: Read attached SKILL.md contracts first; use agy-praxis-mcp (polyglot_map, polyglot_search, polyglot_outline) or serena LSP directly when < 3 files, or delegate 3+ unfamiliar modules to flash-scout (model='flash', 20-50 steps).\n"
        "2. Implement (Parallel Surgeon Dispatch Matrix — 1-2 owned files/dispatch, 40-80 target steps, hard <= 120 cap, <= 500L/file, 650L ceiling, functions <= 100L): flash-surgeon (model='flash': mechanical/tests/docs/version/splits), hydrogen-surgeon (model='flash', Gemini 4 Hydrogen: default 2-4 file feature/API wiring), neon-surgeon (model='pro', Gemini 4 Neon: Quiet UI CSS/client state/SVG/ECharts), argon-surgeon (model='pro', Gemini 4 Argon: 1-2 complex concurrency/state-machine/algorithm files), argon-architect (model='pro': 1M+ blueprinting & OWNED_FILES splits). Update docs/WORKFLOWS.md whenever behavior changes.\n"
        "3. Audit: Invoke flash-auditor (model='flash', 40-80 steps) for bounded-flag test/lint/self-test verification, plus Tab 1 Intra-Google Dual-Review pairing argon-sentinel (model='pro') + carbon-sentinel (model='inherit') — strictly shell-free read-only scoped to review_diff.patch + touched Lstart-Lend spans (0% Partner quota; never \"research\" or claude-sentinel on Gemini tabs!). Escalate Strike-2 blockers via a <3k brief to Tab 2 (claude-specialist / Mode B claude-sentinel).\n"
        f"4. Gate: {gate_directive}"
    )

