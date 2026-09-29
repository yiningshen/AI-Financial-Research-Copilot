# Build checklist

Order follows [architecture.md](architecture.md#implementation-sequence): stand up the shared dependency (Supabase) first, scaffold both service skeletons, wire a thin end-to-end slice (auth + stubbed chat round-trip), then deepen retrieval, grounding, and UI. Don't fully build one side before touching the other — verify the wiring early with a stub.

## Progress audit (2026-09-28)

- Checklist count: 55 of 79 items complete (70%); grounding work appears in both sections 9 and 10, so this is a tracking ratio rather than an effort estimate.
- Automated checks: 82 backend tests pass (2 live integration tests excluded); frontend type-check, lint, and production build pass.
- Live integration: the grounded agent retrieved Apple filing evidence through OpenAI/Supabase, generated with DeepSeek, and passed citation validation.
- Live database: Alembic reports revision `a13d8e5b72c4 (head)`.
- Local corpus: all 25 Markdown filings across five companies are present.
- Items requiring a browser, Supabase dashboard, live LLM call, deployment, or pilot evidence remain unchecked unless a prior manual verification is recorded below.
- Current implementation boundary: ingestion, retrieval, the PydanticAI agent, grounding enforcement, and citation-aware persistence/streaming are complete; final citation UI, full brief validation, deployment, and pilot remain.

## 0. Prerequisites

- [x] Install Python 3.12+, `uv`, Node 20+, `pnpm` (see [README.md](../README.md#prerequisites)) — Python 3.12.14, uv 0.12.5, Node v22.20.0, and pnpm 12.6.0 are present
- [x] Create OpenAI API key (hold off adding it until step 6/8 actually need it)

## 1. Supabase project

- [x] Create account + project ([guides/supabase-setup.md](guides/supabase-setup.md))
- [x] Collect Project URL, anon key, service_role key, direct DB connection string
- [ ] Enable email auth, disable "Confirm email" for local dev — not verifiable from the repo; confirm in the dashboard
- [x] Store credentials in `backend/.env` and `frontend/.env` (never commit; `.env.example` already tracks the shape)

## 2. Scaffold both skeletons

- [x] Backend: `uv sync`, add deps per [guides/backend-setup.md](guides/backend-setup.md), create `app/main.py` with a health check route
- [x] Backend: `app/config.py` — pydantic-settings, fails fast on missing env vars
- [x] Backend: confirm `uv run uvicorn app.main:app --reload` serves the health check
- [x] Frontend: `pnpm create vite . --template react-ts`, add deps per [guides/frontend-setup.md](guides/frontend-setup.md)
- [x] Frontend: `src/lib/env.ts` — validates `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`
- [x] Frontend: `pnpm tsc --noEmit`, `pnpm lint`, and `pnpm build` pass
- [ ] Frontend: run `pnpm dev` and manually verify the app shell in a browser

## 3. Database schema

- [x] `app/database/models/` — SQLAlchemy models, one per file: `users`, `chat_threads`, `chat_messages`, `message_citations`, `source_documents`, `document_chunks`
- [x] `uv run alembic init alembic`, point `env.py` at app metadata + direct (session) DB URL from settings
- [x] `uv run alembic revision --autogenerate -m "initial schema"`, review the generated file
- [x] Hand-add what autogenerate can't infer: `create extension if not exists vector`, `vector(1536)` column, generated `tsvector` column, HNSW index, GIN index, RLS policies (also the `users.id` → `auth.users` FK, and the missing `import pgvector.sqlalchemy` autogenerate omits)
- [x] `uv run alembic upgrade head` against the Supabase direct connection — current at grounded-turn persistence revision `a13d8e5b72c4`

## 4. Auth (thin slice)

- [ ] Frontend auth: browser client, sign-in screen, and session persistence exist; add the missing sign-up screen
- [x] Backend: `app/auth/dependencies.py` — verify `Authorization: Bearer <token>` via Supabase Auth, expose `get_current_user`
- [ ] Verify: signed-in browser session can hit an authenticated backend route and get the right `user_id` back

## 5. Frontend API client

- [x] `src/lib/http.ts` — `fetch` wrapper: base URL, bearer token injection, timeouts, typed `ApiError` (+ `isNetworkError`)
- [x] `src/lib/api.ts` — product calls: create/list threads, fetch message history

## 6. Stubbed chat round-trip

- [x] Backend: `POST /chat/stream` returning a hardcoded streamed response (no LLM yet) per [architecture.md](architecture.md#streaming-contract)
- [x] React Router: login, chat list, chat thread routes
- [x] AI SDK chat primitives pointed at `POST /chat/stream` with Supabase bearer token
- [x] Thread sidebar (past conversations)
- [x] Basic message list + input + streaming indicator
- [ ] Verify in a browser: create a thread, send a question, see a grounded streamed response, then reload and see history

## 7. Ingestion pipeline

Goal: SEC filings in the corpus are parsed, chunked, embedded, and stored in Supabase.

- [x] `ingest/` scripts (or CLI entrypoint) for one-off corpus loading
- [x] HTML → normalized Markdown extraction (preserve page/section metadata)
- [x] Chunking strategy (size + overlap; store chunk index, page, section, ticker, filing type, year)
- [x] Write `source_documents` rows with filing metadata from `manifest.json`
- [x] Write `document_chunks` rows with text + metadata
- [x] OpenAI embedding generation → store `vector(1536)` per chunk
- [x] Generated `tsvector` populated for full-text search
- [x] Idempotent re-run (skip already-ingested documents)
- [x] Unit tests: chunking logic, metadata extraction
- [x] Run ingestion on full sample corpus (25 filings × 5 companies)
- [x] Verify: chunks exist in Supabase; spot-check a known passage (e.g. Apple revenue mix table)

## 8. Retrieval

Reference pattern: [AI Cookbook hybrid retrieval](https://github.com/daveebbelaar/ai-cookbook/tree/main/knowledge/hybrid-retrieval) — independent lexical and dense candidate sets, rank-only RRF (`k=60`), then a bounded final result set. This implementation uses the project's locked Postgres full-text + `pgvector` stack instead of the tutorial's local BM25/NumPy indexes.

- [x] `app/retrieval/queries.py` — `pgvector` semantic query
- [x] `app/retrieval/queries.py` — Postgres full-text query against generated `tsvector`
- [x] `app/retrieval/fusion.py` — Reciprocal Rank Fusion combining both ranked lists
- [x] `app/retrieval/retriever.py` — query → typed source passages, with neighboring-chunk fetch for grounding and PydanticAI-ready `search`, `read_chunk`, and `read_surrounding_chunks` methods
- [x] Unit tests for retrieval (mock DB boundary, no live network per [backend/AGENTS.md](../backend/AGENTS.md#tests))
- [x] Apply retrieval RPC migration and smoke-test hybrid search against the ingested Supabase corpus

## 9. PydanticAI agent

- [x] `app/assistant/instructions.md` — product contract: cite everything, refuse to invent or infer beyond the corpus, and provide no stock picks or investment advice
- [x] PydanticAI agent with typed dependencies in `app/assistant/deps.py` — request identity, retriever, grounding validator, and a per-run evidence ledger
- [x] Typed agent output in `app/assistant/outputs.py` — `GroundedAnswer`, `Citation`, `SourcePassage`
- [x] `app/assistant/agent.py` — bounded tools: `search_filings`, `read_chunk`, `read_surrounding_chunks`
- [x] `app/chat/orchestrator.py` — one turn: trusted history → agent → validate → prepared stream result
- [x] `app/grounding/validator.py` — every citation maps to a passage retrieved during the current run; fail closed on any violation
- [x] `app/chat/streaming.py` — AI SDK-compatible validated text and `data-citation` parts, then persist
- [x] Persist `message_citations` and usage atomically with the successfully stored assistant message
- [x] Unit tests: typed agent output, evidence ledger, citation validation, grounding enforcement, history conversion, streaming, and persistence
- [ ] Verify against the [client-brief example questions](client-brief.md#example-analyst-questions):
  - [ ] Answers cite specific filings and pages or sections
  - [ ] Under-specified questions return a clear "not enough evidence" response
  - [ ] Question 10 (generative AI margin impact) refuses to infer beyond the filings

## 10. Grounding enforcement

- [x] `app/grounding/validator.py` — every answer paragraph/bullet has a citation; every citation maps to a retrieved chunk; block citations to non-retrieved documents
- [x] Controlled failure path when validation fails (no "confident but ungrounded" answers reach the user)
- [x] Unit tests covering citation extraction + grounding enforcement (this is the trust contract — test it hardest)

## 11. Persistence

- [x] `app/database/chats.py` — atomically persist user message, assistant message, citations, usage metadata, and thread timestamp after a successful run
- [x] Frontend: load thread list + message history on chat open; backend ownership checks return 403 for another user's thread

## 12. Final UI

Goal: analysts can verify every claim in one click — this is what makes the product usable.

- [ ] Citation chips/links on assistant messages (company, filing type, date, page/section)
- [ ] Source passage panel — show the underlying excerpt for the selected citation
- [ ] Empty states (no threads, no corpus match)
- [ ] Error states (auth expired, retrieval failure, grounding failure, network/CORS); map the `401/403/404/422/502/500` classes defined in [architecture.md](architecture.md#error-handling)
- [ ] Loading/streaming status during the assistant run
- [ ] Verify: click a citation → see the exact passage from the filing

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
