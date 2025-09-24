# Portfolio Manager

FastAPI + PostgreSQL backend for ingesting market data, calculating analytics, and tracking portfolios.

## Requirements
- Python 3.11
- Poetry
- PostgreSQL 16 (local or Docker)
- Docker Desktop (optional but recommended for local orchestration)

## Initial setup (PowerShell)
1. Clone the repository and move into the project directory:
   ```powershell
   git clone https://github.com/<your-user>/portfolio-manager.git
   cd portfolio-manager
   ```
2. Create your environment file:
   ```powershell
   copy .env.example .env
   ```
3. Install dependencies and apply migrations:
   ```powershell
   poetry install
   poetry run alembic upgrade head
   ```
4. Launch the API:
   ```powershell
   poetry run uvicorn backend.app.main:app --reload --port 8000
   ```
   Docs available at http://127.0.0.1:8000/docs

## Smoke tests
- Full end-to-end check (ingest + metrics + signals):
  ```powershell
  .\tools\smoke.ps1 -BaseUrl "http://127.0.0.1:8000" -Ticker "VOO" -Start "2025-01-01" -End "2025-09-10" -Interval "1d" -Rf 0.02 -Mar 0.0
  ```
- Incremental ingest only:
  ```powershell
  .\tools\smoke_latest.ps1 -Base "http://127.0.0.1:8000" -Ticker "VOO" -Interval "1d"
  ```

## Docker workflow
```powershell
docker compose up --build
```
- API exposed at http://127.0.0.1:8000
- PostgreSQL exposed at 5432 with user `quant` and database `quantfolio`

## Running tests
```powershell
poetry run pytest -q
```

## Useful commands
- Check DB connectivity: `poetry run python -m backend.app.db.test_conn`
- Run migrations: `poetry run alembic upgrade head`
- Start API with live reload: `poetry run uvicorn backend.app.main:app --reload --port 8000`

Keep `.env` out of version control and adjust connection strings or origins as needed for your environment.
