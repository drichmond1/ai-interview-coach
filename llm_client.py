import logging
import os
import tempfile
from typing import Optional
import litellm
from openai import OpenAI
from gtts import gTTS

logger = logging.getLogger(__name__)

PROVIDERS = {
    "groq": "groq/llama-3.3-70b-versatile",
    "openai": "gpt-4o",
    "anthropic": "claude-3-5-sonnet-20241022",
    "gemini": "gemini/gemini-1.5-flash",
}

DEFAULT_PROVIDER = "groq"

_API_KEY_ENV_VARS = {
    "groq": "GROQ_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GOOGLE_API_KEY",
}

_GROQ_TRANSCRIPTION_BASE_URL = "https://api.groq.com/openai/v1"
_TRANSCRIPTION_MODELS = {
    "openai": "whisper-1",
    "groq": "whisper-large-v3-turbo",
}


def get_available_providers() -> list[str]:
    """Return list of supported provider names (for UI dropdown)."""
    return list(PROVIDERS.keys())


def validate_provider(provider: str) -> bool:
    """Return True if provider is known, False otherwise."""
    return provider in PROVIDERS


def get_api_key(provider: str) -> str:
    """Return the API key for the given provider loaded from the environment."""
    env_var = _API_KEY_ENV_VARS.get(provider, "")
    return os.getenv(env_var, "") if env_var else ""


def transcribe_audio(
    audio_path: str,
    provider: str,
    api_key: Optional[str] = None,
) -> str:
    """
    Transcribe an audio file to text.

    Supports OpenAI and Groq (OpenAI-compatible audio transcription API).
    """
    if not audio_path:
        raise ValueError("No audio file provided for transcription.")
    if provider not in _TRANSCRIPTION_MODELS:
        raise ValueError(
            "Speech transcription currently supports 'groq' and 'openai' providers."
        )

    resolved_key = api_key or get_api_key(provider)
    if not resolved_key:
        env_var = _API_KEY_ENV_VARS[provider]
        raise ValueError(
            f"No API key found for provider '{provider}'. "
            f"Set {env_var} in your .env file or enter it manually."
        )

    model = _TRANSCRIPTION_MODELS[provider]
    client_kwargs = {"api_key": resolved_key}
    if provider == "groq":
        client_kwargs["base_url"] = _GROQ_TRANSCRIPTION_BASE_URL

    logger.info("Transcribing audio via provider=%s model=%s path=%s", provider, model, audio_path)
    try:
        client = OpenAI(**client_kwargs)
        with open(audio_path, "rb") as audio_file:
            response = client.audio.transcriptions.create(model=model, file=audio_file)
        transcript = (response.text or "").strip()
        if not transcript:
            raise RuntimeError("Transcription returned empty text.")
        logger.info("Transcription successful, length=%d chars", len(transcript))
        return transcript
    except Exception as exc:
        logger.error("Transcription failed for provider=%s: %s", provider, exc)
        raise RuntimeError(
            f"Speech transcription failed for provider '{provider}': {exc}"
        ) from exc


def synthesize_speech(text: str) -> str:
    """Generate speech audio (mp3) for a text string and return the output filepath."""
    cleaned = (text or "").strip()
    if not cleaned:
        raise ValueError("No text provided for speech synthesis.")

    logger.info("Synthesizing speech, text_length=%d chars", len(cleaned))
    try:
        tts = gTTS(text=cleaned, lang="en")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
            out_path = tmp.name
        tts.save(out_path)
        logger.info("Speech synthesis complete, output=%s", out_path)
        return out_path
    except Exception as exc:
        logger.error("Speech synthesis failed: %s", exc)
        raise RuntimeError(f"Speech synthesis failed: {exc}") from exc


def _chat_openai(
    messages: list[dict],
    model: str,
    api_key: str,
    temperature: float,
) -> str:
    """Call OpenAI directly to avoid provider-adapter issues in some runtimes."""
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("OpenAI API returned an empty response.")
    return content


def chat(
    messages: list[dict],
    provider: str,
    api_key: Optional[str] = None,
    temperature: float = 0.9,
) -> str:
    """
    Call the specified LLM provider and return the assistant's reply as a string.

    Args:
        messages:    OpenAI-style message list, e.g. [{"role": "user", "content": "Hi"}]
        provider:    One of the keys in PROVIDERS (e.g. "groq", "openai")
        api_key:     API key for the chosen provider. When omitted or empty the
                     key is loaded automatically from the corresponding environment
                     variable defined in _API_KEY_ENV_VARS.
        temperature: Sampling temperature (default 0.9)

    Returns:
        The content string from the first response choice.

    Raises:
        ValueError:    If provider is not in PROVIDERS or no API key is available.
        RuntimeError:  If the API call fails for any reason.
    """
    if not validate_provider(provider):
        raise ValueError(
            f"Unknown provider '{provider}'. "
            f"Available providers: {get_available_providers()}"
        )

    resolved_key = api_key or get_api_key(provider)
    if not resolved_key:
        env_var = _API_KEY_ENV_VARS[provider]
        raise ValueError(
            f"No API key found for provider '{provider}'. "
            f"Set {env_var} in your .env file or enter it manually."
        )

    model = PROVIDERS[provider]

    logger.info("LLM chat request: provider=%s model=%s temperature=%.2f messages=%d", provider, model, temperature, len(messages))
    try:
        if provider == "openai":
            result = _chat_openai(messages, model, resolved_key, temperature)
            logger.info("LLM chat response: provider=%s length=%d chars", provider, len(result))
            return result

        response = litellm.completion(
            model=model,
            messages=messages,
            temperature=temperature,
            api_key=resolved_key,
        )
        content = response.choices[0].message.content
        logger.info("LLM chat response: provider=%s length=%d chars", provider, len(content or ""))
        return content
    except Exception as exc:
        logger.error("LLM chat failed: provider=%s model=%s error=%s", provider, model, exc)
        raise RuntimeError(
            f"LLM API call failed for provider '{provider}': {exc}"
        ) from exc
