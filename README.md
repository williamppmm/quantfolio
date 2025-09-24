# Portfolio Manager

Guía rápida para levantar y probar el proyecto.

## Requisitos
- Docker Desktop
- PowerShell
- Python 3.11
- Poetry

## Local (sin Docker)
1) Clonar el repo y ubicarse en la carpeta:
```
cd C:\portfolio-manager
```
2) Crear el archivo de entorno (editar DATABASE_URL si aplica):
```
copy .env.example .env
```
3) Instalar dependencias e inicializar DB:
```
poetry install
poetry run alembic upgrade head
```
4) Levantar la API:
```
poetry run uvicorn backend.app.main:app --reload --port 8000
```
- Docs: http://127.0.0.1:8000/docs

## Smoke test
```
.\tools\smoke.ps1 -BaseUrl "http://127.0.0.1:8000" -Ticker "VOO" -Start "2025-01-01" -End "2025-09-10" -Interval "1d" -Rf 0.02 -Mar 0.0
```

## Docker
```
docker compose up --build
```
- Docs: http://localhost:8000/docs

## Tests
```
poetry run pytest --cov=backend/app --cov-report=term-missing --cov-fail-under=85
```