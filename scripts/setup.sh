#!/usr/bin/env bash
# setup.sh — Cross-Platform Bash Setup Wizard for ag-bridge-mcp (Linux / macOS)
# Generates SUBDOMAIN_HASH, PATH_SECRET, normalized SHA-256 PASS_HASH, and
# configurable session/context-window environment variables with 0600 permissions.

set -euo pipefail

DOMAIN="${AG_BRIDGE_DOMAIN:-example.com}"
ENV_FILE="${HOME}/.config/ag-bridge-mcp/secrets.env"
PASSPHRASE=""
TTL_SECONDS="7200"
MAX_FILE_CHARS="15000"
MAX_TOTAL_FILE_CHARS="24000"
MAX_FILES_PER_CALL="6"
MAX_DIFF_CHARS="15000"
MAX_TRANSCRIPT_TURNS="10"
ENFORCE_MODULAR_HYGIENE="true"
TARGET_FILE_LINES="300"
HARD_MAX_FILE_LINES="400"
KEEP_URLS="false"
QUIET="false"

usage() {
  cat << 'EOF'
Usage: ./scripts/setup.sh [options]

Options:
  --domain <domain>            Base domain (e.g. yourdomain.com)
  --passphrase <phrase>        Spoken passphrase (prompts interactively if omitted)
  --env-file <path>            Output secrets file (default: ~/.config/ag-bridge-mcp/secrets.env)
  --ttl <seconds>              Session deadbolt inactivity timeout in seconds (default: 7200)
  --max-file-chars <chars>     Max characters returned per file slice (default: 15000)
  --max-diff-chars <chars>     Max characters returned per git diff page (default: 15000)
  --enforce-modular <bool>     Enforce <=300 line modular architecture rule (default: true)
  --keep-existing-urls         Keep existing SUBDOMAIN_HASH and PATH_SECRET when rotating passphrase
  --quiet                      Print masked confirmation only
  -h, --help                   Show this help message
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain) DOMAIN="$2"; shift 2 ;;
    --passphrase) PASSPHRASE="$2"; shift 2 ;;
    --env-file) ENV_FILE="$2"; shift 2 ;;
    --ttl) TTL_SECONDS="$2"; shift 2 ;;
    --max-file-chars) MAX_FILE_CHARS="$2"; shift 2 ;;
    --max-diff-chars) MAX_DIFF_CHARS="$2"; shift 2 ;;
    --enforce-modular) ENFORCE_MODULAR_HYGIENE="$2"; shift 2 ;;
    --keep-existing-urls) KEEP_URLS="true"; shift ;;
    --quiet) QUIET="true"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "${PASSPHRASE}" ]]; then
  if [[ -t 0 ]]; then
    if [[ "${DOMAIN}" == "example.com" ]]; then
      read -r -p "Enter your base domain [example.com]: " INPUT_DOMAIN
      DOMAIN="${INPUT_DOMAIN:-example.com}"
    fi
    read -r -s -p "Enter spoken voice passphrase for Antigravity deadbolt: " PASSPHRASE
    echo ""
    read -r -s -p "Confirm voice passphrase: " CONFIRM_PASS
    echo ""
    if [[ "${PASSPHRASE}" != "${CONFIRM_PASS}" ]]; then
      echo "Error: Passphrases did not match." >&2
      exit 1
    fi
    read -r -p "Session unlock duration in seconds [${TTL_SECONDS}]: " INPUT_TTL
    TTL_SECONDS="${INPUT_TTL:-$TTL_SECONDS}"
  else
    echo "Error: --passphrase is required when running non-interactively." >&2
    exit 1
  fi
fi

# Normalize passphrase: lowercase alphanumeric only -> SHA-256 hex digest
NORMALIZED="$(printf '%s' "${PASSPHRASE}" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9')"
if [[ -z "${NORMALIZED}" ]]; then
  echo "Error: Passphrase must contain at least one letter or digit." >&2
  exit 1
fi

if command -v sha256sum >/dev/null 2>&1; then
  PASS_HASH="$(printf '%s' "${NORMALIZED}" | sha256sum | awk '{print $1}')"
elif command -v shasum >/dev/null 2>&1; then
  PASS_HASH="$(printf '%s' "${NORMALIZED}" | shasum -a 256 | awk '{print $1}')"
else
  PASS_HASH="$(printf '%s' "${NORMALIZED}" | openssl dgst -sha256 | awk '{print $NF}')"
fi

gen_hex() {
  local bytes="$1"
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex "${bytes}"
  else
    od -An -N "${bytes}" -tx1 /dev/urandom | tr -d ' \n'
  fi
}

SUBDOMAIN_HASH=""
PATH_SECRET=""
if [[ "${KEEP_URLS}" == "true" && -f "${ENV_FILE}" ]]; then
  SUBDOMAIN_HASH="$(grep -E '^SUBDOMAIN_HASH=' "${ENV_FILE}" | head -n1 | cut -d= -f2- | tr -d "'\" " || true)"
  PATH_SECRET="$(grep -E '^PATH_SECRET=' "${ENV_FILE}" | head -n1 | cut -d= -f2- | tr -d "'\" " || true)"
fi

[[ -z "${SUBDOMAIN_HASH}" ]] && SUBDOMAIN_HASH="$(gen_hex 6)"
[[ -z "${PATH_SECRET}" ]] && PATH_SECRET="$(gen_hex 24)"

mkdir -p "$(dirname "${ENV_FILE}")"
FULL_URL="https://ag-${SUBDOMAIN_HASH}.${DOMAIN}/${PATH_SECRET}/mcp"
TS_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

cat > "${ENV_FILE}" << EOF
# ag-bridge-mcp runtime configuration & secrets
# Generated: ${TS_UTC}
# Gemini Connected Apps URL: ${FULL_URL}

# --- Perimeter & Deadbolt Security ---
SUBDOMAIN_HASH=${SUBDOMAIN_HASH}
PATH_SECRET=${PATH_SECRET}
PASS_HASH=${PASS_HASH}
TTL_SECONDS=${TTL_SECONDS}
BIND_HOST=0.0.0.0
BIND_PORT=8765

# --- Context Window & Pagination Budgets ---
MAX_FILE_CHARS=${MAX_FILE_CHARS}
MAX_TOTAL_FILE_CHARS=${MAX_TOTAL_FILE_CHARS}
MAX_FILES_PER_CALL=${MAX_FILES_PER_CALL}
MAX_DIFF_CHARS=${MAX_DIFF_CHARS}
MAX_TRANSCRIPT_TURNS=${MAX_TRANSCRIPT_TURNS}

# --- Modular Architecture & File Hygiene Standards ---
ENFORCE_MODULAR_HYGIENE=${ENFORCE_MODULAR_HYGIENE}
TARGET_FILE_LINES=${TARGET_FILE_LINES}
HARD_MAX_FILE_LINES=${HARD_MAX_FILE_LINES}
EOF

chmod 600 "${ENV_FILE}"

if [[ "${QUIET}" == "true" ]]; then
  echo "[+] Secrets initialized at ${ENV_FILE} (mode 0600)"
  echo "[+] Deadbolt SHA-256: ${PASS_HASH:0:8}...${PASS_HASH: -6}"
  exit 0
fi

echo ""
echo "======================================================================"
echo " ag-bridge-mcp Configuration & Secrets Initialized "
echo "======================================================================"
echo "[+] Secrets File:      ${ENV_FILE} (chmod 600)"
echo "[+] Subdomain Host:    ag-${SUBDOMAIN_HASH}.${DOMAIN}"
echo "[+] Gemini MCP URL:    ${FULL_URL}"
echo "[+] Deadbolt SHA-256:  ${PASS_HASH:0:12}...${PASS_HASH: -8}"
echo "[+] Session TTL:       ${TTL_SECONDS}s"
echo "[+] File Slice Cap:    ${MAX_FILE_CHARS} chars/file (line-range pagination enabled)"
echo "[+] Diff Page Cap:     ${MAX_DIFF_CHARS} chars/page (offset & per-file pagination enabled)"
echo "[+] Modular Hygiene:   ${ENFORCE_MODULAR_HYGIENE} (<= ${TARGET_FILE_LINES} lines/file target)"
echo "======================================================================"
echo "Next Steps:"
echo "  1. Route DNS / Proxy:  ag-${SUBDOMAIN_HASH}.${DOMAIN} -> http://<host>:8765"
echo "  2. Start Container:    docker compose --env-file ${ENV_FILE} up -d"
echo "  3. In Google Gemini Connected Apps, add Custom MCP URL:"
echo "     ${FULL_URL}"
echo "======================================================================"
