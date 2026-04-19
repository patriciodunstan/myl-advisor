"""LLM Client for Z.ai (OpenAI-compatible)."""
import logging
import hashlib
import json
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import AnalysisCache, _is_cache_expired


logger = logging.getLogger(__name__)

settings = get_settings()

# Initialize OpenAI client for Z.ai
client = AsyncOpenAI(
    api_key=settings.zai_api_key,
    base_url=settings.zai_api_base,
)


def _hash_request(request_data: dict) -> str:
    """Create SHA256 hash of request for caching."""
    request_str = json.dumps(request_data, sort_keys=True)
    return hashlib.sha256(request_str.encode()).hexdigest()


async def get_cached_analysis(
    session: AsyncSession,
    request_hash: str,
) -> Optional[dict]:
    """Check cache for existing analysis."""
    from sqlalchemy import select

    query = select(AnalysisCache).where(AnalysisCache.request_hash == request_hash)
    result = await session.execute(query)
    cached = result.scalar_one_or_none()

    if cached and not _is_cache_expired(cached):
        logger.info("Cache hit for hash=%s", request_hash[:16])
        return {
            "id": cached.id,
            "response": json.loads(cached.response),
            "created_at": cached.created_at,
            "expires_at": cached.expires_at,
        }
    elif cached and _is_cache_expired(cached):
        logger.info("Cache expired for hash=%s", request_hash[:16])
        return None
    else:
        logger.debug("Cache miss for hash=%s", request_hash[:16])
        return None


async def cache_analysis(
    session: AsyncSession,
    request_hash: str,
    card_name: str,
    analysis_type: str,
    response: dict,
    ttl_hours: int = 24,
) -> None:
    """Cache analysis response."""
    expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)

    cached = AnalysisCache(
        request_hash=request_hash,
        card_name=card_name,
        analysis_type=analysis_type,
        response=json.dumps(response),
        expires_at=expires_at,
    )

    session.add(cached)
    await session.flush()

    logger.info("Cached analysis for %s (hash=%s, expires=%s)",
                card_name, request_hash[:16], expires_at)


async def analyze_alternatives_with_llm(
    session: AsyncSession,
    target_card: dict,
    alternatives: list,
    request_data: dict,
) -> Optional[dict]:
    """
    Use LLM to generate enhanced analysis for alternatives.

    This is optional - the keyword-based scoring is usually sufficient.
    The LLM can provide:
    - Better explanations
    - Strategic advice
    - Deck-building considerations
    """
    request_hash = _hash_request(request_data)

    # Check cache first
    cached = await get_cached_analysis(session, request_hash)
    if cached:
        return cached["response"]

    # If no cache and no API key, return None (use keyword-only results)
    if not settings.zai_api_key or settings.zai_api_key == "test_key":
        logger.warning("No valid Z.ai API key configured, skipping LLM analysis")
        return None

    # Build prompt
    prompt = _build_alternatives_prompt(target_card, alternatives)

    try:
        # Call Z.ai
        response = await client.chat.completions.create(
            model=settings.zai_model,
            messages=[
                {
                    "role": "system",
                    "content": "Eres un asistente experto en el juego de cartas MyL. Ayuda a los jugadores a encontrar alternativas estratégicas a sus cartas."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=1000,
        )

        llm_response = response.choices[0].message.content

        # Parse response (simple format for now)
        llm_analysis = {
            "llm_summary": llm_response,
            "enhanced_reasoning": True,
        }

        # Cache the response
        await cache_analysis(
            session=session,
            request_hash=request_hash,
            card_name=target_card["name"],
            analysis_type="alternatives",
            response=llm_analysis,
            ttl_hours=settings.cache_ttl_hours,
        )

        logger.info("LLM analysis completed for %s", target_card["name"])
        return llm_analysis

    except Exception as e:
        logger.error("Error calling Z.ai API: %s", e, exc_info=True)
        # Fall back to keyword-only results
        return None


def _build_alternatives_prompt(target_card: dict, alternatives: list) -> str:
    """Build prompt for alternatives analysis."""
    prompt = f"""Analiza estas alternativas para la carta '{target_card['name']}'.

Carta objetivo:
- Nombre: {target_card['name']}
- Coste: {target_card['cost']}
- Raza: {target_card.get('race_name', 'N/A')}
- Tipo: {target_card.get('type_name', 'N/A')}
- Habilidad: {target_card.get('ability', 'N/A') or 'Sin habilidad'}

Alternativas encontradas:
"""

    for i, alt in enumerate(alternatives[:5], 1):
        card = alt["card"]
        prompt += f"""
{i}. {card['name']}
   - Coste: {card['cost']}
   - Similitud: {alt['similarity']}%
   - Habilidad: {card.get('ability', 'N/A') or 'Sin habilidad'}
   - Razón: {alt['reason']}
"""

    prompt += """

Proporciona:
1. Un resumen breve (2-3 oraciones) sobre cuál es la mejor alternativa y por qué
2. Una sugerencia estratégica sobre cómo integrar esta alternativa en un mazo
3. Consideraciones de sinergia con otras cartas típicas de esta raza

Responde en español, de forma concisa y útil para un jugador."""
    return prompt
