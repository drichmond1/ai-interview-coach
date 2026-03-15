#!/usr/bin/env bash
# Deploy AI Interview Coach to Fly.io
#
# Prerequisites (one-time setup — see instructions printed by this script):
#   1. Install flyctl: curl -L https://fly.io/install.sh | sh
#   2. Sign up / log in: fly auth signup  OR  fly auth login
#
# Usage:
#   chmod +x deploy_to_fly.sh
#   ./deploy_to_fly.sh
#
# To set your API key as a secret (so users don't have to enter one):
#   fly secrets set GROQ_API_KEY=gsk_...

set -euo pipefail

APP_NAME="interview-prep-coach"

# ── Preflight checks ──────────────────────────────────────────────────────

if ! command -v fly &>/dev/null && ! command -v flyctl &>/dev/null; then
    echo "❌ Fly CLI not found."
    echo ""
    echo "Install it with:"
    echo "  curl -L https://fly.io/install.sh | sh"
    echo ""
    echo "Then log in:"
    echo "  fly auth signup   # new account (includes free tier)"
    echo "  fly auth login    # existing account"
    exit 1
fi

FLY=$(command -v fly || command -v flyctl)

# Check authentication
if ! $FLY auth whoami &>/dev/null 2>&1; then
    echo "❌ Not logged in to Fly.io."
    echo ""
    echo "Run one of:"
    echo "  fly auth signup   # new account"
    echo "  fly auth login    # existing account"
    exit 1
fi

echo "✅ Fly CLI authenticated as: $($FLY auth whoami)"

# ── Create app if it doesn't exist ────────────────────────────────────────

if $FLY apps list 2>/dev/null | grep -q "$APP_NAME"; then
    echo "✅ App '$APP_NAME' already exists"
else
    echo "📦 Creating app '$APP_NAME'..."
    $FLY apps create "$APP_NAME" --machines || true
fi

# ── Deploy ────────────────────────────────────────────────────────────────

echo ""
echo "🚀 Deploying to Fly.io..."
$FLY deploy --app "$APP_NAME"

echo ""
echo "══════════════════════════════════════════════════════════"
echo "  ✅ Deployed! Your app is live at:"
echo ""
echo "     https://${APP_NAME}.fly.dev"
echo ""
echo "══════════════════════════════════════════════════════════"
echo ""
echo "Useful commands:"
echo "  fly logs -a $APP_NAME              # view logs"
echo "  fly secrets set GROQ_API_KEY=...   # set API key for all users"
echo "  fly status -a $APP_NAME            # check app status"
echo "  fly scale count 1 -a $APP_NAME     # keep always running (no auto-stop)"
echo "  fly apps destroy $APP_NAME         # tear down"
