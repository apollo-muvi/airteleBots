#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# Pre-Push Security Scan — AirteleBots
# Scans a bot directory for hardcoded tokens, .env leaks,
# and missing .gitignore coverage.
#
# Usage: bash .github/scripts/security-scan.sh <bot-dir>
# Example: bash .github/scripts/security-scan.sh ytd-bot/
# ─────────────────────────────────────────────────────────
set -euo pipefail

BOT_DIR="${1:-.}"
BOT_NAME="$(basename "$BOT_DIR")"
HAS_ERRORS=0
HAS_WARNINGS=0

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Security Scan: $BOT_NAME"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. Hardcoded tokens in Python files ──
echo -e "\n${YELLOW}[1/4] Scanning for hardcoded tokens...${NC}"
VIOLATIONS=$(grep -rn 'TELEGRAM_BOT_TOKEN\|BOT_TOKEN\|TOKEN\s*=\|API_KEY\s*=\|API_SECRET\s*=' \
  "$BOT_DIR" --include='*.py' --exclude-dir=venv --exclude-dir=__pycache__ \
  | grep -v 'os\.environ\|os\.getenv\|os\.environ\.get\|load_dotenv\|\.env\.example' \
  | grep -v 'print.*TOKEN\|print.*token\|print.*API_KEY' \
  | grep -v '_SUPPORTED_INSERTIONS\|_TOKEN\|TOKEN_' \
  || true)

if [ -n "$VIOLATIONS" ]; then
  echo -e "${RED}❌ Possible hardcoded tokens found:${NC}"
  echo "$VIOLATIONS"
  HAS_ERRORS=1
else
  echo -e "${GREEN}✅ No hardcoded tokens detected${NC}"
fi

# ── 2. Check .env not git-tracked ──
echo -e "\n${YELLOW}[2/4] Checking .env not tracked by git...${NC}"
if [ -f "$BOT_DIR/.env" ]; then
  TRACKED=$(git ls-files --error-unmatch "$BOT_DIR/.env" 2>/dev/null || true)
  if [ -n "$TRACKED" ]; then
    echo -e "${RED}❌ .env is git-tracked! Remove with: git rm --cached $BOT_DIR/.env${NC}"
    HAS_ERRORS=1
  else
    echo -e "${GREEN}✅ .env present but not git-tracked${NC}"
  fi
else
  echo -e "${GREEN}✅ No .env file (expected — .env is gitignored)${NC}"
fi

# ── 3. Verify .gitignore covers .env ──
echo -e "\n${YELLOW}[3/4] Checking .gitignore coverage...${NC}"
REQUIRED_PATTERNS=(".env" "venv/" "__pycache__/" "*.db" "token.json" "credentials.json")
for pattern in "${REQUIRED_PATTERNS[@]}"; do
  if grep -q "^${pattern}$" .gitignore 2>/dev/null; then
    : # ok
  elif grep -q "**/${pattern}$" .gitignore 2>/dev/null; then
    : # ok
  elif grep -q "${pattern}" .gitignore 2>/dev/null; then
    : # ok — pattern found somewhere
  else
    echo -e "${YELLOW}⚠️  Missing in .gitignore: $pattern${NC}"
    HAS_WARNINGS=1
  fi
done
if [ "$HAS_WARNINGS" -eq 0 ]; then
  echo -e "${GREEN}✅ .gitignore covers all required patterns${NC}"
fi

# ── 4. Check .env.example exists ──
echo -e "\n${YELLOW}[4/4] Checking .env.example exists...${NC}"
if [ -f "$BOT_DIR/.env.example" ]; then
  echo -e "${GREEN}✅ $BOT_DIR/.env.example present${NC}"
else
  echo -e "${YELLOW}⚠️  Missing $BOT_DIR/.env.example${NC}"
  HAS_WARNINGS=1
fi

# ── Summary ──
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ "$HAS_ERRORS" -gt 0 ]; then
  echo -e "${RED}❌ Security scan FAILED — fix errors above${NC}"
  exit 1
elif [ "$HAS_WARNINGS" -gt 0 ]; then
  echo -e "${YELLOW}⚠️  Security scan PASSED with warnings${NC}"
  exit 0
else
  echo -e "${GREEN}✅ Security scan PASSED${NC}"
  exit 0
fi