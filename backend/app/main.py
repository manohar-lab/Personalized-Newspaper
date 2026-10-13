from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.logging import setup_logging, logger
from app.api.v1.router import api_v1_router


from app.database.session import AsyncSessionLocal
from app.database.seed_topics import seed_topics
from app.database.seed_articles import seed_articles
from app.database.seed_feeds import seed_sources_and_feeds


from app.workers.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup initialization
    setup_logging()
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION} [{settings.ENVIRONMENT}]")
    try:
        async with AsyncSessionLocal() as session:
            await seed_topics(session)
            await seed_sources_and_feeds(session)
            await seed_articles(session)
    except Exception as e:
        logger.warning(f"Startup seed error: {e}")

    # Start background scheduler if enabled
    if settings.SCHEDULER_ENABLED and settings.ENVIRONMENT != "testing":
        try:
            start_scheduler()
        except Exception as e:
            logger.error(f"Failed to start background scheduler: {e}")

    yield
    # Shutdown cleanup
    logger.info(f"Shutting down {settings.PROJECT_NAME}")
    try:
        await stop_scheduler()
    except Exception as e:
        logger.error(f"Error during scheduler shutdown: {e}")



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
# Strip any trailing slashes and whitespace because browser Origin headers never have trailing slashes
raw_origins = list(settings.CORS_ORIGINS)
if settings.FRONTEND_URL:
    raw_origins.append(settings.FRONTEND_URL)

raw_origins.extend([
    "https://personalized-newspaper.vercel.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
])

origins = []
for o in raw_origins:
    if isinstance(o, str):
        cleaned = o.strip().rstrip("/")
        if cleaned and cleaned not in origins:
            origins.append(cleaned)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=600,
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled server error processing {request.method} {request.url.path}: {exc}")
    origin = request.headers.get("origin")
    resp_headers = {}
    if origin and origin.rstrip("/") in origins:
        resp_headers["Access-Control-Allow-Origin"] = origin
        resp_headers["Access-Control-Allow-Credentials"] = "true"
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
        headers=resp_headers,
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
