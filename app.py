import logging
import os
import gradio as gr
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

load_dotenv()  # Load .env if present

# Gradio 4.x requires type="messages" for OpenAI-style chat dicts; Gradio 5.x removed the param.
_GR_MAJOR = int(gr.__version__.split(".")[0])

# Patch gradio_client schema parser to handle boolean JSON schemas (pydantic v2 compat)
try:
    import gradio_client.utils as _gcu
    _orig_json_schema = _gcu._json_schema_to_python_type

    def _patched_json_schema(schema, defs):
        if isinstance(schema, bool):
            return "Any" if schema else "None"
        return _orig_json_schema(schema, defs)

    _gcu._json_schema_to_python_type = _patched_json_schema
except Exception:
    pass

from interview_agent import start_interview, handle_response, get_progress, get_summary
from llm_client import (
    DEFAULT_PROVIDER,
    get_api_key,
    get_available_providers,
    synthesize_speech,
    transcribe_audio,
)


def make_progress_md(asked: int) -> str:
    return f"**Questions asked: {asked}**"


def _msg(role: str, content: str) -> dict:
    """Helper to build a gradio 6 messages-format chat entry."""
    return {"role": role, "content": content}


def _voice_update_for_text(text: str) -> tuple[dict, str]:
    """Generate audio update payload for interviewer text."""
    try:
        audio_path = synthesize_speech(text)
        return gr.update(value=audio_path, visible=True), ""
    except Exception as exc:
        return gr.update(value=None, visible=False), f"⚠️ Voice playback unavailable: {exc}"


with gr.Blocks(title="AI Interview Coach") as demo:
    state = gr.State(None)

    gr.Markdown("# 🤖 AI Interview Coach")
    gr.Markdown("Practice your interview skills with an AI-powered interviewer tailored to any job description.")
    gr.Markdown("<p style='text-align:right; color:gray; font-size:0.85em;'>Created by Richmond Dzoku</p>")

    error_display = gr.Markdown("", visible=False)

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
        resume_input = gr.Textbox(
            label="Resume (optional)",
            placeholder="Paste your resume here to get personalized feedback…",
            lines=4,
        )
        difficulty_dropdown = gr.Dropdown(
            choices=["Easy", "Medium", "Hard"],
            value="Medium",
            label="Difficulty Level",
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
            value="",
            visible=not bool(get_api_key(DEFAULT_PROVIDER)),
        )
        api_key_status = gr.Markdown(
            "🔑 **API key loaded from environment variable.**",
            visible=bool(get_api_key(DEFAULT_PROVIDER)),
        )
        start_btn = gr.Button("🚀 Start Interview", variant="primary")
        gr.Markdown(
            "Need a free API key? Get one from "
            "[Groq](https://console.groq.com) (recommended) or "
            "[Google AI Studio](https://aistudio.google.com)",
            visible=not bool(get_api_key(DEFAULT_PROVIDER)),
        )

    # ── Provider change: update API key field dynamically ─────────────────────

    def handle_provider_change(provider):
        env_key = get_api_key(provider)
        has_key = bool(env_key)
        return (
            gr.update(visible=not has_key, value=""),
            gr.update(visible=has_key),
        )

    provider_dropdown.change(
        handle_provider_change,
        inputs=[provider_dropdown],
        outputs=[api_key_input, api_key_status],
    )

    progress_md = gr.Markdown("", visible=False)

    chatbot = gr.Chatbot(height=500, label="Interview", visible=False, **({} if _GR_MAJOR >= 5 else {"type": "messages"}))
    interviewer_audio = gr.Audio(
        label="🔊 Interviewer Voice",
        visible=False,
        autoplay=True,
    )

    with gr.Group(visible=False) as answer_panel:
        answer_input = gr.Textbox(label="Your Response", lines=4, placeholder="Type your answer or ask a clarifying question…")
        speech_input = gr.Audio(
            label="🎤 Speak Your Answer (optional)",
            sources=["microphone", "upload"],
            type="filepath",
        )
        with gr.Row():
            transcribe_btn = gr.Button("📝 Transcribe Speech", variant="secondary")
            submit_btn = gr.Button("✅ Submit", variant="primary")
            end_btn = gr.Button("⏭️ End Interview", variant="secondary")

    new_interview_btn = gr.Button("🔄 Start New Interview", visible=False)

    # ── Handlers ──────────────────────────────────────────────────────────────

    def handle_start(jd, resume, difficulty, provider, api_key):
        if not jd.strip():
            logger.warning("Start interview attempted with empty job description")
            yield (gr.update(), gr.update(value="❌ Please enter a job description.", visible=True),
                   gr.update(), gr.update(), gr.update(), gr.update(), gr.update(),
                   gr.update(interactive=True, value="🚀 Start Interview"), gr.update())
            return

        api_key = (api_key or "").strip()
        resolved_key = api_key or get_api_key(provider)
        if not resolved_key:
            logger.warning("Start interview attempted without API key for provider=%s", provider)
            yield (gr.update(), gr.update(value="❌ Please enter your API key.", visible=True),
                   gr.update(), gr.update(), gr.update(), gr.update(), gr.update(),
                   gr.update(interactive=True, value="🚀 Start Interview"), gr.update())
            return
        yield (gr.update(), gr.update(value="", visible=False),
               gr.update(), gr.update(), gr.update(), gr.update(), gr.update(),
               gr.update(interactive=False, value="⏳ Starting…"),
               gr.update(value=None, visible=False))

        logger.info("Starting interview: provider=%s difficulty=%s jd_length=%d resume_length=%d",
                     provider, difficulty, len(jd), len((resume or "")))
        try:
            new_state, first_question = start_interview(
                jd, provider, resolved_key,
                resume=(resume or "").strip(),
                difficulty=(difficulty or "Medium").lower(),
            )
        except Exception as exc:
            logger.error("Interview start failed: %s", exc)
            yield (gr.update(), gr.update(value=f"❌ {exc}", visible=True),
                   gr.update(visible=True), gr.update(visible=False),
                   gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),
                   gr.update(interactive=True, value="🚀 Start Interview"),
                   gr.update(value=None, visible=False))
            return

        asked = get_progress(new_state)
        history = [_msg("assistant", first_question)]
        voice_update, voice_warning = _voice_update_for_text(first_question)
        error_update = (
            gr.update(value=voice_warning, visible=True)
            if voice_warning
            else gr.update(value="", visible=False)
        )

        yield (new_state, error_update,
               gr.update(visible=False),
               gr.update(value=make_progress_md(asked), visible=True),
               gr.update(value=history, visible=True),
               gr.update(visible=True), gr.update(visible=False),
               gr.update(interactive=True, value="🚀 Start Interview"),
               voice_update)

    start_btn.click(
        handle_start,
        inputs=[jd_input, resume_input, difficulty_dropdown, provider_dropdown, api_key_input],
        outputs=[state, error_display, setup_panel, progress_md, chatbot, answer_panel, new_interview_btn, start_btn, interviewer_audio],
    )

    def handle_transcribe(audio_path, provider, api_key):
        if not audio_path:
            logger.warning("Transcribe attempted with no audio file")
            return (
                gr.update(),
                gr.update(value="❌ Please record or upload audio before transcribing.", visible=True),
                gr.update(),
            )

        resolved_key = (api_key or "").strip() or get_api_key(provider)
        if not resolved_key:
            return (
                gr.update(),
                gr.update(value="❌ Please enter your API key before transcribing.", visible=True),
                gr.update(),
            )

        logger.info("Transcribing audio: provider=%s path=%s", provider, audio_path)
        try:
            transcript = transcribe_audio(audio_path, provider, resolved_key)
        except Exception as exc:
            logger.error("Transcription failed in UI handler: %s", exc)
            return (
                gr.update(),
                gr.update(value=f"❌ Speech transcription failed: {exc}", visible=True),
                gr.update(),
            )

        logger.info("Transcription successful in UI handler")
        return (
            gr.update(value=transcript),
            gr.update(value="", visible=False),
            gr.update(value=None),
        )

    transcribe_btn.click(
        handle_transcribe,
        inputs=[speech_input, provider_dropdown, api_key_input],
        outputs=[answer_input, error_display, speech_input],
    )

    def handle_submit(current_state, answer, audio_path, chat_history, provider, api_key):
        # Auto-transcribe if user has audio but no typed text
        if not answer.strip() and audio_path:
            logger.info("Auto-transcribing audio before submit")
            resolved_key = (api_key or "").strip() or get_api_key(provider)
            if not resolved_key:
                yield (current_state, gr.update(value="❌ Please enter your API key.", visible=True),
                       chat_history, gr.update(), gr.update(), gr.update(), answer, gr.update(), gr.update())
                return
            try:
                answer = transcribe_audio(audio_path, provider, resolved_key)
            except Exception as exc:
                logger.error("Auto-transcription failed: %s", exc)
                yield (current_state, gr.update(value=f"❌ Speech transcription failed: {exc}", visible=True),
                       chat_history, gr.update(), gr.update(), gr.update(), answer, gr.update(), gr.update())
                return

        if not answer.strip():
            logger.warning("Submit attempted with empty response")
            yield (current_state, gr.update(value="❌ Please type a response or record audio before submitting.", visible=True),
                   chat_history, gr.update(), gr.update(), gr.update(), answer, gr.update(), gr.update())
            return

        logger.info("Processing candidate response, length=%d chars", len(answer.strip()))
        try:
            new_state, response_type, reply, next_q = handle_response(current_state, answer)
        except Exception as exc:
            logger.error("Response handling failed: %s", exc)
            yield (current_state, gr.update(value=f"❌ {exc}", visible=True),
                   chat_history, gr.update(), gr.update(), gr.update(), answer, gr.update(), gr.update())
            return

        history = list(chat_history)
        history.append(_msg("user", answer))
        logger.info("Response processed: type=%s", response_type)

        if response_type == "clarifying":
            history.append(_msg("assistant", reply))
            voice_update, voice_warning = _voice_update_for_text(reply)
            error_update = (
                gr.update(value=voice_warning, visible=True)
                if voice_warning
                else gr.update(value="", visible=False)
            )
            yield (new_state, error_update, history,
                   gr.update(), gr.update(visible=True), gr.update(visible=False),
                   "", None, voice_update)
        else:
            history.append(_msg("assistant", reply))
            history.append(_msg("assistant", next_q))
            asked = get_progress(new_state)
            voice_text = f"{reply}\n\n{next_q}"
            voice_update, voice_warning = _voice_update_for_text(voice_text)
            error_update = (
                gr.update(value=voice_warning, visible=True)
                if voice_warning
                else gr.update(value="", visible=False)
            )
            yield (new_state, error_update, history,
                   gr.update(value=make_progress_md(asked), visible=True),
                   gr.update(visible=True), gr.update(visible=False), "", None, voice_update)

    submit_btn.click(
        handle_submit,
        inputs=[state, answer_input, speech_input, chatbot, provider_dropdown, api_key_input],
        outputs=[state, error_display, chatbot, progress_md, answer_panel, new_interview_btn, answer_input, speech_input, interviewer_audio],
    )

    def handle_end(current_state, chat_history):
        if current_state is None:
            logger.warning("End interview attempted with no active session")
            return (current_state, gr.update(value="❌ No active interview session.", visible=True),
                    chat_history, gr.update(), gr.update(), gr.update())
        logger.info("Ending interview: questions_answered=%d", len(current_state.answers))
        try:
            summary = get_summary(current_state)
        except Exception as exc:
            logger.error("Summary generation failed in UI handler: %s", exc)
            return (current_state, gr.update(value=f"❌ {exc}", visible=True),
                    chat_history, gr.update(), gr.update(), gr.update())

        history = list(chat_history)
        history.append(_msg("assistant", summary))
        voice_update, voice_warning = _voice_update_for_text(summary)
        error_update = (
            gr.update(value=voice_warning, visible=True)
            if voice_warning
            else gr.update(value="", visible=False)
        )
        return (current_state, error_update, history,
                gr.update(visible=False), gr.update(visible=True), voice_update)

    end_btn.click(
        handle_end,
        inputs=[state, chatbot],
        outputs=[state, error_display, chatbot, answer_panel, new_interview_btn, interviewer_audio],
    )

    def handle_new_interview():
        logger.info("Starting new interview session (reset)")
        return (None, gr.update(value="", visible=False), gr.update(visible=True),
                gr.update(value="", visible=False), gr.update(value=[], visible=False),
                gr.update(visible=False), gr.update(visible=False), "", "", "", "", None, gr.update(value=None, visible=False))

    new_interview_btn.click(
        handle_new_interview,
        inputs=[],
        outputs=[state, error_display, setup_panel, progress_md, chatbot,
                 answer_panel, new_interview_btn, jd_input, resume_input, api_key_input, answer_input, speech_input, interviewer_audio],
    )

if __name__ == "__main__":
    is_deployed = os.getenv("SPACE_ID") or os.getenv("FLY_ALLOC_ID") or os.getenv("FLY_APP_NAME")
    server_name = "0.0.0.0" if is_deployed else "127.0.0.1"
    demo.launch(server_name=server_name, server_port=7860)
