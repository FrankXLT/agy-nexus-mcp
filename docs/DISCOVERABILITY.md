# AGY-Nexus MCP Discoverability & Release Metadata (`v4.2.0`)

This reference holds the ready-to-apply metadata for the **`v4.2.0`** release across GitHub Repository Settings, the Official MCP Registry (`server.json`), Python packaging (`pyproject.toml`), and the static project site.

---

## 1. Concise Repository Summary (`98` chars)

Use this single-sentence summary for GitHub **About -> Description**, `pyproject.toml`, and registry listings:

```text
Two-doorway MCP server to steer your IDE from Gemini, track quota % left, and route helper models.
```

---

## 2. Fourteen Curated GitHub Search Topics

Apply all **14** topics in GitHub **Repository Settings -> About -> Topics** (or via `gh repo edit`):

1. `mcp`
2. `model-context-protocol`
3. `mcp-server`
4. `gemini`
5. `antigravity-ide`
6. `claude-code`
7. `ai-coding-assistant`
8. `multi-agent-orchestration`
9. `subagents`
10. `token-usage-tracker`
11. `quota-tracker`
12. `developer-tools`
13. `self-hosted`
14. `progressive-web-app`

Space-separated topic string for quick paste:

```text
mcp model-context-protocol mcp-server gemini antigravity-ide claude-code ai-coding-assistant multi-agent-orchestration subagents token-usage-tracker quota-tracker developer-tools self-hosted progressive-web-app
```

---

## 3. Registry & Project Site URLs

### Canonical Project Site & Relative Hub Links

| Target | Value | Usage |
| :--- | :--- | :--- |
| Canonical Project URL | `https://projects.oaworkbench.org/agy-nexus-mcp/` | Primary homepage for GitHub About, `server.json`, and `pyproject.toml` |
| Static Interactive Demo | `./demo/` | Relative portfolio switcher route (`https://projects.oaworkbench.org/agy-nexus-mcp/demo/`) |
| Documentation Hub | `./docs/` | Relative portfolio switcher route (`https://projects.oaworkbench.org/agy-nexus-mcp/docs/`) |

### Manifest Alignment Checklist (`v4.2.0`)

| File | Field | Target `v4.2.0` Value | Verified State |
| :--- | :--- | :--- | :--- |
| `pyproject.toml` | `project.description` | `Two-doorway MCP server to steer your IDE from Gemini, track quota % left, and route helper models.` | Aligned (`version = "4.2.0"`) |
| `pyproject.toml` | `[project.urls].Homepage` | `https://projects.oaworkbench.org/agy-nexus-mcp/` | Aligned for `v4.2.0` |
| `pyproject.toml` | `[project.urls].Documentation` | `https://projects.oaworkbench.org/agy-nexus-mcp/docs/` | Aligned for `v4.2.0` |
| `server.json` | `websiteUrl` | `https://projects.oaworkbench.org/agy-nexus-mcp/` | Aligned for `v4.2.0` |
| `server.json` | `version` & OCI tag | `4.2.0` / `ghcr.io/frankxlt/agy-nexus-mcp:4.2.0` | Aligned (`<= 100` char description) |

---

## 4. Social Preview Asset Check

- **Expected Path**: `docs/assets/social-preview.png`
- **Required Dimensions**: `1280x640` (`2:1` aspect ratio, PNG under `1 MB`)
- **Current Status**: **Ready** — `docs/assets/social-preview.png` (`1280x640`) and the refreshed `docs/assets/` captures (`dashboard-desktop.png`, `dashboard-mobile.png`, `workspace-desktop.png`, `workspace-mobile.png`) are stripped of all PNG metadata chunks and synced into `build/gh-pages/assets/`.
- **Release Action**: After release approval and `main` merge, upload `docs/assets/social-preview.png` under GitHub **Settings -> General -> Social preview** alongside applying the 14 topics and repository homepage URL.
