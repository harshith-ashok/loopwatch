# Loopwatch

Watches business journeys (login, checkout, payment, order confirmation) the way a customer does.
When one breaks it detects, investigates, decides under a written policy, acts through a fixed
action catalog, and verifies the journey passes 3 times in a row, otherwise it rolls back and
escalates. An ESP32 edge node (simulated) is both a signal source and a recovery target.

Built for SYNESIS 26. Everything here runs against a simulated shop and a simulated edge node;
no physical board and no model API key are required.

## Quick start

```bash
docker compose up -d db                                   # 1. Postgres + pgvector on :5433
cd backend && cp .env.example .env && uv sync && uv run alembic upgrade head   # 2. backend deps + schema
cd backend && LOOPWATCH_DEMO_DATA=true uv run uvicorn app.main:app --port 8000  # 3. API (with sample history)
cd frontend && npm install && npm run dev                 # 4. console at http://localhost:5173
cd backend && uv run python -m app.harness.rehearse       # 5. optional: scripted demo run
```

No Docker? `LOOPWATCH_DATABASE_URL=sqlite:////tmp/lw.db` works for a quick look (create the tables
with `uv run python -c "from app.core.db import Base,get_engine; import app.models; Base.metadata.create_all(get_engine())"`).

## The 3-minute demo

See [docs/demo-script.md](docs/demo-script.md). In short: break the order worker, watch it recover
on its own; overheat the edge node, approve the power cycle, watch verification fail and the system
roll back and escalate honestly.

## Docs

- [docs/architecture.md](docs/architecture.md): pipeline, state machine, data model
- [docs/edge.md](docs/edge.md): edge node, message schema, simulator, placeholder firmware
- [docs/results.md](docs/results.md): measured results and their limits
- [docs/hard-rules-check.md](docs/hard-rules-check.md): the ten hard rules checked against the code
- [TODO.md](TODO.md): phase plan and what was and was not done

## Commands

```bash
cd backend && uv run pytest -q                      # backend tests
cd backend && uv run python -m app.harness.run      # evaluation harness (minutes, accelerated timings)
cd frontend && npm run lint && npm run typecheck && npm test
```
