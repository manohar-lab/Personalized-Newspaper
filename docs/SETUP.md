# Development Setup Guide

Welcome to the **Personalized Newspaper** developer setup guide.

---

## Prerequisites

1. **Node.js**: v18.0.0 or higher (v24.x recommended)
2. **Python**: 3.10 or higher (3.13/3.14 tested)
3. **PostgreSQL**: PostgreSQL 14+ database instance running on `localhost:5432`

---

## 1. Environment Configuration

Copy `.env.example` to create your local `.env` configuration:

```bash
cp .env.example .env
```

Ensure your `.env` contains:

```env
ENVIRONMENT=development
LOG_LEVEL=INFO
SECRET_KEY=dev-secret-key-personalized-newspaper-2026

API_BASE_URL=http://localhost:8000
FRONTEND_URL=http://localhost:3000

POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=personalized_newspaper
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/personalized_newspaper

NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

---

## 2. Backend Setup (FastAPI)

1. Create a Python virtual environment:
   ```bash
   python -m venv backend/.venv
   ```

2. Activate virtual environment:
   - **Windows PowerShell**:
     ```powershell
     .\backend\.venv\Scripts\Activate.ps1
     ```
   - **Linux/macOS**:
     ```bash
     source backend/.venv/bin/activate
     ```

3. Install dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```

4. Run unit tests:
   ```bash
   cd backend
   pytest tests
   ```

5. Start backend development server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

   FastAPI interactive documentation will be available at:
   - OpenAPI Docs: `http://localhost:8000/api/docs`
   - ReDoc: `http://localhost:8000/api/redoc`

---

## 3. Database Setup (PostgreSQL)

You can run PostgreSQL natively or using the provided automated helper script:

```bash
python backend/setup_postgres.py
```

Verify connection:
```bash
curl http://localhost:8000/api/health/database
```

---

## 4. Frontend Setup (Next.js)

1. Install Node dependencies:
   ```bash
   cd frontend
   npm install
   ```

2. Start Next.js development server:
   ```bash
   npm run dev
   ```

3. Open your browser:
   - App URL: `http://localhost:3000`

---

## 5. Verification Checklist

- [x] Backend Service: `GET http://localhost:8000/api/health` -> `{"status": "ok", "service": "personalized-newspaper"}`
- [x] Database Connection: `GET http://localhost:8000/api/health/database` -> `{"status": "connected", "database": "postgresql"}`
- [x] Frontend Status Badge: Green indicator "Backend Status: Connected"
