# Build checklist

Order follows [architecture.md](architecture.md#implementation-sequence): stand up the shared dependency (Supabase) first, scaffold both service skeletons, wire a thin end-to-end slice (auth + stubbed chat round-trip), then deepen retrieval, grounding, and UI. Don't fully build one side before touching the other — verify the wiring early with a stub.

## 0. Prerequisites

- [ ] Install Python 3.12+, `uv`, Node 20+, `pnpm` (see [README.md](../README.md#prerequisites))
- [ ] Create OpenAI API key (hold off adding it until step 6/8 actually need it)

## 1. Supabase project

- [ ] Create account + project ([guides/supabase-setup.md](guides/supabase-setup.md))
- [ ] Collect Project URL, anon key, service_role key, direct DB connection string
- [ ] Enable email auth, disable "Confirm email" for local dev
- [ ] Store credentials in `backend/.env` and `frontend/.env` (never commit; `.env.example` already tracks the shape)

## 2. Scaffold both skeletons

- [ ] Backend: `uv sync`, add deps per [guides/backend-setup.md](guides/backend-setup.md), create `app/main.py` with a health check route
- [ ] Backend: `app/config.py` — pydantic-settings, fails fast on missing env vars
- [ ] Backend: confirm `uv run uvicorn app.main:app --reload` serves the health check
- [ ] Frontend: `pnpm create vite . --template react-ts`, add deps per [guides/frontend-setup.md](guides/frontend-setup.md)
- [ ] Frontend: `src/lib/env.ts` — validates `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`
- [ ] Frontend: confirm `pnpm dev` renders a blank shell and `pnpm tsc --noEmit` / `pnpm lint` pass

## 3. Database schema

- [ ] `app/database/models/` — SQLAlchemy models, one per file: `users`, `chat_threads`, `chat_messages`, `message_citations`, `source_documents`, `document_chunks`
- [ ] `uv run alembic init alembic`, point `env.py` at app metadata + direct (session) DB URL from settings
- [ ] `uv run alembic revision --autogenerate -m "initial schema"`, review the generated file
- [ ] Hand-add what autogenerate can't infer: `create extension if not exists vector`, `vector(1536)` column, generated `tsvector` column, HNSW index, GIN index, RLS policies
- [ ] `uv run alembic upgrade head` against the Supabase direct connection

## 4. Auth (thin slice)

- [ ] Frontend: `src/lib/supabase.ts` browser client, sign-in/sign-up screen, session persistence
- [ ] Backend: `app/auth/dependencies.py` — verify `Authorization: Bearer <token>` via Supabase Auth, expose `get_current_user`
- [ ] Verify: signed-in browser session can hit an authenticated backend route and get the right `user_id` back

## 5. Frontend API client

- [ ] `src/lib/http.ts` — `fetch` wrapper: base URL, bearer token injection, timeouts, typed `ApiError` (+ `isNetworkError`)
- [ ] `src/lib/api.ts` — product calls: create/list threads, fetch message history

## 6. Stubbed chat round-trip

- [ ] Backend: `POST /chat/stream` returning a hardcoded streamed response (no LLM yet) per [architecture.md](architecture.md#streaming-contract)
- [ ] Frontend: `useChat` wired to `${apiBaseUrl}/chat/stream` with bearer header, rendering the stub reply
- [ ] Verify end-to-end: sign in → send message → see streamed stub text in browser

## 7. Ingestion pipeline

- [ ] `data/download.py` — pull sample 10-Ks from SEC EDGAR (already exists — run it, confirm `data/downloads/` + `manifest.json`)
- [ ] `backend/ingest/` — HTML → normalized Markdown extraction, write to `source_documents`
- [ ] Chunking with page/section metadata → `document_chunks`
- [ ] Embed chunks via OpenAI, store vectors
- [ ] Run ingestion against the 5-company sample corpus (AAPL, AMZN, GOOGL, MSFT, NVDA, FY2021–2025)

## 8. Retrieval

- [ ] `app/retrieval/queries.py` — `pgvector` semantic query
- [ ] `app/retrieval/queries.py` — Postgres full-text query against generated `tsvector`
- [ ] `app/retrieval/fusion.py` — Reciprocal Rank Fusion combining both ranked lists
- [ ] `app/retrieval/retriever.py` — query → source passages, with neighboring-chunk fetch for grounding
- [ ] Unit tests for retrieval (mock DB boundary, no live network per [backend/AGENTS.md](../backend/AGENTS.md#tests))

## 9. PydanticAI agent

- [ ] `app/assistant/deps.py` — `DocumentAgentDeps` (user_id, thread_id, retriever, grounding_validator)
- [ ] `app/assistant/outputs.py` — `GroundedAnswer`, `Citation`, `SourcePassage`
- [ ] `app/assistant/instructions.md` — product contract: cite everything, refuse beyond-corpus inference, no stock advice
- [ ] `app/assistant/agent.py` — bounded tools: `search_filings`, `read_chunk`, `read_surrounding_chunks`
- [ ] `app/chat/orchestrator.py` — wire the real agent into the chat turn, replacing the step-6 stub

## 10. Grounding enforcement

- [ ] `app/grounding/validator.py` — every claim has a citation; every citation maps to a retrieved chunk; block citations to non-retrieved documents
- [ ] Controlled failure path when validation fails (no "confident but ungrounded" answers reach the user)
- [ ] Unit tests covering citation extraction + grounding enforcement (this is the trust contract — test it hardest)

## 11. Persistence

- [ ] `app/database/chats.py` — persist thread, user message, assistant message, citations, usage metadata after a successful run
- [ ] Frontend: load thread list + message history on chat open (own threads only — verify 403 on cross-user access)

## 12. Final UI

- [ ] `src/components/chat/*` — citations, expandable source passage, empty states, streaming/error states
- [ ] Friendly error rendering for the `401/403/404/422/502/500` classes in [architecture.md](architecture.md#error-handling)

## 13. Validate against the brief

- [ ] Manually run the 10 example analyst questions from [client-brief.md](client-brief.md#example-analyst-questions) — every answer cited, no hallucinated claims
- [ ] Confirm the bot refuses to over-infer on question 10 (generative AI margin impact) — this is the one it's supposed to punt on
- [ ] Confirm no stock recommendations ever surface (explicit out-of-scope item)

## 14. Deploy

- [ ] Railway: backend service (Uvicorn) with env vars set
- [ ] Railway: frontend service (static Vite build) with env vars set
- [ ] `ALLOWED_ORIGINS` configured for CORS between the two Railway URLs
- [ ] Smoke test signed-in chat flow against deployed URLs

## 15. Pilot

- [ ] Onboard the 5 senior-analyst pilot group with real Driftwood email logins
- [ ] Track whether the pilot reports ≥3 hours/analyst/week saved — this is the actual definition of done
