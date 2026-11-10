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

```bash
uv run alembic revision --autogenerate -m "describe change"   # then review the file
uv run alembic upgrade head
```

`DATABASE_URL` must be the direct or session connection (port 5432). The transaction pooler (6543) can't run migrations, and `app/config.py` rejects it at startup.

## Configuration

All environment access goes through `app/config.py`. Import `settings` from there; never call `os.getenv` or `load_dotenv` elsewhere. Missing required vars fail at startup with every missing name listed.

Generation runs on DeepSeek via its OpenAI-compatible API; embeddings run on OpenAI, which is why both keys exist.

Retrieval defaults and agent execution budgets are also validated in
`app/config.py`. They can be overridden with `RETRIEVAL_*` and
`AGENT_MAX_*` environment variables documented in `.env.example`; invalid
values fail during startup.

The hybrid search stages, concurrency model, live smoke test, and grounding
contract are documented in [app/retrieval/README.md](app/retrieval/README.md).

## Observability

`app/observability.py` configures [Pydantic Logfire](https://logfire.pydantic.dev)
(OpenTelemetry) at API startup and in the eval runner. Every chat turn is one
trace:

```text
chat turn                           thread, answer status, tokens, estimated cost
└─ agent run                        PydanticAI: messages and final output
   ├─ chat deepseek-flash           one per model request: latency, tokens
   ├─ running tool: search_filings  tool arguments and result
   │  └─ retrieval.search           filters, passages, seeds
   │     ├─ openai embedding …      latency, input tokens
   │     ├─ supabase rpc …_full_text / …_semantic    latency, rows (concurrent)
   │     └─ supabase rpc get_document_chunk_windows  latency, rows
   └─ chat deepseek-flash           grounding retries show up as extra requests
```

Exceptions are recorded on the span that raised them, and `logger.exception`
calls in the API land in the same trace.

| Variable | Default | Purpose |
| --- | --- | --- |
| `LOGFIRE_TOKEN` | unset | Write token for a Logfire project. Without it, spans are created but not exported. |
| `LOGFIRE_ENVIRONMENT` | `local` | Environment tag for filtering, e.g. `production`. |
| `LOGFIRE_INCLUDE_CONTENT` | `true` | Put prompts, tool arguments, retrieved text, and search queries on spans. Diagnosing wrong answers needs this; set it to `false` if traces must not hold analyst questions. |
| `DEEPSEEK_INPUT_USD_PER_MTOK`, `DEEPSEEK_OUTPUT_USD_PER_MTOK` | unset | Prices from DeepSeek's pricing page. Both are required to enable cost estimates. |
| `DEEPSEEK_CACHED_INPUT_USD_PER_MTOK` | input price | Price for cache-hit input tokens. |

The estimated cost covers DeepSeek generation only. Query embeddings cost a
fraction of a cent per thousand searches; their token counts are recorded on
the embedding spans. Each persisted assistant message's `usage` JSON also stores
token counts and `estimated_cost_usd`, so cost is queryable without Logfire.

Useful Logfire queries:

- Slow turns: `span_name = 'chat turn'`, sorted by duration, then open the
  trace to see whether time went to model requests, retries, or Supabase RPCs.
- Expensive turns: `attributes->>'usage.estimated_cost_usd'` on `chat turn`.
- Grounding retries: `chat turn` spans where `usage.requests` is above the
  usual two (one tool round plus the final answer).

## Troubleshooting

**`ModuleNotFoundError: No module named 'fastapi'` (or `'app'`)** — you ran the wrong Python. Dependencies live only in `backend/.venv`, so any other interpreter fails. Prefix commands with `uv run`, or point your editor at:

```
backend/.venv/bin/python
```

In VSCode: Cmd+Shift+P → **Python: Select Interpreter** → **Enter interpreter path...**. Opening `backend/` as the workspace folder lets VSCode find `.venv` automatically.
