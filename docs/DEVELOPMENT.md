# TurfSlot - Local Development

## Prerequisites
- Docker Desktop
- Python 3.12 (3.11+ works)
- Node.js 22

> A host PostgreSQL already uses port 5432, so the Docker Postgres is published on **5433**.

## 1. Start infrastructure (Postgres + Mailpit)

```bash
docker compose -f docker-compose.dev.yml up -d db mailpit
# one-time: create the test database
docker compose -f docker-compose.dev.yml exec db psql -U turfslot -c "CREATE DATABASE turfslot_test"
```

| Service | URL |
|---------|-----|
| Postgres | `postgresql://turfslot:turfslot@localhost:5433/turfslot` |
| Postgres (tests) | `postgresql://turfslot:turfslot@localhost:5433/turfslot_test` |
| Mailpit SMTP | `localhost:1025` |
| Mailpit UI | http://localhost:8025 |

## 2. Environment

```bash
cp .env.example backend/.env     # API (host) reads backend/.env
cp .env.example .env             # docker compose reads ./.env (optional)
```

`DODO_PAYMENTS_API_KEY=fake` (or empty) uses the built-in fake payment gateway.

## 3. Backend (Windows, Git Bash / PowerShell)

```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/alembic upgrade head
.venv/Scripts/uvicorn app.main:app --reload --port 8000
```

(macOS/Linux: use `.venv/bin/...`.) API: http://localhost:8000, docs: http://localhost:8000/docs, health: http://localhost:8000/health

New migration: `.venv/Scripts/alembic revision --autogenerate -m "describe change"`

## 4. Frontend

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

## 5. Tests and checks

```bash
# backend (uses TEST_DATABASE_URL, real Postgres)
cd backend
.venv/Scripts/ruff check .
.venv/Scripts/pytest --cov=app --cov-fail-under=80

# frontend
cd frontend
npm run lint && npm run type-check && npm test && npm run build
```

## 6. Everything in Docker

Hot-reload dev stack (api with `uvicorn --reload`, web with Vite):

```bash
docker compose -f docker-compose.dev.yml up --build
```

Production-like stack (nginx-served build, migrations run on api start):

```bash
docker compose up -d --build
```

| App | URL |
|-----|-----|
| Web (nginx build) | http://localhost:3000 |
| Web (Vite dev) | http://localhost:5173 |
| API / docs | http://localhost:8000 / http://localhost:8000/docs |
| Mailpit | http://localhost:8025 |

The two compose files use separate project names (`turfslot`, `turfslot-dev`) and data volumes, but share host ports, so run only one at a time.

Stop: `docker compose -f docker-compose.dev.yml down` (add `-v` to wipe the database).
