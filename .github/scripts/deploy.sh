#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# CD Deploy Script — AirteleBots
# Pulls latest code and restarts changed bot services.
# Triggered by GitHub Actions CD workflow via SSH.
#
# Usage: bash .github/scripts/deploy.sh
# ─────────────────────────────────────────────────────────
set -euo pipefail

REPO_DIR="$HOME/airteleBots"
SERVICES=("ytd-bot" "know-bot" "volcabu-bot" "apolloew-bot" "translate-bot" "yt-shadow-bot" "tts-bot")

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Deploying AirteleBots"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. Pull latest code
cd "$REPO_DIR"
echo -e "\n📥 Pulling latest code..."
git pull origin main

# 2. Detect changed bot directories
echo -e "\n🔍 Detecting changed bots..."
CHANGED=$(git diff --name-only HEAD~1 HEAD 2>/dev/null || git diff --name-only HEAD)
echo "Files changed:"
echo "$CHANGED" | head -20

declare -A BOT_RESTARTED
RESTARTED_COUNT=0
for srv in "${SERVICES[@]}"; do
    if echo "$CHANGED" | grep -q "^${srv}/"; then
        echo -e "\n🔄 Restarting $srv..."
        if systemctl --user restart "$srv"; then
            echo "✅ $srv restarted"
            BOT_RESTARTED["$srv"]=true
            RESTARTED_COUNT=$((RESTARTED_COUNT + 1))
        else
            echo "❌ $srv restart FAILED"
        fi
    fi
done

# 3. If shared infrastructure changed, daemon-reload
if echo "$CHANGED" | grep -qE "^\.github/|^\.gitignore|^README"; then
    echo -e "\n🔄 Shared infra changed — daemon-reload not needed (no service files changed)"
fi

# 4. Summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Deploy Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ "$RESTARTED_COUNT" -gt 0 ]; then
    echo "✅ $RESTARTED_COUNT bot(s) restarted: ${!BOT_RESTARTED[*]-}"
else
    echo "ℹ️  No bot services needed restart."
fi

# Verify
echo ""
echo "📊 Fleet status:"
for srv in "${SERVICES[@]}"; do
    active=$(systemctl --user is-active "$srv" 2>/dev/null || echo "unknown")
    icon="🟢"
    [ "$active" != "active" ] && icon="🔴"
    echo "  $icon $srv — $active"
done