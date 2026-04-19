"""Alternatives endpoint - Find cheaper card alternatives."""
import logging
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import AlternativesRequest, AlternativesResponse, AlternativeCard, CardInfo
from app.services.alternative_finder import find_alternatives
from app.llm.client import analyze_alternatives_with_llm


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/advisor", tags=["advisor"])


@router.post("/alternatives", response_model=AlternativesResponse, tags=["advisor"])
async def get_alternatives(
    request: AlternativesRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Find alternative cards based on keyword similarity.

    Process:
    1. Find the target card by name
    2. Get cards of the same race within cost range
    3. Filter by banlist and rarity
    4. Score by keyword overlap in abilities
    5. Return top 10 alternatives

    Parameters:
    - card_name: Name of the card to find alternatives for
    - format: Game format (racial_edicion, racial_libre, constructed)
    - max_rarity: Maximum rarity to include (optional)
    - max_cost: Maximum cost to consider (optional)

    Returns:
    - alternatives: List of alternative cards with similarity scores
    - meta: Metadata about the analysis
    """
    logger.info(
        "GET /alternatives | card_name=%r format=%r max_rarity=%s max_cost=%s",
        request.card_name, request.format, request.max_rarity, request.max_cost
    )

    try:
        # Find alternatives
        result = await find_alternatives(
            session=db,
            card_name=request.card_name,
            format_type=request.format,
            max_rarity=request.max_rarity,
            max_cost=request.max_cost,
            limit=10,
        )

        # Check for errors
        if "error" in result.get("meta", {}):
            error_msg = result["meta"]["error"]
            logger.warning("Alternatives request error: %s", error_msg)

            # Return appropriate HTTP status
            if "not found" in error_msg.lower():
                raise HTTPException(status_code=404, detail=error_msg)
            else:
                raise HTTPException(status_code=400, detail=error_msg)

        # Format response
        alternatives = [
            AlternativeCard(
                card=CardInfo(**alt["card"]),
                similarity=alt["similarity"],
                reason=alt["reason"],
            )
            for alt in result["alternatives"]
        ]

        # Try LLM enhancement if API key is configured
        llm_result = await analyze_alternatives_with_llm(
            session=db,
            target_card=result["meta"]["target_card"],
            alternatives=result["alternatives"],
            request_data={
                "card_name": request.card_name,
                "format": request.format,
                "max_rarity": request.max_rarity,
                "max_cost": request.max_cost,
            },
        )

        response = AlternativesResponse(
            alternatives=alternatives,
            meta=result["meta"],
            llm_analysis=llm_result,
        )

        logger.info("GET /alternatives | %s → %d alternatives",
                    request.card_name, len(alternatives))

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in alternatives endpoint: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        ) from e
