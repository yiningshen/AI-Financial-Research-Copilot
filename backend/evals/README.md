# Evaluation suite

A fixed, versioned set of analyst questions with expected evidence, scored with
deterministic metrics. Run it before and after every change to prompts,
retrieval settings, chunking, or models, then compare the two reports.

## What is measured

| Area | Metric | How it is computed |
| --- | --- | --- |
| Retrieval | `retrieval.hit_rate` | Share of answerable cases where at least one expected evidence passage came back from `DocumentRetriever.search`. |
| | `retrieval.evidence_recall` | Mean share of each case's expected evidence passages that were retrieved (seeds or neighbors). |
| | `retrieval.mrr` | Mean reciprocal rank of the first fused seed that brought in expected evidence. A neighbor inherits its seed's rank. |
| Citations | `answers.citation_precision` | Share of validated sources that come from an expected filing (accession number). |
| | `answers.cited_evidence_recall` | Share of expected evidence passages that the answer actually cites, not just retrieves. |
| Grounding | `answers.fact_recall` | Share of expected key facts (e.g. `34%`, `Hopper`) present in the answer text. |
| | `answers.unverified_number_cases` | Answered cases containing a number that appears in none of the cited chunks. A hallucination signal to inspect by hand, since derived figures also show up here. |
| | `answers.errors` | Runs that failed closed: grounding retries or usage limits were exhausted. |
| Refusal | `answers.abstention_accuracy` | Out-of-corpus questions answered with `insufficient_evidence`. |
| | `answers.refusal_accuracy` | Investment-advice questions answered with `refused`. |
| | `answers.false_answer_rate` | Share of unanswerable questions that got an `answered` response. This is the costliest failure, so its target is 0. |
| Overall | `answers.status_accuracy`, `answers.answer_rate` | Expected status matched, and share of answerable questions actually answered (low means over-refusal). |
| Performance | `retrieval.latency_p50_s`, `retrieval.latency_p95_s` | Wall time per `DocumentRetriever.search` call (nearest-rank percentiles). |
| | `agent.latency_p50_s`, `agent.latency_p95_s` | Wall time per full agent run, including grounding retries. |
| | `agent.mean_requests`, `agent.mean_tool_calls`, `agent.total_tokens` | Averages and totals over runs that completed. Extra requests usually mean grounding retries. |
| | `agent.estimated_cost_usd` | Total DeepSeek cost for the run. It's `None` until the `DEEPSEEK_*_USD_PER_MTOK` prices are set. |

Every answer the agent returns has already passed `GroundingValidator`: quotes
exist verbatim in passages retrieved during the run, and every paragraph is
cited. The suite measures what the validator can't, which is whether the *right*
evidence was found and cited and whether the model abstains when it should.

## Running

Fast tests check the scorers and the gold set without any network access.
`test_cases.py` checks that every expected phrase exists in the local filing
Markdown, so a typo can't silently score as a retrieval miss:

```bash
cd backend
uv run pytest tests/evals
```

Live runs load `backend/.env` and make billable OpenAI embedding requests, plus
DeepSeek requests for the agent stage:

```bash
uv run python -m evals.run --stage retrieval   # cheap: embeddings + Supabase
uv run python -m evals.run                     # retrieval + full agent
uv run python -m evals.run --case nvda-data-center-2025 --stage agent
uv run python -m evals.run --baseline evals/reports/<earlier>.json --enforce
```

Each run writes `evals/reports/<timestamp>.json` (gitignored) with the summary,
config, git commit, per-case scores, answer text, and cited quotes.
Each agent case also records its latency, token usage, estimated cost, and
`trace_id`. When `LOGFIRE_TOKEN` is set, every case is exported as its own
trace, so a slow, expensive, or wrong case can be opened straight from the
report (see "Observability" in `backend/README.md`).
`--baseline` prints deltas against an earlier report. `--enforce` exits 1 when
any threshold in `cases.json` is missed.

## Adding a case

Add an entry to `cases.json`:

- `expected_status` lists the acceptable statuses.
- Answerable cases need `evidence` items. Each one is an accession number plus a
  short **prose** phrase from that filing. Avoid table cells: chunks re-serialize
  tables, so table text won't match the local Markdown.
- Use `facts` for key values the answer must state. Each fact is a list of
  acceptable surface forms.
- Use `extra_citable_accessions` when another filing legitimately reports the
  same figure, such as a later 10-K restating a prior year.
- `filters` are used only by the retrieval stage. In the agent stage, the agent
  picks its own filters.

Unanswerable cases (`insufficient_evidence`, `refused`) must not list evidence or
facts. When you change what a case means, bump `version` so that reports from
different suite versions aren't compared as like for like.

The initial thresholds are targets, not a measured baseline. Calibrate them
after the first full run.
