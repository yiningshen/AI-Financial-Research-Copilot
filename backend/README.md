# Backend

FastAPI service for Document Copilot. Conventions live in [AGENTS.md](AGENTS.md); fuller setup notes in [../docs/guides/backend-setup.md](../docs/guides/backend-setup.md).

## Setup

```bash
cd backend
uv sync                 # installs deps + the local `app` package (editable)
cp .env.example .env    # then fill in real values
```

`uv sync` must run before anything else — it creates `.venv` and makes `from app...` imports work.

## Run

```bash
uv run uvicorn app.main:app --reload     # http://127.0.0.1:8000
curl http://127.0.0.1:8000/health        # {"status":"ok"}
```

Interactive API docs: <http://127.0.0.1:8000/docs>

## Test and lint

```bash
uv run pytest -m "not integration"   # fast suite: no network, no DB
uv run pytest                        # includes integration tests (needs live credentials)
uv run ruff check app/
uv run ruff format app/
```

## Migrations

Alembic owns the schema. Never edit tables in the Supabase dashboard.

Not initialized yet — run `uv run alembic init alembic` once, then point `alembic/env.py` at the app metadata and `settings.database_url`. After that:

```bash
uv run alembic revision --autogenerate -m "describe change"   # then review the file
uv run alembic upgrade head
```

`DATABASE_URL` must be the direct or session connection (port 5432). The transaction pooler (6543) can't run migrations, and `app/config.py` rejects it at startup.

## Configuration

All environment access goes through `app/config.py`. Import `settings` from there; never call `os.getenv` or `load_dotenv` elsewhere. Missing required vars fail at startup with every missing name listed.

Generation runs on DeepSeek via its OpenAI-compatible API; embeddings run on OpenAI, which is why both keys exist.

## Troubleshooting

**`ModuleNotFoundError: No module named 'fastapi'` (or `'app'`)** — you ran the wrong Python. Dependencies live only in `backend/.venv`, so any other interpreter fails. Prefix commands with `uv run`, or point your editor at:

```
backend/.venv/bin/python
```

In VSCode: Cmd+Shift+P → **Python: Select Interpreter** → **Enter interpreter path...**. Opening `backend/` as the workspace folder lets VSCode find `.venv` automatically.
