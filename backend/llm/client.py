"""
LLM client with an auto-built provider chain.

Priority (cheapest / most generous free tier first):
  groq → anthropic → mistral → together → openai

Only providers with API keys set in .env are included.
Add a key to unlock that provider as a fallback — no code changes needed.
"""

import re
import time
from contextvars import ContextVar
from typing import Literal
from utils.logger import get_logger

from config import (
    GROQ_API_KEY, ANTHROPIC_API_KEY, MISTRAL_API_KEY, TOGETHER_API_KEY, OPENAI_API_KEY,
    GROQ_MODEL, ANTHROPIC_MODEL, MISTRAL_MODEL, TOGETHER_MODEL, OPENAI_MODEL,
    LLM_PROVIDER_ORDER,
)

logger = get_logger("llm.client")

_MAX_RETRIES = 3       # retries per provider on transient rate limits
_DEFAULT_WAIT = 65     # seconds when retry delay can't be parsed

# Matches common API key formats that providers echo back in error messages.
_KEY_PATTERN = re.compile(
    r'(gsk_|sk-proj-|sk-ant-api03-|sk-ant-|sk-)[A-Za-z0-9_\-]{20,}'
    r'|(?:api[_\-\s]?key|apikey|authorization|bearer)[\s:=]+[A-Za-z0-9_\-\.]{20,}',
    re.IGNORECASE,
)

def _redact(value) -> str:
    """Strip API key-like strings from a value before it reaches logs or the client."""
    return _KEY_PATTERN.sub('[REDACTED]', str(value))


# ---------------------------------------------------------------------------
# Error classification helpers
# ---------------------------------------------------------------------------

def _parse_retry_delay(err: Exception) -> float:
    text = str(err)
    m = re.search(r"retryDelay['\": ]+(\d+)", text, re.IGNORECASE)
    if m:
        return float(m.group(1)) + 2
    m = re.search(r"retry in (\d+(?:\.\d+)?)", text, re.IGNORECASE)
    if m:
        return float(m.group(1)) + 2
    return _DEFAULT_WAIT

def _strip_code_fences(text: str) -> str:
    """Strip markdown code fences that some LLMs add despite being told not to."""
    text = text.strip()
    m = re.match(r'^```(?:json)?\s*\n?(.*?)\n?```\s*$', text, re.DOTALL)
    return m.group(1).strip() if m else text

def _is_rate_limit(err: Exception) -> bool:
    t = str(err)
    return "429" in t or "RESOURCE_EXHAUSTED" in t or "rate_limit_exceeded" in t

def _is_quota_exhausted(err: Exception) -> bool:
    """Daily / total quota gone — waiting won't help."""
    t = str(err)
    return (
        "PerDay" in t or "'limit': 0" in t or '"limit": 0' in t  # Groq
        or "credit balance is too low" in t.lower()              # Anthropic
        or "billing" in t.lower() and "insufficient" in t.lower()
    )

def _is_too_large(err: Exception) -> bool:
    t = str(err)
    return "413" in t or "too large" in t.lower()


# ---------------------------------------------------------------------------
# Public exception
# ---------------------------------------------------------------------------

class LLMUnavailableError(Exception):
    pass


# ---------------------------------------------------------------------------
# LLMClient
# ---------------------------------------------------------------------------

class LLMClient:
    """
    Tries providers in priority order.  Each provider is attempted up to
    _MAX_RETRIES+1 times on transient rate limits; quota exhaustion and
    oversized requests skip immediately to the next provider.
    """

    def __init__(self):
        # Build ordered chain from whichever keys are configured, respecting LLM_PROVIDER_ORDER
        self._chain: list[tuple[str, object]] = []
        logger.info(f"[LLM] provider order: {LLM_PROVIDER_ORDER}")

        openai_client_cache: dict = {}  # lazy-init shared OpenAI factory

        def _get_openai(name: str, api_key: str, base_url: str | None = None):
            if name not in openai_client_cache:
                try:
                    from openai import OpenAI
                    kwargs = {"api_key": api_key}
                    if base_url:
                        kwargs["base_url"] = base_url
                    openai_client_cache[name] = OpenAI(**kwargs)
                except ImportError:
                    logger.warning("[LLM] openai package not installed — mistral/together/openai skipped. Run: pip install openai")
                    return None
            return openai_client_cache[name]

        for provider in LLM_PROVIDER_ORDER:
            if provider == "groq" and GROQ_API_KEY:
                try:
                    import groq as groq_sdk
                except ImportError:
                    logger.warning("[LLM] groq package not installed — skipped. Run: pip install groq")
                    continue
                self._chain.append(("groq", groq_sdk.Groq(api_key=GROQ_API_KEY)))
                logger.info("[LLM] provider enabled: groq")
            elif provider == "anthropic" and ANTHROPIC_API_KEY:
                try:
                    import anthropic as anthropic_sdk
                except ImportError:
                    logger.warning("[LLM] anthropic package not installed — skipped. Run: pip install anthropic")
                    continue
                self._chain.append(("anthropic", anthropic_sdk.Anthropic(api_key=ANTHROPIC_API_KEY)))
                logger.info("[LLM] provider enabled: anthropic")
            elif provider == "mistral" and MISTRAL_API_KEY:
                c = _get_openai("mistral", MISTRAL_API_KEY, "https://api.mistral.ai/v1")
                if c:
                    self._chain.append(("mistral", c))
                    logger.info("[LLM] provider enabled: mistral")
            elif provider == "together" and TOGETHER_API_KEY:
                c = _get_openai("together", TOGETHER_API_KEY, "https://api.together.xyz/v1")
                if c:
                    self._chain.append(("together", c))
                    logger.info("[LLM] provider enabled: together")
            elif provider == "openai" and OPENAI_API_KEY:
                c = _get_openai("openai", OPENAI_API_KEY)
                if c:
                    self._chain.append(("openai", c))
                    logger.info("[LLM] provider enabled: openai")

        if not self._chain:
            logger.error("[LLM] No providers configured — set at least one API key in .env")

    # ------------------------------------------------------------------

    def complete(
        self,
        system: str,
        user: str,
        response_format: Literal["text", "json"] = "text",
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> str:
        last_error = None

        for name, client in self._chain:
            for attempt in range(_MAX_RETRIES + 1):
                try:
                    t0 = time.time()
                    result = self._call(name, client, system, user, response_format, max_tokens, temperature)
                    logger.info(f"[LLM] {name} OK in {time.time()-t0:.2f}s")
                    return result
                except Exception as e:
                    last_error = e
                    if _is_too_large(e):
                        logger.warning(f"[LLM] {name} request too large — next provider")
                        break
                    elif _is_quota_exhausted(e):
                        logger.warning(f"[LLM] {name} quota exhausted — next provider")
                        break
                    elif _is_rate_limit(e) and attempt < _MAX_RETRIES:
                        wait = _parse_retry_delay(e)
                        logger.warning(f"[LLM] {name} rate-limited — waiting {wait:.0f}s (attempt {attempt+1})")
                        time.sleep(wait)
                    else:
                        logger.warning(f"[LLM] {name} failed: {type(e).__name__}: {_redact(e)} — next provider")
                        break

        raise LLMUnavailableError(f"All providers failed. Last error: {_redact(last_error)}")

    # ------------------------------------------------------------------

    def _call(self, name, client, system, user, response_format, max_tokens, temperature) -> str:
        if name == "groq":
            return self._call_groq(client, system, user, response_format, max_tokens, temperature)
        elif name == "anthropic":
            return self._call_anthropic(client, system, user, response_format, max_tokens, temperature)
        else:
            # mistral / together / openai — all OpenAI-compatible
            return self._call_openai_compat(name, client, system, user, response_format, max_tokens, temperature)

    def _call_groq(self, client, system, user, response_format, max_tokens, temperature) -> str:
        kwargs = dict(
            model=GROQ_MODEL,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if response_format == "json":
            kwargs["response_format"] = {"type": "json_object"}
        return client.chat.completions.create(**kwargs).choices[0].message.content

    def _call_anthropic(self, client, system, user, response_format, max_tokens, temperature) -> str:
        sys_prompt = system
        if response_format == "json":
            sys_prompt = system + "\n\nRespond with valid JSON only. No markdown, no code fences, no explanation."
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            temperature=temperature,
            system=sys_prompt,
            messages=[{"role": "user", "content": user}],
        )
        text = response.content[0].text
        if response_format == "json":
            text = _strip_code_fences(text)
        return text

    def _call_openai_compat(self, name, client, system, user, response_format, max_tokens, temperature) -> str:
        model = {
            "mistral": MISTRAL_MODEL,
            "together": TOGETHER_MODEL,
            "openai":   OPENAI_MODEL,
        }[name]
        kwargs = dict(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if response_format == "json":
            kwargs["response_format"] = {"type": "json_object"}
        return client.chat.completions.create(**kwargs).choices[0].message.content


# ---------------------------------------------------------------------------
# Shared singleton + per-request user override
# ---------------------------------------------------------------------------

# Set this context var to use a caller-supplied key for the duration of a request.
user_llm_override: ContextVar['LLMClient | None'] = ContextVar('user_llm_override', default=None)

_client: LLMClient | None = None

def get_llm_client() -> LLMClient:
    override = user_llm_override.get(None)
    if override is not None:
        return override
    global _client
    if _client is None:
        _client = LLMClient()
    return _client


_PROVIDER_BASE_URLS = {
    "mistral": "https://api.mistral.ai/v1",
    "together": "https://api.together.xyz/v1",
}

def build_for_user(provider: str, api_key: str) -> LLMClient:
    """Construct a single-provider LLMClient using the caller's own API key."""
    client = object.__new__(LLMClient)
    client._chain = []

    if provider == "groq":
        import groq as groq_sdk
        client._chain.append(("groq", groq_sdk.Groq(api_key=api_key)))
    elif provider == "anthropic":
        import anthropic as anthropic_sdk
        client._chain.append(("anthropic", anthropic_sdk.Anthropic(api_key=api_key)))
    elif provider in ("openai", "mistral", "together"):
        from openai import OpenAI
        kwargs = {"api_key": api_key}
        if provider in _PROVIDER_BASE_URLS:
            kwargs["base_url"] = _PROVIDER_BASE_URLS[provider]
        client._chain.append((provider, OpenAI(**kwargs)))
    else:
        raise ValueError(f"Unknown provider: {provider!r}")

    logger.info(f"[LLM] user-supplied key: provider={provider}")
    return client
