
## Run

```
docker compose up -d db          # from repo root; Postgres+pgvector on :5433
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
uv run pytest -q
```
