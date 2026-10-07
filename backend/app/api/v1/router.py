from fastapi import APIRouter
from app.api.v1.endpoints import (
    health,
    auth,
    topics,
    interests,
    onboarding,
    articles,
    newspaper,
    users,
    news,
    behavior,
    reading,
    admin_pipeline,
    search,
    recommendations,
    sources,
    admin_sources,
    stories,
    admin_editorial,
    briefings,
    news_sessions,
)

api_v1_router = APIRouter()

api_v1_router.include_router(health.router, tags=["Health"])
api_v1_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_v1_router.include_router(topics.router, prefix="/topics", tags=["Topics"])
api_v1_router.include_router(interests.router, prefix="/users/me/interests", tags=["Interests"])
api_v1_router.include_router(interests.router, prefix="/interests", tags=["Interests"])
api_v1_router.include_router(onboarding.router, prefix="/onboarding", tags=["Onboarding"])
api_v1_router.include_router(articles.router, prefix="/articles", tags=["Articles"])
api_v1_router.include_router(newspaper.router, prefix="/newspaper", tags=["Newspaper"])
api_v1_router.include_router(users.router, prefix="/users/me", tags=["Users"])
api_v1_router.include_router(news.router, prefix="/news", tags=["News"])
api_v1_router.include_router(sources.router, prefix="/news/sources", tags=["Sources"])
api_v1_router.include_router(sources.router, prefix="/sources", tags=["Sources"])
api_v1_router.include_router(stories.router, prefix="/stories", tags=["Stories"])
api_v1_router.include_router(stories.router, prefix="/news/stories", tags=["Stories"])
api_v1_router.include_router(briefings.router, prefix="/briefings", tags=["Briefings"])
api_v1_router.include_router(news_sessions.router, prefix="/news/sessions", tags=["News Sessions"])
api_v1_router.include_router(behavior.router, prefix="/behavior", tags=["Behavior"])
api_v1_router.include_router(reading.router, prefix="/reading", tags=["Reading"])
api_v1_router.include_router(admin_pipeline.router, prefix="/admin/pipeline", tags=["Admin Pipeline"])
api_v1_router.include_router(admin_sources.router, prefix="/admin", tags=["Admin Sources"])
api_v1_router.include_router(admin_editorial.router, prefix="/admin/editorial", tags=["Admin Editorial"])
api_v1_router.include_router(search.router, prefix="/search", tags=["Search"])
api_v1_router.include_router(recommendations.router, prefix="/recommendations", tags=["Recommendations"])




