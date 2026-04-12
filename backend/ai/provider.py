"""
Unified LLM client. Routes to Claude, OpenAI, or OpenRouter.
Active provider/model is read from ai_provider_config.
API keys are read from system_config.
All calls are cached in the llm_cache table (TTL from system_config).
"""
import hashlib
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.models import LLMCache, AIProviderConfig
from backend.db.system_config import get_config


def _make_cache_key(prompt: str, system: str, provider: str, model: str) -> str:
    raw = f"{provider}:{model}:{system}:{prompt}"
    return hashlib.sha256(raw.encode()).hexdigest()[:64]


async def _get_cached(session: AsyncSession, cache_key: str) -> str | None:
    now = datetime.now(timezone.utc)
    row = await session.scalar(
        select(LLMCache).where(
            LLMCache.cache_key == cache_key,
            LLMCache.expires_at > now,
        )
    )
    return row.response if row else None


async def _set_cached(
    session: AsyncSession, cache_key: str, prompt_hash: str,
    response: str, provider: str, model: str, ttl_seconds: int
):
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    existing = await session.scalar(
        select(LLMCache).where(LLMCache.cache_key == cache_key)
    )
    if existing:
        existing.response = response
        existing.expires_at = expires_at
    else:
        session.add(LLMCache(
            cache_key=cache_key,
            prompt_hash=prompt_hash,
            response=response,
            provider=provider,
            model=model,
            expires_at=expires_at,
        ))
    await session.commit()


async def _resolve_provider_and_key(
    session: AsyncSession,
    override_provider: str | None,
    override_model: str | None,
) -> tuple[str, str, str]:
    """Return (provider, model, api_key) from DB config."""
    active = await session.scalar(
        select(AIProviderConfig).where(AIProviderConfig.is_active == True)
    )
    provider = override_provider or (active.provider if active else "claude")
    model = override_model or (active.model_id if active else "claude-haiku-4-5-20251001")
    api_key = await get_config(session, f"{provider}_api_key", "")
    return provider, model, api_key


async def complete(
    prompt: str,
    system: str = "You are a helpful AI content intelligence assistant.",
    session: AsyncSession | None = None,
    use_cache: bool = True,
    override_provider: str | None = None,
    override_model: str | None = None,
) -> str:
    """
    Send a prompt to the configured LLM provider and return the response text.
    Provider, model, and API key are read from the database.
    Results are cached by default.
    """
    if session is None:
        raise RuntimeError(
            "complete() requires a DB session to read provider config and API keys. "
            "Pass the current AsyncSession."
        )

    provider, model, api_key = await _resolve_provider_and_key(
        session, override_provider, override_model
    )

    cache_key = _make_cache_key(prompt, system, provider, model)

    if use_cache:
        cached = await _get_cached(session, cache_key)
        if cached:
            return cached

    response_text = await _call_provider(provider, model, system, prompt, api_key)

    if use_cache:
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()
        ttl = int(await get_config(session, "llm_cache_ttl_seconds", "604800"))
        await _set_cached(
            session, cache_key, prompt_hash, response_text,
            provider, model, ttl
        )

    return response_text


async def _call_provider(
    provider: str, model: str, system: str, prompt: str, api_key: str
) -> str:
    if provider == "claude":
        return await _call_claude(model, system, prompt, api_key)
    elif provider == "openai":
        return await _call_openai(model, system, prompt, api_key)
    elif provider == "openrouter":
        return await _call_openrouter(model, system, prompt, api_key)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


async def _call_claude(model: str, system: str, prompt: str, api_key: str) -> str:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=api_key)
    message = await client.messages.create(
        model=model,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


async def _call_openai(model: str, system: str, prompt: str, api_key: str) -> str:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=api_key)
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        max_tokens=1024,
    )
    return response.choices[0].message.content or ""


async def _call_openrouter(model: str, system: str, prompt: str, api_key: str) -> str:
    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 1024,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def complete_batch(
    prompts: list[str],
    system: str = "You are a helpful AI content intelligence assistant.",
    session: AsyncSession | None = None,
) -> list[str]:
    """Process multiple prompts, using cache for each independently."""
    results = []
    for prompt in prompts:
        result = await complete(prompt, system=system, session=session)
        results.append(result)
    return results
