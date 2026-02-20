"""
LLM Provider abstraction layer.

Supports multiple LLM providers with automatic fallback:
  1. Anthropic Claude (if ANTHROPIC_API_KEY is set)
  2. Groq (if GROQ_API_KEY is set)
  3. Ollama local (if running)
  4. Raises RuntimeError if none available
"""

import os

from langchain_core.language_models.chat_models import BaseChatModel


def get_llm() -> BaseChatModel:
    """Get the best available LLM provider.

    Checks providers in order: Anthropic → Groq → Ollama → Error.

    Returns:
        A LangChain chat model instance.

    Raises:
        RuntimeError: If no LLM provider is available.
    """
    # 1. Try Anthropic Claude
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if anthropic_key:
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model="claude-sonnet-4-20250514",
            api_key=anthropic_key,
            temperature=0,
            max_tokens=1024,
        )

    # 2. Try Groq
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if groq_key:
        from langchain_groq import ChatGroq

        return ChatGroq(
            model="llama-3.3-70b-versatile",
            api_key=groq_key,
            temperature=0,
            max_tokens=1024,
        )

    # 3. Try Ollama (local)
    try:
        import httpx

        response = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
        if response.status_code == 200:
            from langchain_community.chat_models import ChatOllama

            return ChatOllama(
                model="llama3",
                temperature=0,
            )
    except (httpx.ConnectError, httpx.TimeoutException, Exception):
        pass

    # 4. No provider available
    raise RuntimeError(
        "No LLM provider available. Please set one of the following:\n"
        "  - ANTHROPIC_API_KEY (for Claude)\n"
        "  - GROQ_API_KEY (for Groq, free tier available)\n"
        "  - Or run Ollama locally (http://localhost:11434)"
    )
