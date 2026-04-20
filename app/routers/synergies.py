"""Router for synergies endpoint."""
import logging

from fastapi import APIRouter, Depends, status, HTTPException

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.synergy_analyzer import find_synergies
from app.schemas import SynergiesRequest, SynergiesResponse


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/advisor", tags=["advisor"])


@router.post(
    "/synergies",
    response_model=SynergiesResponse,
    status_code=status.HTTP_200_OK,
    summary="Find synergistic cards",
    description="Find cards that work well together based on keyword/effect combinations"
)
async def get_synergies(
    request: SynergiesRequest,
    db: AsyncSession = Depends(get_db),
) -> SynergiesResponse:
    """
    Find synergistic cards for the given input cards.

    The synergy analyzer looks for cards with complementary effects:
    - Removal + Draw = Remove threats, refuel hand
    - Buff + Evasion = Big damage that can't be blocked
    - Summon + Protection = Recursive threats that are hard to kill
    - Resource + High Cost = Ramp into big plays
    """
    logger.info(
        "get_synergies | card_names=%r format=%r race=%r",
        request.card_names, request.format, request.race_slug
    )

    try:
        result = await find_synergies(
            session=db,
            card_names=request.card_names,
            race_slug=request.race_slug,
            format_type=request.format,
            limit=request.limit,
        )

        # Check for errors in the result
        if "error" in result.get("meta", {}):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result["meta"]["error"]
            )

        return SynergiesResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_synergies | error=%s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error finding synergies: {str(e)}"
        )
