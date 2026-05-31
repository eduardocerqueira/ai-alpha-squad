#!/usr/bin/env bash
# Check AI Alpha Squad infrastructure prerequisites (no secrets printed).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'
ok() { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}!${NC} $1"; }
fail() { echo -e "${RED}✗${NC} $1"; }

echo "AI Alpha Squad — prerequisite check"
echo "Repo: $ROOT"
echo

# --- Files ---
if [[ -f .env ]]; then
  ok ".env exists"
  set -a
  # shellcheck disable=SC1091
  source .env 2>/dev/null || warn ".env present but could not source (check syntax)"
  set +a
else
  warn ".env missing — copy from .env.example"
fi

if [[ -f .agents/squad-config.yaml ]]; then
  ok "squad-config.yaml exists"
else
  warn "squad-config.yaml missing (optional) — copy from .agents/squad-config.example.yaml"
fi

# --- CLI tools ---
if command -v gh >/dev/null 2>&1; then
  if gh auth status >/dev/null 2>&1; then
    ok "GitHub CLI authenticated"
  else
    fail "GitHub CLI not authenticated — run: gh auth login"
  fi
else
  fail "gh not installed"
fi

if command -v npx >/dev/null 2>&1; then
  ok "npx available (skills CLI)"
else
  warn "npx not found — needed for npx skills"
fi

if command -v wrangler >/dev/null 2>&1; then
  if wrangler whoami >/dev/null 2>&1; then
    ok "Wrangler authenticated"
  else
    warn "Wrangler installed but not logged in — wrangler login or CLOUDFLARE_API_TOKEN"
  fi
else
  warn "wrangler not installed (optional until Cloudflare work)"
fi

if command -v hf >/dev/null 2>&1; then
  if hf auth whoami >/dev/null 2>&1; then
    ok "Hugging Face CLI authenticated"
  else
    warn "hf installed but not logged in — hf auth login or HF_TOKEN"
  fi
else
  warn "hf not installed (optional until HF work)"
fi

# --- Env vars (presence only) ---
check_env() {
  local name=$1
  local required=${2:-optional}
  if [[ -n "${!name:-}" ]]; then
    ok "$name is set"
  elif [[ "$required" == "required" ]]; then
    fail "$name is not set (required)"
  else
    warn "$name is not set (optional)"
  fi
}

echo
echo "Environment variables (from .env if loaded):"

check_env GITHUB_OWNER optional
check_env SQUAD_WORK_QUEUE_REPO optional
check_env GITHUB_TOKEN optional

echo "--- WhatsApp (optional channel) ---"
check_env WHATSAPP_DIRECTOR_PHONE optional
check_env WHATSAPP_PHONE_NUMBER_ID optional
check_env WHATSAPP_ACCESS_TOKEN optional

echo "--- Cloudflare (optional until used) ---"
check_env CLOUDFLARE_API_TOKEN optional
check_env CLOUDFLARE_ACCOUNT_ID optional

echo "--- Hugging Face (optional until used) ---"
check_env HF_TOKEN optional

echo "--- VS Code publish (job 1) ---"
check_env VSCE_PAT optional
check_env OPENVSX_PAT optional

echo "--- Apple (job 3) ---"
check_env APP_STORE_CONNECT_KEY_ID optional

# --- Skills ---
echo
if [[ -d .agents/skills/whatsapp-director ]]; then
  ok "Squad skill whatsapp-director present"
else
  warn "whatsapp-director skill missing"
fi

count=$(find .agents/skills -maxdepth 1 -mindepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')
if [[ "${count:-0}" -gt 0 ]]; then
  ok "$count skill(s) under .agents/skills/"
else
  warn "No skills in .agents/skills — run ./.agents/skills-install.sh"
fi

echo
echo "Done. Full setup: .agents/infrastructure-prerequisites.md"
