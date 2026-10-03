# System Architecture Blueprint

The **Personalized Newspaper** system is built on a decoupled, pipeline-oriented architecture designed to scale from ingestion through AI classification to user-specific newspaper rendering.

---

## High-Level Data Flow

```
NEWS SOURCES (RSS / Web Ingestion)
       │
       ▼
INGESTION & SCRAPER ENGINE (scraper/sources, extractor, processors)
       │
       ▼
ARTICLE CLEANING & DEDUPLICATION
       │
       ▼
AI CLASSIFICATION & EMBEDDINGS (backend/app/agents)
       │
       ▼
POSTGRESQL STORAGE (backend/app/database, models, repositories)
       │
       ▼
USER INTEREST PROFILE & PERSONAL RANKING (backend/app/services)
       │
       ▼
NEWSPAPER GENERATION ENGINE
       │
       ▼
FRONTEND READER (frontend/app - Next.js)
```

---

## Directory Responsibilities

- **`frontend/`**: Next.js App Router application implementing digital newspaper UI, Tailwind styling, and reactive state management.
- **`backend/`**: FastAPI REST server providing endpoints, SQLAlchemy async database layer, schemas, services, and AI agents.
  - `app/api/`: Versioned API routing handlers.
  - `app/core/`: Application settings, logging, and CORS setup.
  - `app/database/`: Async connection pool and session handlers.
  - `app/models/`: SQLAlchemy ORM data models.
  - `app/schemas/`: Pydantic validation schemas.
  - `app/services/`: Business logic for recommendations and ranking.
  - `app/repositories/`: Data access abstraction layer.
  - `app/agents/`: Modular AI classification and summarization agents.
- **`scraper/`**: Dedicated scraping and RSS ingestion package separate from API server.
  - `sources/`: RSS & HTML web scraper targets.
  - `extractors/`: Content extraction algorithms.
  - `processors/`: Sanitization, text cleaning, and deduplication logic.
- **`docs/`**: Architectural blueprints and setup documentation.
