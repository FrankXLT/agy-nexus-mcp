# Bundled Antigravity Agent Roles (`8-Model Multi-Agent Roster`)

This directory contains the tracked agent definitions used by `agy-nexus-mcp`, `list_models_and_agents`, and `scripts/sync_agents.py`. All subagents enforce a `<= 120`-step ceiling and `model:` values compatible with Antigravity's YAML loader (`inherit`, `flash`, `pro`, `flash_lite`), while `targetModel` and `difficultyLevel` annotate the physical model and effort tier:

| Agent File | Role | `model` Arg | `targetModel` | Effort | Tools | Primary Responsibility |
| :--- | :--- | :---: | :--- | :---: | :--- | :--- |
| `flash-scout.md` | Fast Codebase Mapper | `flash` | Gemini 3.8 Flash | Low | Read-Only | Directory mapping, symbol indexing, fast grep scans |
| `argon-architect.md` | System Blueprint Architect | `pro` | Gemini 4 Carbon / Argon | High | Read-Only | 1M+ context blueprinting, schema design, task decomposition |
| `flash-surgeon.md` | High-Volume Code Writer | `flash` | Gemini 3.8 Flash | Medium | Read-Write | Boilerplate, CRUD, version bumps, docs, test fixtures |
| `hydrogen-surgeon.md` | Everyday Multi-File Surgeon | `flash` | Gemini 4 Hydrogen | Medium | Read-Write | Everyday multi-file coding & `<= 500L` module splits |
| `neon-surgeon.md` | Frontend & Visual Surgeon | `pro` | Gemini 4 Neon | Medium | Read-Write | Frontend state, Quiet UI CSS & SVG/ECharts geometry |
| `argon-surgeon.md` | Deep Systems Surgeon | `pro` | Gemini 4 Argon | Medium | Read-Write | State machines, async concurrency, algorithms (`1–3` files) |
| `flash-auditor.md` | Rapid Test & Lint Runner | `flash` | Gemini 3.8 Flash | Low | Read+Exec | Executes unit tests, linters, and extracts minimal failure traces |
| `argon-sentinel.md` | Invariant & Safety Auditor | `pro` | Gemini 4 Argon | High | Read-Only | Race conditions, resource leaks, and security invariant checks |
| `carbon-sentinel.md` | Tab 1 Orthogonal Gate | `inherit` | Gemini 4 Carbon | High | Read-Only | Mode A Tab 1 security, auth & contract auditor (`0%` Partner) |
| `claude-specialist.md` | Strike-2 Escalation Surgeon | `inherit` | Claude Sonnet 5.5 | Medium | Read-Write | Resolves Strike-2 bugs from `<3k` token escalation briefs |
| `claude-sentinel.md` | Cross-Family Security Gate | `inherit` | Claude Sonnet 5.5 | High | Read-Only | Orthogonal auth, crypto, and `/dual-review` security audits |
| `pool-failover.md` | Quota Arbitrage Dispatcher | `flash` | GPT-OSS 120B | Medium | Read+Exec | Queries `quota-router.sh` for Partner Pool failover routing |
| `swarm-orchestrator.md` | Mission Control Orchestrator | `inherit` | Gemini 4 Carbon | Medium | Main Agent | Thin-orchestrator Dual-Tab routing loop |

## Sync Parity & Installation

Check SHA-256 parity against `~/.gemini/config/agents/` without mutating global files:

```bash
python3 scripts/sync_agents.py --check
```

Explicitly apply tracked repo templates to `~/.gemini/config/agents/` when desired outside feature sessions:

```bash
python3 scripts/sync_agents.py --apply
```
