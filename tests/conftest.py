#!/usr/bin/env python3
"""Shared pytest fixtures ensuring zero leakage into live session_state.json."""
from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Iterator

import pytest

import agy_nexus.config as cfg
from agy_nexus.telemetry_scanner import WIRE_TELEMETRY_RING


@pytest.fixture(autouse=True)
def isolate_session_state(tmp_path: Path) -> Iterator[None]:
    """Snapshot SESSION_STATE, WIRE_TELEMETRY_RING, STATE_FILE, and AGY_BG_DIR to temporary per-test paths."""
    orig_state_file = cfg.STATE_FILE
    orig_bg_dir = cfg.AGY_BG_DIR
    orig_env_state = os.environ.get("AG_BRIDGE_STATE_FILE")
    orig_session_state = copy.deepcopy(cfg.SESSION_STATE)
    orig_wire_ring = copy.deepcopy(WIRE_TELEMETRY_RING)

    isolated_bg = tmp_path / "isolated_bg"
    isolated_bg.mkdir(parents=True, exist_ok=True)
    isolated_state_file = isolated_bg / "session_state.json"
    cfg.AGY_BG_DIR = isolated_bg
    cfg.STATE_FILE = isolated_state_file
    os.environ["AG_BRIDGE_STATE_FILE"] = str(isolated_state_file)
    cfg.SESSION_STATE.update({
        "unlocked_at": 0.0,
        "selected_session": "",
        "selected_workspace": "",
        "selected_workspace_uris": [],
        "selected_project": "",
        "active_contexts": {},
        "pinned_calls": 0,
        "auto_resolved_calls": 0,
        "session_index_map": {},
        "session_workspace_map": {},
        "session_workspace_uris_map": {},
        "session_project_map": {},
        "session_title_map": {},
    })
    WIRE_TELEMETRY_RING.clear()
    try:
        yield
    finally:
        WIRE_TELEMETRY_RING.clear()
        WIRE_TELEMETRY_RING.extend(orig_wire_ring)
        cfg.AGY_BG_DIR = orig_bg_dir
        cfg.STATE_FILE = orig_state_file
        if orig_env_state is None:
            os.environ.pop("AG_BRIDGE_STATE_FILE", None)
        else:
            os.environ["AG_BRIDGE_STATE_FILE"] = orig_env_state
        cfg.SESSION_STATE.clear()
        cfg.SESSION_STATE.update(orig_session_state)
