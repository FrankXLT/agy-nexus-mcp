#!/usr/bin/env bash
# sync_repo.sh — Synchronizes sidecars/ag-bridge-mcp in antigravity-config with
# the standalone ~/gitlab/ag-bridge-mcp repository and pushes to GitLab.

set -euo pipefail

SRC_DIR="${AG_BRIDGE_SRC_DIR:-$HOME/gitlab/antigravity-config/sidecars/ag-bridge-mcp}"
DST_DIR="${AG_BRIDGE_DST_DIR:-$HOME/gitlab/ag-bridge-mcp}"
ANTIGRAVITY_REPO="${HOME}/gitlab/antigravity-config"

if [[ "${1:-}" == "--install-hooks" ]]; then
  HOOK_FILE="${ANTIGRAVITY_REPO}/.git/hooks/post-commit"
  cat > "${HOOK_FILE}" << 'EOF'
#!/usr/bin/env bash
# Auto-sync sidecars/ag-bridge-mcp to standalone ag-bridge-mcp repository when modified
if git diff-tree --no-commit-id --name-only -r HEAD | grep -q "^sidecars/ag-bridge-mcp/"; then
  "$HOME/gitlab/antigravity-config/sidecars/ag-bridge-mcp/scripts/sync_repo.sh" >/dev/null 2>&1 &
fi
EOF
  chmod +x "${HOOK_FILE}"
  echo "Installed post-commit auto-sync hook at ${HOOK_FILE}"
  exit 0
fi

mkdir -p "${DST_DIR}"
rsync -a --delete \
  --exclude='.git' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.venv' \
  --exclude='venv' \
  --exclude='secrets.env' \
  "${SRC_DIR}/" "${DST_DIR}/"

cd "${DST_DIR}"
if [[ -d .git ]]; then
  if [[ -n "$(git status --porcelain)" ]]; then
    LAST_MSG="$(git -C "${ANTIGRAVITY_REPO}" log -1 --pretty=%s 2>/dev/null || echo "chore: sync ag-bridge-mcp")"
    git add -A
    git commit -m "${LAST_MSG}"
    git push origin main
    echo "Synced and pushed changes to standalone ag-bridge-mcp repo."
  else
    echo "Standalone ag-bridge-mcp repo is already up to date."
  fi
fi
