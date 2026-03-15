---
title: ai-interview-coach
emoji: 🤖
colorFrom: blue
colorTo: indigo
sdk: gradio
app_file: app.py
pinned: false
---

# AI Interview Coach

> Paste a job description, get asked a realistic number of interview questions, receive structured feedback per answer, and a final summary with a hire / no-hire recommendation — all powered by LLMs via Groq, OpenAI, Anthropic, or Google Gemini. Deploy for free on HuggingFace Spaces.

---

## Overview

**AI Interview Coach** is an interactive mock-interview web application built with [Gradio](https://gradio.app). You paste a job description, the app analyses the role and generates a tailored set of interview questions, then conducts the interview one question at a time. After each answer you receive immediate, structured feedback (strengths, areas to improve, score). When the interview is complete you get a final summary report with an overall hire / no-hire recommendation.

Key characteristics:
- **Realistic question count** — the number of questions is derived from the job description, not hard-coded.
- **Multi-provider LLM support** — switch between Groq (free), OpenAI, Anthropic Claude, or Google Gemini from the UI without touching code.
- **Voice-enabled interview flow** — speak answers via microphone transcription and hear interviewer responses read aloud.
- **Free default** — the default provider is Groq (Llama 3.3-70B), which requires no credit card.
- **Free cloud hosting** — one-command push to HuggingFace Spaces for a permanent public URL.

---

## Screenshots / UI Description

The app has a **two-stage UI**:

### Stage 1 — Setup Panel
When you first open the app you see the setup panel:
- **Job Description** — a large text area where you paste the full JD.
- **LLM Provider** — a dropdown to choose Groq / OpenAI / Anthropic / Gemini.
- **API Key** — a password field for the chosen provider's key.
- **Start Interview** button — analyses the JD and transitions to the chat stage.

A progress bar and status message keep you informed while the job description is being analysed.

### Stage 2 — Interview Chatbot
Once the interview starts the setup panel collapses and a full-screen chat interface appears:
- The AI interviewer greets you and asks the first question.
- You type your answer in the chat input and press Enter (or click Send).
- After each answer the AI returns **structured feedback**: what you did well, what to improve, and a score out of 10.
- You can **record your answer** and transcribe it to text (currently supported for Groq/OpenAI providers).
- The interviewer response is also available as **audio playback** after each AI message.
- A small **progress indicator** shows `Question X of Y` so you always know where you are.
- After the final question the AI produces a **summary report**: overall score, hire / no-hire recommendation, top strengths, and key development areas.

---

## Prerequisites & Sign-ups

| Service | URL | Required? | Purpose | Notes |
|---|---|---|---|---|
| **Groq** | [console.groq.com](https://console.groq.com) | ✅ Required (default) | Free LLM API | Llama 3.3-70B; no credit card needed |
| **HuggingFace** | [huggingface.co](https://huggingface.co) | ✅ For cloud deploy | Free Spaces hosting | Skip if only running locally |
| **Google AI Studio** | [aistudio.google.com](https://aistudio.google.com) | Optional | Gemini 1.5 Flash | Free tier available |
| **OpenAI** | [platform.openai.com](https://platform.openai.com) | Optional | GPT-4o | Paid; requires billing setup |
| **Anthropic** | [console.anthropic.com](https://console.anthropic.com) | Optional | Claude 3.5 Sonnet | Paid; requires billing setup |

---

## Local Development

### 1. Clone / download

```bash
git clone <repo-url>
cd interview-agent
```

### 2. Create virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure API keys

```bash
cp .env.example .env
# Edit .env and add your Groq API key (minimum required)
```

### 4. Run the app

```bash
python3 app.py
```

- **Local URL**: http://127.0.0.1:7860

> To share a temporary public URL, set `share=True` in `demo.launch()` in `app.py`. The link is valid for **72 hours**.

---

## Switching LLM Providers

**From the UI**: use the **LLM Provider** dropdown and enter the corresponding API key. No code changes needed.

**To change the default provider in code**: edit `llm_client.py` and change:
```python
DEFAULT_PROVIDER = "groq"   # change to "openai", "anthropic", or "gemini"
```

**To add a new provider**: add one entry to the `PROVIDERS` dict and one to the `_API_KEY_ENV_VARS` dict in `llm_client.py`.

---

## HuggingFace Spaces Deployment (Free, Permanent)

### Step-by-step

1. **Sign up** at [huggingface.co](https://huggingface.co).

2. **Create a new Space**:
   - Click **New Space**
   - Name it (e.g. `ai-interview-coach`)
   - SDK: **Gradio**
   - Hardware: **CPU Basic (free)**
   - Click **Create Space**

3. **Add API key secrets** (never commit keys to code):
   - Go to your Space page → **Settings** → **Variables and Secrets** → **New Secret**
   - Add `GROQ_API_KEY` (and any other provider keys you want pre-loaded)

4. **Push your code**:

   ```bash
   # Option A: via git (recommended)
   git init
   git remote add space https://huggingface.co/spaces/YOUR_USERNAME/ai-interview-coach
   git add .
   git commit -m "Initial commit"
   git push space main

   # Option B: Upload files via the web UI on the Space page
   ```

5. HuggingFace will **auto-install** `requirements.txt` and start the app. Watch the **Logs** tab for build progress.

6. Your app is live at:
   ```
   https://huggingface.co/spaces/YOUR_USERNAME/ai-interview-coach
   ```

### Note on API keys in Spaces

The app reads API keys from the UI input field. Users can enter their own keys on the page. If you want a **pre-loaded key** (so users don't need their own), set the HF Secret and modify `app.py` to use `os.getenv("GROQ_API_KEY", "")` as the default value for the API key textbox.

---

## Project Structure

```
interview-agent/
├── app.py                  Gradio UI (setup panel + chatbot + progress)
├── interview_agent.py      Interview state machine
├── llm_client.py           Multi-provider LLM abstraction (litellm)
├── prompts.py              All prompt templates
├── requirements.txt        Python dependencies
├── .env.example            API key template (copy to .env)
└── README.md               This file
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| **"Failed to analyse job description"** | Check your API key is correct and has remaining quota |
| **Groq rate limit hit** | Groq free tier is generous, but if you hit it wait ~60 s or switch to Gemini |
| **HF Space not starting** | Open the **Logs** tab on the Space page — usually a missing or mis-spelled requirement |
| **`NotOpenSSLWarning` on startup** | Harmless warning on macOS with LibreSSL — the app runs fine, ignore it |
