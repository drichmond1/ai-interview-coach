"""
Google Colab deployment script for AI Interview Coach.

Generates a ready-to-run Colab notebook (.ipynb) that installs dependencies,
uploads the application source files, and launches the Gradio app with a
public shareable link.

Usage (run locally):
    python deploy_to_colab.py

This produces `interview_agent_colab.ipynb` in the current directory.
Upload it to Google Colab and follow the instructions in the notebook.
"""

import json
import base64
import os

# ---------------------------------------------------------------------------
# Source files to bundle into the notebook
# ---------------------------------------------------------------------------
SOURCE_FILES = [
    "llm_client.py",
    "prompts.py",
    "interview_agent.py",
    "app.py",
]

NOTEBOOK_FILENAME = "interview_agent_colab.ipynb"


def _read_source(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _make_code_cell(source_lines: list[str]) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source_lines,
    }


def _make_md_cell(source_lines: list[str]) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": source_lines,
    }


def build_notebook() -> dict:
    cells = []

    # ── Title ──────────────────────────────────────────────────────────────
    cells.append(_make_md_cell([
        "# 🤖 AI Interview Coach — Google Colab Deployment\n",
        "\n",
        "This notebook deploys the AI Interview Coach Gradio app directly in Colab.\n",
        "\n",
        "**Run each cell in order.** The final cell launches the app and prints a\n",
        "public URL you can share with anyone.\n",
        "\n",
        "### Prerequisites\n",
        "- A free API key from one of the supported providers:\n",
        "  - [Groq](https://console.groq.com) (recommended — free tier)\n",
        "  - [Google AI Studio](https://aistudio.google.com)\n",
        "  - [OpenAI](https://platform.openai.com)\n",
        "  - [Anthropic](https://console.anthropic.com)\n",
    ]))

    # ── Cell 1: Install dependencies ──────────────────────────────────────
    cells.append(_make_md_cell([
        "## 1 · Install dependencies\n",
    ]))
    cells.append(_make_code_cell([
        "!pip install -q gradio>=4.0.0 litellm>=1.0.0 openai==2.28.0 httpx==0.28.1 gTTS>=2.5.0 python-dotenv>=1.0.0\n",
    ]))

    # ── Cell 2: (Optional) Set API key via Colab Secrets ──────────────────
    cells.append(_make_md_cell([
        "## 2 · Set your API key (optional)\n",
        "\n",
        "You can enter your API key directly in the app UI, **or** set it here so\n",
        "it's pre-loaded. Using Colab Secrets (🔑 icon in the sidebar) is the\n",
        "safest approach — add a secret named e.g. `GROQ_API_KEY` and toggle\n",
        "\"Notebook access\" on.\n",
        "\n",
        "Alternatively, uncomment and paste your key below.\n",
    ]))
    cells.append(_make_code_cell([
        "import os\n",
        "\n",
        "# Option A — Colab Secrets (recommended)\n",
        "try:\n",
        "    from google.colab import userdata\n",
        "    for key_name in ['GROQ_API_KEY', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'GOOGLE_API_KEY']:\n",
        "        try:\n",
        "            val = userdata.get(key_name)\n",
        "            if val:\n",
        "                os.environ[key_name] = val\n",
        "                print(f'✅ {key_name} loaded from Colab Secrets')\n",
        "        except Exception:\n",
        "            pass\n",
        "except ImportError:\n",
        "    pass\n",
        "\n",
        "# Option B — Paste directly (less secure)\n",
        "# os.environ['GROQ_API_KEY'] = 'gsk_...'  # uncomment and fill in\n",
    ]))

    # ── Cell 3: Write application source files ────────────────────────────
    cells.append(_make_md_cell([
        "## 3 · Write application source files\n",
        "\n",
        "The cells below create each source file in the Colab runtime.\n",
    ]))

    for filename in SOURCE_FILES:
        content = _read_source(filename)
        # Use %%writefile magic to create files cleanly
        escaped = content.replace("\\", "\\\\")
        lines = [f"%%writefile {filename}\n"] + [
            line + "\n" for line in content.split("\n")
        ]
        # Remove trailing extra newline from split
        if lines and lines[-1] == "\n":
            lines[-1] = ""
        cells.append(_make_code_cell(lines))

    # ── Cell 4: Launch the app ────────────────────────────────────────────
    cells.append(_make_md_cell([
        "## 4 · Launch the app 🚀\n",
        "\n",
        "This starts the Gradio server and prints a **public URL** (valid for 72 hours).\n",
        "Share the link with anyone — no Colab access required on their end.\n",
        "\n",
        "⚠️ **Keep this cell running** — closing it stops the app.\n",
    ]))
    cells.append(_make_code_cell([
        "import subprocess, sys, os\n",
        "\n",
        "# Patch the launch call to use share=True for a public Colab link\n",
        "os.environ['GRADIO_SERVER_NAME'] = '0.0.0.0'\n",
        "\n",
        "# Import and launch with share=True for public URL\n",
        "from app import demo\n",
        "demo.launch(share=True, server_name='0.0.0.0')\n",
    ]))

    # ── Assemble notebook ─────────────────────────────────────────────────
    notebook = {
        "nbformat": 4,
        "nbformat_minor": 0,
        "metadata": {
            "colab": {"provenance": [], "name": "AI Interview Coach"},
            "kernelspec": {
                "name": "python3",
                "display_name": "Python 3",
            },
            "language_info": {"name": "python", "version": "3.10.0"},
        },
        "cells": cells,
    }
    return notebook


def main():
    notebook = build_notebook()

    with open(NOTEBOOK_FILENAME, "w", encoding="utf-8") as f:
        json.dump(notebook, f, indent=1, ensure_ascii=False)

    print(f"✅ Notebook generated: {NOTEBOOK_FILENAME}")
    print()
    print("Next steps:")
    print("  1. Go to https://colab.research.google.com")
    print("  2. File → Upload notebook → select interview_agent_colab.ipynb")
    print("  3. (Optional) Add your API key to Colab Secrets (🔑 sidebar icon):")
    print("     - Secret name: GROQ_API_KEY  |  Value: your key  |  Toggle 'Notebook access' on")
    print("  4. Runtime → Run all")
    print("  5. The last cell prints a public *.gradio.live URL — share it with anyone")
    print()
    print("Notes:")
    print("  • The public link is valid for 72 hours per Gradio's free tunnel")
    print("  • The app stays live as long as the Colab runtime is running")
    print("  • Free Colab runtimes disconnect after ~90 min of inactivity")
    print("  • Use Colab Pro for longer-lived sessions if needed")


if __name__ == "__main__":
    main()
