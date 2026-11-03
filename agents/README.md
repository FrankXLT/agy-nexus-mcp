# Bundled Antigravity Agent Roles (`8-Agent Orthogonal Roster`)

This directory contains the 8 core agent definitions (plus failover and orchestrator helpers) used by `agy-nexus-mcp` and `list_models_and_agents`:

| Agent File | Role | Model Tier | Effort | Tool Permissions | Primary Responsibility |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `flash-scout.md` | Fast Codebase Mapper | `flash` | Low | Read-Only | Directory mapping, symbol indexing, fast grep scans |
| `argon-architect.md` | System Blueprint Architect | `pro` | High | Read-Only | 1M+ context blueprinting, schema design, task decomposition |
| `flash-surgeon.md` | High-Volume Code Writer | `flash` | Medium | Read-Write | Boilerplate, CRUD, mechanical refactors, CSS/UI styling |
| `argon-surgeon.md` | Deep Systems Surgeon | `pro` | Medium | Read-Write | State machines, async concurrency, algorithms, tricky logic |
| `flash-auditor.md` | Rapid Test & Lint Runner | `flash` | Low | Read+Exec | Executes unit tests, linters, and extracts minimal failure traces |
| `argon-sentinel.md` | Invariant & Safety Auditor | `pro` | High | Read-Only | Race conditions, resource leaks, and security invariant checks |
| `claude-specialist.md` | Strike-2 Escalation Surgeon | `inherit` | High | Read-Write | Resolves Strike-2 bugs from `<3k` token escalation briefs |
| `claude-sentinel.md` | Cross-Family Security Gate | `inherit` | High | Read-Only | Orthogonal auth, crypto, and `/dual-review` security audits |

## Installation

Copy these templates into your local Antigravity configuration directory:

```bash
mkdir -p ~/.gemini/config/agents
cp agents/*.md ~/.gemini/config/agents/
```
