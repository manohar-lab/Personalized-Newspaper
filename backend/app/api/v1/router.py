from fastapi import APIRouter
from app.api.v1.endpoints import health, auth, topics, interests, onboarding

api_v1_router = APIRouter()

api_v1_router.include_router(health.router, tags=["Health"])
api_v1_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_v1_router.include_router(topics.router, prefix="/topics", tags=["Topics"])
api_v1_router.include_router(interests.router, prefix="/users/me/interests", tags=["Interests"])
api_v1_router.include_router(onboarding.router, prefix="/onboarding", tags=["Onboarding"])
