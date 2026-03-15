#!/bin/bash
# One-time deployment to HuggingFace Spaces
# Prerequisites:
#   1. Free HuggingFace account: https://huggingface.co/join
#   2. Write token from:         https://huggingface.co/settings/tokens/new?tokenType=write
#      Add it to your .env file as: HF_TOKEN=hf_...
#   3. After deploying, add secret in HF Space settings:
#      GROQ_API_KEY = your_groq_key
#      (Space URL → Settings → Variables and Secrets)

set -e

SPACE_NAME="ai-interview-coach"

cd "$(dirname "$0")"

# Ensure the virtual environment exists
if [ ! -f ".venv/bin/activate" ]; then
  echo "❌ Virtual environment not found. Run first:"
  echo "   python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

source .venv/bin/activate

# Suppress the noisy urllib3/LibreSSL warning that appears on macOS
export PYTHONWARNINGS="ignore:::urllib3"

# Load HF_TOKEN from .env if not already set in the environment
if [ -z "$HF_TOKEN" ] && [ -f ".env" ]; then
  export HF_TOKEN=$(grep -E '^HF_TOKEN=' .env | cut -d '=' -f2-)
fi

if [ -z "$HF_TOKEN" ]; then
  echo "⚠️  No HF_TOKEN found. gradio deploy will prompt you to log in interactively."
  echo "   To skip the prompt, add HF_TOKEN=hf_... to your .env file."
  echo ""
fi

# Resolve HF username from the token (or cached login)
HF_USERNAME=$(huggingface-cli whoami 2>/dev/null | head -1) || true

echo "🚀 Deploying AI Interview Coach to HuggingFace Spaces..."
if [ -n "$HF_USERNAME" ]; then
  echo "   Space will be: https://huggingface.co/spaces/$HF_USERNAME/$SPACE_NAME"
fi
echo ""

# Deploy
gradio deploy --title "$SPACE_NAME" --app-file app.py

echo ""
echo "✅ Deployment complete!"
echo ""
echo "⚠️  Don't forget to add your GROQ_API_KEY secret:"
if [ -n "$HF_USERNAME" ]; then
  echo "   → Go to: https://huggingface.co/spaces/$HF_USERNAME/$SPACE_NAME/settings"
fi
echo "   → Variables and Secrets → New Secret"
echo "   → Name: GROQ_API_KEY, Value: your key from https://console.groq.com"
