import os
import litellm

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


def get_available_providers() -> list[str]:
    """Return list of supported provider names (for UI dropdown)."""
    return list(PROVIDERS.keys())


def validate_provider(provider: str) -> bool:
    """Return True if provider is known, False otherwise."""
    return provider in PROVIDERS


def chat(
    messages: list[dict],
    provider: str,
    api_key: str,
    temperature: float = 0.7,
) -> str:
    """
    Call the specified LLM provider and return the assistant's reply as a string.

    Args:
        messages:    OpenAI-style message list, e.g. [{"role": "user", "content": "Hi"}]
        provider:    One of the keys in PROVIDERS (e.g. "groq", "openai")
        api_key:     API key for the chosen provider
        temperature: Sampling temperature (default 0.7)

    Returns:
        The content string from the first response choice.

    Raises:
        ValueError:    If provider is not in PROVIDERS.
        RuntimeError:  If the API call fails for any reason.
    """
    if not validate_provider(provider):
        raise ValueError(
            f"Unknown provider '{provider}'. "
            f"Available providers: {get_available_providers()}"
        )

    model = PROVIDERS[provider]
    env_var = _API_KEY_ENV_VARS[provider]
    os.environ[env_var] = api_key

    try:
        response = litellm.completion(
            model=model,
            messages=messages,
            temperature=temperature,
        )
        return response.choices[0].message.content
    except Exception as exc:
        raise RuntimeError(
            f"LLM API call failed for provider '{provider}': {exc}"
        ) from exc
