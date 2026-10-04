from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import setup_logging, logger
from app.api.v1.router import api_v1_router


from app.database.session import AsyncSessionLocal
from app.database.seed_topics import seed_topics
from app.database.seed_articles import seed_articles


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup initialization
    setup_logging()
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION} [{settings.ENVIRONMENT}]")
    try:
        async with AsyncSessionLocal() as session:
            await seed_topics(session)
            await seed_articles(session)
    except Exception as e:
        logger.warning(f"Startup seed error: {e}")
    yield
    # Shutdown cleanup
    logger.info(f"Shutting down {settings.PROJECT_NAME}")



app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Personalized Newspaper Backend API",
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

# CORS Configuration
origins = settings.CORS_ORIGINS
if settings.FRONTEND_URL and settings.FRONTEND_URL not in origins:
    origins.append(settings.FRONTEND_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount health & API routes at /api
app.include_router(api_v1_router, prefix="/api")


@app.get("/", include_in_schema=False)
async def root():
    return {
        "title": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": "/api/docs",
    }
