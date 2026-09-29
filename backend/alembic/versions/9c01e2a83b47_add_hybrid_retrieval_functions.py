"""Add bounded hybrid retrieval database functions.

Revision ID: 9c01e2a83b47
Revises: f4a8c2d71e35
Create Date: 2026-09-26
"""

from collections.abc import Sequence

from alembic import op

revision: str = "9c01e2a83b47"
down_revision: str | Sequence[str] | None = "f4a8c2d71e35"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEMANTIC_SIGNATURE = (
    "public.search_document_chunks_semantic(vector,integer,text[],text[],integer[])"
)
FULL_TEXT_SIGNATURE = (
    "public.search_document_chunks_full_text(text,integer,text[],text[],integer[])"
)
WINDOW_SIGNATURE = "public.get_document_chunk_windows(uuid[],integer)"


def upgrade() -> None:
    """Create fixed SQL entrypoints used by the retrieval service."""
    op.execute("grant select on public.source_documents to authenticated")
    op.execute("grant select on public.document_chunks to authenticated")
    op.execute(
        """
        create function public.search_document_chunks_semantic(
            p_query_embedding vector(1536),
            p_match_count integer default 50,
            p_tickers text[] default null,
            p_forms text[] default null,
            p_fiscal_years integer[] default null
        )
        returns table (chunk_id uuid, score double precision)
        language sql
        stable
        security invoker
        set search_path = ''
        as $$
            select
                c.id as chunk_id,
                (
                    1 - (
                        c.embedding operator(public.<=>) p_query_embedding
                    )
                )::double precision as score
            from public.document_chunks as c
            join public.source_documents as d on d.id = c.document_id
            where c.embedding is not null
              and (p_tickers is null or d.ticker = any(p_tickers))
              and (p_forms is null or d.form = any(p_forms))
              and (p_fiscal_years is null or d.fiscal_year = any(p_fiscal_years))
            order by c.embedding operator(public.<=>) p_query_embedding, c.id
            limit greatest(1, least(p_match_count, 100));
        $$
        """
    )
    op.execute(
        """
        create function public.search_document_chunks_full_text(
            p_query text,
            p_match_count integer default 50,
            p_tickers text[] default null,
            p_forms text[] default null,
            p_fiscal_years integer[] default null
        )
        returns table (chunk_id uuid, score double precision)
        language sql
        stable
        security invoker
        set search_path = ''
        as $$
            with parsed_query as (
                select websearch_to_tsquery('pg_catalog.english', p_query) as value
            )
            select
                c.id as chunk_id,
                ts_rank_cd(c.search_vector, q.value)::double precision as score
            from public.document_chunks as c
            join public.source_documents as d on d.id = c.document_id
            cross join parsed_query as q
            where c.search_vector @@ q.value
              and (p_tickers is null or d.ticker = any(p_tickers))
              and (p_forms is null or d.form = any(p_forms))
              and (p_fiscal_years is null or d.fiscal_year = any(p_fiscal_years))
            order by score desc, c.id
            limit greatest(1, least(p_match_count, 100));
        $$
        """
    )
    op.execute(
        """
        create function public.get_document_chunk_windows(
            p_chunk_ids uuid[],
            p_radius integer default 1
        )
        returns table (
            seed_chunk_id uuid,
            seed_rank integer,
            distance integer,
            chunk_id uuid,
            document_id uuid,
            chunk_index integer,
            content text,
            token_count integer,
            page integer,
            section text,
            metadata jsonb,
            ticker text,
            company_name text,
            form text,
            filing_date date,
            report_date date,
            fiscal_year integer,
            accession_number text,
            source_url text
        )
        language sql
        stable
        security invoker
        set search_path = ''
        as $$
            select
                requested.chunk_id as seed_chunk_id,
                requested.seed_rank::integer,
                abs(neighbor.chunk_index - seed.chunk_index)::integer as distance,
                neighbor.id as chunk_id,
                neighbor.document_id,
                neighbor.chunk_index,
                neighbor.content,
                neighbor.token_count,
                neighbor.page,
                neighbor.section,
                neighbor.metadata,
                document.ticker::text,
                document.company_name,
                document.form::text,
                document.filing_date,
                document.report_date,
                document.fiscal_year,
                document.accession_number::text,
                document.source_url
            from unnest(p_chunk_ids) with ordinality
                as requested(chunk_id, seed_rank)
            join public.document_chunks as seed on seed.id = requested.chunk_id
            join public.document_chunks as neighbor
              on neighbor.document_id = seed.document_id
             and neighbor.chunk_index between
                 seed.chunk_index - greatest(0, least(p_radius, 5))
                 and seed.chunk_index + greatest(0, least(p_radius, 5))
            join public.source_documents as document
              on document.id = neighbor.document_id
            order by requested.seed_rank, neighbor.chunk_index, neighbor.id;
        $$
        """
    )

    for signature in (SEMANTIC_SIGNATURE, FULL_TEXT_SIGNATURE, WINDOW_SIGNATURE):
        op.execute(f"revoke all on function {signature} from public")
        op.execute(f"grant execute on function {signature} to authenticated")
        op.execute(f"grant execute on function {signature} to service_role")


def downgrade() -> None:
    """Remove the retrieval entrypoints and explicit corpus grants."""
    op.execute(f"drop function if exists {WINDOW_SIGNATURE}")
    op.execute(f"drop function if exists {FULL_TEXT_SIGNATURE}")
    op.execute(f"drop function if exists {SEMANTIC_SIGNATURE}")
    op.execute("revoke select on public.document_chunks from authenticated")
    op.execute("revoke select on public.source_documents from authenticated")
