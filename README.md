# Personalized Newspaper

> **Your news. Your interests. Your newspaper.**

A production-oriented personal daily newspaper application that aggregates stories from the web, understands each reader's interests, learns from interaction behavior, and dynamically compiles a personalized digital newspaper.

---

## Phase 1 Architecture Foundation

Phase 1 establishes the production project foundation with strict component separation:

- **`frontend/`**: Next.js (React + TypeScript + Tailwind CSS) digital newspaper interface.
- **`backend/`**: FastAPI (Python) REST API service with async SQLAlchemy database layer.
- **`scraper/`**: Isolated web ingestion, RSS scraping, extraction, and content cleaning architecture.
- **`docs/`**: Architecture and development setup documentation.

---

## Quick Start

### 1. Environment Setup

```bash
cp .env.example .env
```

### 2. Backend (FastAPI)

```bash
# Create virtual environment and install requirements
python -m venv backend/.venv
.\backend\.venv\Scripts\Activate.ps1   # Windows
pip install -r backend/requirements.txt

# Run backend tests
cd backend && pytest tests

# Start FastAPI server
uvicorn app.main:app --reload --port 8000
```

### 3. Database (PostgreSQL)

Start PostgreSQL natively or run the helper script:

```bash
python backend/setup_postgres.py
```

### 4. Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:3000` to view the newspaper.

---

## Verification Endpoints

- **Backend Health**: `GET http://localhost:8000/api/health`
- **PostgreSQL Connection**: `GET http://localhost:8000/api/health/database`
- **OpenAPI Docs**: `http://localhost:8000/api/docs`
- **Frontend App**: `http://localhost:3000`

---

## Architecture Pipeline

```
NEWS SOURCES ➔ INGESTION ➔ EXTRACTION ➔ CLEANING ➔ DEDUPLICATION ➔ AI CLASSIFICATION ➔ USER PROFILE ➔ RANKING ➔ NEWSPAPER GENERATION ➔ READER UI
```

BY Manu
