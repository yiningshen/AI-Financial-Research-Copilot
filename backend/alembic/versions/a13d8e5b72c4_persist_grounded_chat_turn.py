"""Persist grounded chat citations and usage atomically.

Revision ID: a13d8e5b72c4
Revises: 9c01e2a83b47
Create Date: 2026-09-28
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a13d8e5b72c4"
down_revision: str | Sequence[str] | None = "9c01e2a83b47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_SIGNATURE = (
    "public.persist_chat_turn(uuid, uuid, text, jsonb, uuid, text, jsonb)"
)
NEW_SIGNATURE = (
    "public.persist_chat_turn(uuid, uuid, text, jsonb, uuid, text, jsonb, "
    "jsonb, jsonb)"
)


def upgrade() -> None:
    op.execute(f"drop function if exists {OLD_SIGNATURE}")
    op.execute("grant insert on public.message_citations to authenticated")
    op.execute(
        """
        create function public.persist_chat_turn(
            p_thread_id uuid,
            p_user_message_id uuid,
            p_user_content text,
            p_user_parts jsonb,
            p_assistant_message_id uuid,
            p_assistant_content text,
            p_assistant_parts jsonb,
            p_assistant_usage jsonb,
            p_citations jsonb
        )
        returns void
        language plpgsql
        security invoker
        set search_path = ''
        as $$
        begin
            if not exists (
                select 1
                from public.chat_threads
                where id = p_thread_id and user_id = auth.uid()
            ) then
                raise insufficient_privilege using message = 'Thread access denied';
            end if;

            insert into public.chat_messages (id, thread_id, role, content, parts)
            values (
                p_user_message_id,
                p_thread_id,
                'user',
                p_user_content,
                p_user_parts
            );

            insert into public.chat_messages (
                id, thread_id, role, content, parts, usage
            )
            values (
                p_assistant_message_id,
                p_thread_id,
                'assistant',
                p_assistant_content,
                p_assistant_parts,
                p_assistant_usage
            );

            insert into public.message_citations (
                message_id,
                document_id,
                chunk_id,
                position,
                quoted_text,
                page,
                section
            )
            select
                p_assistant_message_id,
                citation.document_id,
                citation.chunk_id,
                citation.position,
                citation.quoted_text,
                citation.page,
                citation.section
            from jsonb_to_recordset(coalesce(p_citations, '[]'::jsonb)) as citation(
                document_id uuid,
                chunk_id uuid,
                position integer,
                quoted_text text,
                page integer,
                section text
            );

            update public.chat_threads
            set updated_at = now()
            where id = p_thread_id;
        end;
        $$
        """
    )
    op.execute(f"revoke all on function {NEW_SIGNATURE} from public")
    op.execute(f"grant execute on function {NEW_SIGNATURE} to authenticated")


def downgrade() -> None:
    op.execute(f"drop function if exists {NEW_SIGNATURE}")
    op.execute("revoke insert on public.message_citations from authenticated")
    op.execute(
        """
        create function public.persist_chat_turn(
            p_thread_id uuid,
            p_user_message_id uuid,
            p_user_content text,
            p_user_parts jsonb,
            p_assistant_message_id uuid,
            p_assistant_content text,
            p_assistant_parts jsonb
        )
        returns void
        language plpgsql
        security invoker
        set search_path = ''
        as $$
        begin
            if not exists (
                select 1
                from public.chat_threads
                where id = p_thread_id and user_id = auth.uid()
            ) then
                raise insufficient_privilege using message = 'Thread access denied';
            end if;

            insert into public.chat_messages (id, thread_id, role, content, parts)
            values (
                p_user_message_id,
                p_thread_id,
                'user',
                p_user_content,
                p_user_parts
            );

            insert into public.chat_messages (id, thread_id, role, content, parts)
            values (
                p_assistant_message_id,
                p_thread_id,
                'assistant',
                p_assistant_content,
                p_assistant_parts
            );

            update public.chat_threads
            set updated_at = now()
            where id = p_thread_id;
        end;
        $$
        """
    )
    op.execute(f"revoke all on function {OLD_SIGNATURE} from public")
    op.execute(f"grant execute on function {OLD_SIGNATURE} to authenticated")
