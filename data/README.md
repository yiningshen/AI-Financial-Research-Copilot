# Data

Local data artifacts for development live here.

- `downloads/` holds raw source files fetched from SEC EDGAR, grouped by year.
- `markdown/` holds Docling-converted Markdown files with the same year layout and
  a manifest whose `local_path` values point to the Markdown outputs.
- Downloaded payloads are gitignored because the corpus can get large.
- Fetch a sample corpus with `uv run data/download.py` 
- Convert the downloaded HTML corpus with
  `cd backend && uv run python ../data/convert_to_markdown.py`.
- Load or refresh the converted files in `source_documents` with
  `cd backend && uv run python ingest/source_documents.py`.
- Validate Docling chunking for one filing without network or database writes with
  `cd backend && uv run python -m ingest.pipeline --accession ACCESSION_NUMBER`.
- Locate a canary chunk with `--find-text "Net Sales"`, then embed and load only
  that chunk by adding `--chunk-index INDEX --write`. Use `--all --write` only
  after the canary succeeds.
