"""Title chat threads from their first user question.

Revision ID: b6d4c8e91f20
Revises: a13d8e5b72c4
Create Date: 2026-10-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b6d4c8e91f20"
down_revision: str | Sequence[str] | None = "a13d8e5b72c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_persist_function(*, update_title: bool) -> None:
    title_assignment = """
                title = coalesce(
                    title,
                    nullif(
                        left(
                            regexp_replace(
                                btrim(p_user_content),
                                '[[:space:]]+',
                                ' ',
                                'g'
                            ),
                            200
                        ),
                        ''
                    )
                ),
            """ if update_title else ""
    op.execute(
        f"""
        create or replace function public.persist_chat_turn(
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
            set
                {title_assignment}
                updated_at = now()
            where id = p_thread_id;
        end;
        $$
        """
    )


def upgrade() -> None:
    op.execute(
        """
        update public.chat_threads as thread
        set title = left(
            regexp_replace(btrim(first_message.content), '[[:space:]]+', ' ', 'g'),
            200
        )
        from (
            select distinct on (thread_id) thread_id, content
            from public.chat_messages
            where role = 'user'
            order by thread_id, created_at, id
        ) as first_message
        where thread.id = first_message.thread_id
          and (thread.title is null or btrim(thread.title) in ('', 'New chat'))
        """
    )
    op.execute(
        """
        update public.chat_threads as thread
        set title = null
        where btrim(coalesce(thread.title, '')) in ('', 'New chat')
          and not exists (
              select 1
              from public.chat_messages as message
              where message.thread_id = thread.id and message.role = 'user'
          )
        """
    )
    _create_persist_function(update_title=True)


def downgrade() -> None:
    _create_persist_function(update_title=False)
