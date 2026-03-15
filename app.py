import os
import gradio as gr
from dotenv import load_dotenv

load_dotenv()  # Load .env if present

# Patch gradio_client schema introspection bug (boolean 'description' fields crash on Python 3.9 + gradio 4.44)
import gradio_client.utils as _gcu
_orig_j2p = _gcu._json_schema_to_python_type
def _safe_j2p(schema, defs):
    try:
        return _orig_j2p(schema, defs)
    except (TypeError, KeyError):
        return "Any"
_gcu._json_schema_to_python_type = _safe_j2p

from interview_agent import start_interview, submit_answer, get_progress, get_summary
from llm_client import get_available_providers, DEFAULT_PROVIDER

# Load API key from environment — falls back to empty string if not set
_ENV_API_KEY = os.getenv("GROQ_API_KEY", "")


def make_progress_md(asked: int, total: int) -> str:
    filled = round(asked / total * 10) if total else 0
    bar = "▓" * filled + "░" * (10 - filled)
    pct = round(asked / total * 100) if total else 0
    return f"**Question {asked} of {total}** &nbsp; `{bar}` {pct}%"


with gr.Blocks(title="AI Interview Coach") as demo:
    state = gr.State(None)

    gr.Markdown("# 🤖 AI Interview Coach")
    gr.Markdown("Practice your interview skills with an AI-powered interviewer tailored to any job description.")
    gr.Markdown("<p style='text-align:right; color:gray; font-size:0.85em;'>Created by Richmond Dzoku</p>")

    # ── Error display ──────────────────────────────────────────────────────────
    error_display = gr.Markdown("", visible=False)

    # ── Setup panel ───────────────────────────────────────────────────────────
    with gr.Group(visible=True) as setup_panel:
        jd_input = gr.Textbox(
            label="Job Description",
            placeholder=(
                "Paste the job description here…\n\n"
                "Example: We are looking for a Senior Backend Engineer with 5+ years of "
                "experience in Python, REST APIs, and cloud infrastructure (AWS/GCP)…"
            ),
            lines=6,
        )
        provider_dropdown = gr.Dropdown(
            choices=get_available_providers(),
            value=DEFAULT_PROVIDER,
            label="LLM Provider",
        )
        api_key_input = gr.Textbox(
            label="API Key",
            type="password",
            placeholder="Enter your API key…",
            value=_ENV_API_KEY,
            visible=not bool(_ENV_API_KEY),  # hidden when loaded from env
        )
        api_key_status = gr.Markdown(
            "🔑 **API key loaded from environment variable.**",
            visible=bool(_ENV_API_KEY),
        )
        start_btn = gr.Button("🚀 Start Interview", variant="primary")
        gr.Markdown(
            "Need a free API key? Get one from "
            "[Groq](https://console.groq.com) (recommended) or "
            "[Google AI Studio](https://aistudio.google.com)",
            visible=not bool(_ENV_API_KEY),
        )

    # ── Progress bar ──────────────────────────────────────────────────────────
    progress_md = gr.Markdown("", visible=False)

    # ── Chatbot (classic tuple format: [[user, bot], ...]) ────────────────────
    chatbot = gr.Chatbot(height=500, label="Interview", visible=False)

    # ── Answer input panel ────────────────────────────────────────────────────
    with gr.Group(visible=False) as answer_panel:
        answer_input = gr.Textbox(
            label="Your Answer",
            lines=4,
            placeholder="Type your answer here…",
        )
        with gr.Row():
            submit_btn = gr.Button("✅ Submit Answer", variant="primary")
            end_btn = gr.Button("⏭️ End Interview", variant="secondary")

    # ── New interview button (shown after completion) ─────────────────────────
    new_interview_btn = gr.Button("🔄 Start New Interview", visible=False)

    # ── Handlers ──────────────────────────────────────────────────────────────

    def handle_start(jd, provider, api_key):
        if not jd.strip():
            yield (
                gr.update(),
                gr.update(value="❌ Please enter a job description.", visible=True),
                gr.update(), gr.update(), gr.update(), gr.update(), gr.update(),
                gr.update(interactive=True, value="🚀 Start Interview"),
            )
            return
        if not api_key.strip():
            yield (
                gr.update(),
                gr.update(value="❌ Please enter your API key.", visible=True),
                gr.update(), gr.update(), gr.update(), gr.update(), gr.update(),
                gr.update(interactive=True, value="🚀 Start Interview"),
            )
            return

        # Loading state
        yield (
            gr.update(),
            gr.update(value="", visible=False),
            gr.update(), gr.update(), gr.update(), gr.update(), gr.update(),
            gr.update(interactive=False, value="⏳ Starting…"),
        )

        try:
            new_state, first_question = start_interview(jd, provider, api_key)
        except Exception as exc:
            yield (
                gr.update(),
                gr.update(value=f"❌ {exc}", visible=True),
                gr.update(visible=True), gr.update(visible=False),
                gr.update(visible=False), gr.update(visible=False),
                gr.update(visible=False),
                gr.update(interactive=True, value="🚀 Start Interview"),
            )
            return

        asked, total = get_progress(new_state)
        # Classic format: [user_msg, bot_msg] — interviewer speaks first, so user=None
        history = [[None, first_question]]

        yield (
            new_state,
            gr.update(value="", visible=False),
            gr.update(visible=False),
            gr.update(value=make_progress_md(asked, total), visible=True),
            gr.update(value=history, visible=True),
            gr.update(visible=True),
            gr.update(visible=False),
            gr.update(interactive=True, value="🚀 Start Interview"),
        )

    start_btn.click(
        handle_start,
        inputs=[jd_input, provider_dropdown, api_key_input],
        outputs=[state, error_display, setup_panel, progress_md, chatbot, answer_panel, new_interview_btn, start_btn],
    )

    def handle_submit(current_state, answer, chat_history):
        if not answer.strip():
            yield (
                current_state,
                gr.update(value="❌ Please type an answer before submitting.", visible=True),
                chat_history, gr.update(), gr.update(), gr.update(), answer,
            )
            return

        try:
            new_state, feedback, next_or_summary = submit_answer(current_state, answer)
        except Exception as exc:
            yield (
                current_state,
                gr.update(value=f"❌ {exc}", visible=True),
                chat_history, gr.update(), gr.update(), gr.update(), answer,
            )
            return

        history = list(chat_history)
        # User answer + feedback as one turn
        history.append([answer, feedback])

        if new_state.phase == "done":
            # Summary as a standalone bot message
            history.append([None, next_or_summary])
            yield (
                new_state,
                gr.update(value="", visible=False),
                history,
                gr.update(value="**Interview Complete ✅**", visible=True),
                gr.update(visible=False),
                gr.update(visible=True),
                "",
            )
        else:
            # Next question as a standalone bot message
            history.append([None, next_or_summary])
            asked, total = get_progress(new_state)
            yield (
                new_state,
                gr.update(value="", visible=False),
                history,
                gr.update(value=make_progress_md(asked, total), visible=True),
                gr.update(visible=True),
                gr.update(visible=False),
                "",
            )

    submit_btn.click(
        handle_submit,
        inputs=[state, answer_input, chatbot],
        outputs=[state, error_display, chatbot, progress_md, answer_panel, new_interview_btn, answer_input],
    )

    def handle_end(current_state, chat_history):
        if current_state is None:
            return (
                current_state,
                gr.update(value="❌ No active interview session.", visible=True),
                chat_history, gr.update(), gr.update(),
            )
        try:
            summary = get_summary(current_state)
        except Exception as exc:
            return (
                current_state,
                gr.update(value=f"❌ {exc}", visible=True),
                chat_history, gr.update(), gr.update(),
            )

        history = list(chat_history)
        history.append([None, summary])
        return (
            current_state,
            gr.update(value="", visible=False),
            history,
            gr.update(visible=False),
            gr.update(visible=True),
        )

    end_btn.click(
        handle_end,
        inputs=[state, chatbot],
        outputs=[state, error_display, chatbot, answer_panel, new_interview_btn],
    )

    def handle_new_interview():
        return (
            None,
            gr.update(value="", visible=False),
            gr.update(visible=True),
            gr.update(value="", visible=False),
            gr.update(value=[], visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
            "", "", "",
        )

    new_interview_btn.click(
        handle_new_interview,
        inputs=[],
        outputs=[
            state, error_display, setup_panel, progress_md, chatbot,
            answer_panel, new_interview_btn, jd_input, api_key_input, answer_input,
        ],
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", show_api=False)
