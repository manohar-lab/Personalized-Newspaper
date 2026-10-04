import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

class TopicResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    description: Optional[str] = None
    parent_topic_id: Optional[uuid.UUID] = None
    created_at: datetime
