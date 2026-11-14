#!/usr/bin/env python3
"""agy_nexus.tools_polyglot — Backward-compatible shim re-exporting `agy-praxis-mcp` (`tools_praxis.py`)."""
from __future__ import annotations

from agy_nexus.tools_praxis import (  # noqa: F401
    main,
    polyglot_map,
    polyglot_outline,
    polyglot_search,
    praxis_claim_handoff,
    praxis_handoff_inbox,
    praxis_mcp,
    praxis_mcp as polyglot_mcp,
    praxis_update_handoff,
)

if __name__ == "__main__":
    main()
