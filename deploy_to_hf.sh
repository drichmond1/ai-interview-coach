#!/bin/bash
# One-time deployment to HuggingFace Spaces
# Prerequisites:
#   1. Free HuggingFace account: https://huggingface.co/join
#   2. Write token from:         https://huggingface.co/settings/tokens/new?tokenType=write
#   3. After deploying, add secret in HF Space settings:
#      GROQ_API_KEY = your_groq_key
#      (Space URL → Settings → Variables and Secrets)

set -e

HF_USERNAME=${1:-"drichmond1"}
SPACE_NAME="ai-interview-coach"

echo "🚀 Deploying AI Interview Coach to HuggingFace Spaces..."
echo "   Space will be: https://huggingface.co/spaces/$HF_USERNAME/$SPACE_NAME"
echo ""

# Activate venv
cd "$(dirname "$0")"
source .venv/bin/activate

# Deploy (will prompt for HF token if not cached)
gradio deploy --title "$SPACE_NAME" --app-file app.py

echo ""
echo "✅ Deployment complete!"
echo "🌐 Live at: https://huggingface.co/spaces/$HF_USERNAME/$SPACE_NAME"
echo ""
echo "⚠️  Don't forget to add your GROQ_API_KEY secret:"
echo "   → Go to: https://huggingface.co/spaces/$HF_USERNAME/$SPACE_NAME/settings"
echo "   → Variables and Secrets → New Secret"
echo "   → Name: GROQ_API_KEY, Value: your key from https://console.groq.com"
