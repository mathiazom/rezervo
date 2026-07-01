from fastapi import APIRouter

from rezervo.utils.category_utils import ACTIVITY_CATEGORIES, RezervoBaseCategory

router = APIRouter()


@router.get("/categories", response_model=list[RezervoBaseCategory])
async def get_activity_categories():
    return [
        RezervoBaseCategory(
            name=c.name,
            color=c.color,
        )
        for c in ACTIVITY_CATEGORIES
    ]
