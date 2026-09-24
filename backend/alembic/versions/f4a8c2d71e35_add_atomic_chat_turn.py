"""Add atomic chat-turn persistence.

Revision ID: f4a8c2d71e35
Revises: e3b6f7a91c24
Create Date: 2026-09-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f4a8c2d71e35"
down_revision: str | Sequence[str] | None = "e3b6f7a91c24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FUNCTION_SIGNATURE = (
    "public.persist_chat_turn(uuid, uuid, text, jsonb, uuid, text, jsonb)"
)


def upgrade() -> None:
    """Persist both sides of a completed turn in one transaction."""
    op.execute(
        "grant select, insert, update on public.chat_threads to authenticated"
    )
    op.execute("grant select, insert on public.chat_messages to authenticated")
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
    op.execute(f"revoke all on function {FUNCTION_SIGNATURE} from public")
    op.execute(f"grant execute on function {FUNCTION_SIGNATURE} to authenticated")


def downgrade() -> None:
    """Remove the chat-turn function and its explicit table grants."""
    op.execute(f"drop function if exists {FUNCTION_SIGNATURE}")
    op.execute("revoke select, insert on public.chat_messages from authenticated")
    op.execute(
        "revoke select, insert, update on public.chat_threads from authenticated"
    )
