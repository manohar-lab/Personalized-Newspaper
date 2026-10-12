# Personalized Newspaper

> **Your news. Your interests. Your newspaper.**

A production-oriented personal digital newspaper application that aggregates stories from the web, understands each reader's interests, learns from interaction behavior, and dynamically compiles an editorial broadsheet newspaper edition.

---

## System Architecture

The application is built on a decoupled, pipeline-oriented architecture:

- **`frontend/`**: Next.js 14 App Router (React 18 + TypeScript + Tailwind CSS) editorial digital newspaper interface.
- **`backend/`**: FastAPI (Python 3.14) REST API service with async SQLAlchemy database layer, APScheduler workers, and AI intelligence pipelines.
- **`scraper/`**: Isolated web ingestion, RSS scraping, readability extraction, sanitization, and deduplication engine.
- **`docs/`**: Architecture blueprints (`docs/ARCHITECTURE.md`) and development setup instructions (`docs/SETUP.md`).

```
NEWS SOURCES ➔ INGESTION ➔ EXTRACTION ➔ CLEANING ➔ DEDUPLICATION ➔ AI CLASSIFICATION ➔ USER PROFILE ➔ RANKING ➔ NEWSPAPER GENERATION ➔ READER UI
```

---

## Current Capabilities (Phases 1–24 Implemented)

The project has completed Phases 1 through 24:

1. **Architecture Foundation & Scaffolding (Phase 1)**: Multi-service structure with isolated frontend, backend, and ingestion layers.
2. **User Authentication & Authorization (Phase 2)**: JWT-based authentication, password hashing (bcrypt), token refresh, and protected endpoints.
3. **Topic Taxonomy & Cold-Start Onboarding (Phase 3)**: Hierarchical topic taxonomy, cold-start interest questionnaire, and explicit preference weighting.
4. **News Source Registry & RSS Ingestion (Phase 4)**: Multi-source feed management, RSS/Atom feed parsing, feed validation, and OPML import.
5. **Article Extraction & Sanitization (Phase 5)**: Automated HTML readability extraction, text normalization, image discovery, author resolution, and metadata parsing.
6. **Automated Polling & Ingestion Pipeline (Phase 6)**: Background feed polling, rate limiting, domain politeness delays, robots.txt caching, and feed health monitoring.
7. **Near-Duplicate Detection & Deduplication (Phase 7)**: Locality-sensitive hashing (MinHash/LSH), SimHash fingerprinting, URL canonicalization, and syndicated article suppression.
8. **AI-Powered Article Intelligence (Phase 8)**: Automated topic classification, named entity recognition (NER), quality assessment, importance scoring, and semantic text embeddings.
9. **Daily Newspaper Generation & Broadsheet Engine (Phase 9)**: Daily edition compilation, broadsheet layout assignment (Lead, Feature, Compact, Standard), and persistent edition snapshots.
10. **APScheduler Background Automation (Phase 10)**: Automated background workers for periodic feed ingestion, article analysis, and morning edition generation.
11. **Reader Engagement & Explicit Feedback (Phase 11)**: User actions including Like, Save/Bookmark, and Not-Interested filtering with instant layout adjustments.
12. **Personalized Multi-Factor Ranking Engine (Phase 12)**: Multi-factor scoring combining topic affinity, entity match, importance, recency decay, and serendipity.
13. **Dynamic Interest Learning & Topic Drift (Phase 13)**: Implicit interest evolution, exponential decay of past engagement, and emerging topic discovery.
14. **Recommendations & Serendipity Engine (Phase 14)**: Personalized "For You" recommendations, serendipity injection, and diverse perspective discovery.
15. **Behavioral Reading Telemetry (Phase 15)**: Reading dwell time, scroll depth telemetry, completion rates, and behavioral engagement scoring.
16. **Multi-Source Story Clustering & Synthesis (Phase 16)**: Story clustering across multiple news sources, primary article selection, timeline tracking, and coverage breadth scoring.
17. **Autonomous Editorial Newsroom Engine (Phase 17)**: Automated digital editor (`EditorialNewsroom`, `EditorialComposer`, `EditorialCandidateSelector`) curating lead stories, section quotas, and editorial summaries.
18. **Personal Daily News Briefings (Phase 18)**: Executive bullet-point briefings, morning executive summaries, and AI-driven daily highlights.
19. **Longform Reading Experience (Phase 19)**: Dedicated article reading view with editorial serif typography, reading progress bars, estimated read times, and related coverage.
20. **Source Intelligence & Media Diversity (Phase 20)**: Publisher credibility scoring, source following, source muting, and independent source coverage verification.
21. **Reading History & Activity Log (Phase 21)**: Timestamped reading history, session tracking (start, heartbeat, complete), and "Continue Reading" resume states.
22. **Web Intelligence & Content Discovery (Phase 22)**: Discovery engine with exploration controls, trending topic identification, and serendipity sliders.
23. **Personalization Control Center & Explainability (Phase 23)**: Transparent "Why This Story?" explanations, topic weight sliders, and full profile inspection.
24. **Intelligent News Search & Discovery Engine (Phase 24)**: Full-text and faceted search across articles and stories, live query suggestions, search history management, and topic/entity filters.

---

## Quick Start

### 1. Environment Setup

```bash
cp .env.example .env
```

Ensure `.env` contains:
```ini
ENVIRONMENT=development
LOG_LEVEL=INFO
SECRET_KEY=dev-secret-key-personalized-newspaper-2026
JWT_SECRET_KEY=dev-jwt-secret-key-personalized-newspaper-2026
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/personalized_newspaper
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

### 2. Database (PostgreSQL)

Start PostgreSQL natively or run the automated helper script:

```bash
python backend/setup_postgres.py
```

Verify connection:
```bash
curl http://localhost:8000/api/health/database
```

### 3. Backend (FastAPI)

```bash
# Create virtual environment and install dependencies
python -m venv backend/.venv
.\backend\.venv\Scripts\Activate.ps1   # Windows PowerShell
pip install -r backend/requirements.txt

# Run backend test suite
cd backend && pytest tests

# Start development server
uvicorn app.main:app --reload --port 8000
```

### 4. Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:3000` or `http://localhost:3000/newspaper` to view the newspaper.

---

## Verification Endpoints

- **Backend Health**: `GET http://localhost:8000/api/health`
- **Database Connection**: `GET http://localhost:8000/api/health/database`
- **OpenAPI Interactive Documentation**: `GET http://localhost:8000/api/docs`
- **ReDoc Documentation**: `GET http://localhost:8000/api/redoc`
- **Frontend Application**: `http://localhost:3000`

---

## Future Enhancements — Not Yet Implemented

> **Note**: The items below represent a proposed future development roadmap. These are architectural proposals and suggestions for future milestones beyond Phase 24; they are **not yet implemented** and are subject to change.

### 1. Reading History and Continuity
- **Cross-Device Session Synchronization**: Persist in-progress reading sessions across multiple reader devices in real-time.
- **Offline Reading & Bookmark Cache**: Client-side Service Worker caching allowing readers to download today's entire edition for offline reading during commutes.
- **Reading Progress Continuity**: Granular scroll position preservation allowing instant resume at the exact paragraph where the reader left off.

### 2. Advanced Reading Analytics
- **Personal Reading Insights Dashboard**: Monthly and yearly reading dashboards displaying total words read, time spent per category, and dominant topics.
- **Vocabulary & Complexity Metrics**: Analysis of readability grade levels and specialized terminology encountered across consumed stories.
- **Topic Diversity Index**: Visual radar charts illustrating whether reading patterns are broadening or becoming topical echo chambers.

### 3. Enhanced Feedback Learning
- **Implicit Multimodal Feedback Signals**: Incorporation of fine-grained behavioral feedback such as paragraph re-reading, quote copying, and article sharing.
- **Counterfactual Ranking Evaluation**: Off-policy evaluation to benchmark personalization updates without degrading live reader editions.
- **Explicit Negative Feedback Fine-Tuning**: Granular dismissal reasons (e.g., "Outdated news", "Sensationalist headline", "Seen on another site") feeding directly into the ranking engine.

### 4. Advanced Search and Discovery
- **Hybrid Vector + Lexical (BM25) Re-Ranking**: Combining exact keyword retrieval with dense vector similarity for improved recall on technical and entity queries.
- **Natural Language Question Answering**: Generative question answering over archived editions with citation links to original articles.
- **Saved Searches & Alert Feeds**: Ability to save custom query filters as dynamic topic feeds integrated into the daily newspaper broadsheet.

### 5. Editorial Personalization
- **Multi-Edition Daily Schedules**: Support for configurable publishing times (e.g., a rapid 7:00 AM Morning Dispatch and a reflective 6:00 PM Evening Edition).
- **Custom Broadsheet Typography & Density Preferences**: Reader-selectable newspaper column density (compact tabular, broadsheet multi-column, or distraction-free magazine).
- **Custom Section Ordering**: Drag-and-drop broadsheet section sequencing allowing readers to prioritize their preferred sections over standard layouts.

### 6. Enhanced Story Intelligence
- **Interactive Story Evolution Timelines**: Visual chronological timelines showing how a multi-day developing news event unfolded over time.
- **Cross-Source Framing & Perspective Analysis**: Side-by-side analysis contrasting how different publishers report on the same event.
- **Live Event Ingestion via Webhooks & WebSockets**: Real-time push updates for fast-breaking stories directly onto the active reader page without full page refreshes.

### 7. Newsletter and Export Options
- **Automated Email Newsletters**: Scheduled delivery of the daily personalized edition directly to the reader's email inbox using HTML templates.
- **Print-Ready PDF Broadsheet Export**: Generation of multi-column printable PDFs formatted like physical newspaper front pages.
- **ePub / Kindle Delivery**: Automatic conversion and wireless delivery of daily editions to e-readers.

### 8. Notifications and Alerts
- **Breaking News Web Push Notifications**: Browser push notifications for breaking stories matching high-affinity topics.
- **Developing Story Update Pings**: Configurable alerts when a new article is added to a developing story cluster the reader is tracking.
- **Weekly Digest Alerts**: Opt-in weekend roundups summarizing key stories read or missed throughout the week.

### 9. Accessibility Improvements
- **Screen Reader Navigation Modes**: Enhanced ARIA landmarks and hotkey shortcuts for skipping between newspaper sections and articles (`J`/`K` navigation).
- **Dyslexic-Friendly Typography**: Optional switch to open-dyslexic typefaces with adjusted line height and word spacing.
- **Audio Read-Aloud / Text-to-Speech (TTS)**: In-browser audio streaming of the daily edition using natural speech synthesis.

### 10. Performance and Scalability
- **Redis Cache Layer**: In-memory caching for candidate pools, dynamic interest profiles, and computed embeddings to reduce database load.
- **PostgreSQL Partitioning**: Time-based range partitioning for `articles`, `user_actions`, and `reading_history` tables as data scales into millions of records.
- **Background Worker Concurrency Tuning**: Distributed task queues (e.g., Celery or RQ) for parallelizing scraper extraction across multiple worker nodes.

### 11. Production Deployment Improvements
- **Container Orchestration**: Production-ready multi-container Docker Compose and Kubernetes deployment manifests with health probes.
- **Telemetry & Monitoring**: Prometheus metric scrapers and Grafana dashboards tracking ingestion latency, scraping errors, and edition generation times.
- **Automated CI/CD Workflows**: GitHub Actions pipelines for automated linting, test suite execution, database migration dry-runs, and container builds.

---

## Authors & Acknowledgments

- **Author**: Manu
- **Project**: Personalized Newspaper Application
