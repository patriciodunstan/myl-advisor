"""Router for hidden gems endpoint."""
import logging

from fastapi import APIRouter, Depends, status, HTTPException

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.hidden_gems_finder import find_hidden_gems
from app.schemas import HiddenGemsRequest, HiddenGemsResponse


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/advisor", tags=["advisor"])


@router.post(
    "/hidden-gems",
    response_model=HiddenGemsResponse,
    status_code=status.HTTP_200_OK,
    summary="Find hidden gems",
    description="Find underrated cards with high keyword density but common/low rarity"
)
async def get_hidden_gems(
    request: HiddenGemsRequest,
    db: AsyncSession = Depends(get_db),
) -> HiddenGemsResponse:
    """
    Find hidden gems - underrated cards with high keyword density but common/low rarity.

    Hidden gems are scored based on:
    - Keyword density (more keywords = higher score)
    - Rarity bonus (common cards get higher bonus)
    - Cost efficiency (cheaper cards with more keywords get higher score)
    """
    logger.info(
        "get_hidden_gems | race=%r format=%r max_cost=%s min_keywords=%d limit=%d",
        request.race_slug, request.format, request.max_cost,
        request.min_keywords, request.limit
    )

    try:
        result = await find_hidden_gems(
            session=db,
            race_slug=request.race_slug,
            format_type=request.format,
            max_cost=request.max_cost,
            min_keywords=request.min_keywords,
            limit=request.limit,
        )

        # Check for errors in the result
        if "error" in result.get("meta", {}):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result["meta"]["error"]
            )

        return HiddenGemsResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_hidden_gems | error=%s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error finding hidden gems: {str(e)}"
        )
