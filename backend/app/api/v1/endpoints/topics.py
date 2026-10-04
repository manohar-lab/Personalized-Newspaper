from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.topic import Topic
from app.schemas.topic import TopicResponse

router = APIRouter()

@router.get("", response_model=List[TopicResponse])
async def get_topics(
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all available topics."""
    stmt = select(Topic).order_by(Topic.name.asc())
    result = await db.execute(stmt)
    topics = result.scalars().all()
    return [TopicResponse.model_validate(t) for t in topics]
