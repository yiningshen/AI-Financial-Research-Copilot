"""Add application user creation on Supabase signup.

Revision ID: e3b6f7a91c24
Revises: 642137246ab7
Create Date: 2026-09-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e3b6f7a91c24"
down_revision: str | Sequence[str] | None = "642137246ab7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create public.users rows when Supabase creates auth users."""
    op.execute(
        """
        create function public.handle_new_user()
        returns trigger
        language plpgsql
        security definer set search_path = ''
        as $$
        begin
            insert into public.users (id, email, full_name)
            values (new.id, new.email, new.raw_user_meta_data ->> 'full_name');
            return new;
        end;
        $$
        """
    )
    op.execute(
        """
        create trigger on_auth_user_created
            after insert on auth.users
            for each row execute procedure public.handle_new_user()
        """
    )
    # Preserve accounts created before this trigger was installed.
    op.execute(
        """
        insert into public.users (id, email, full_name, created_at)
        select id, email, raw_user_meta_data ->> 'full_name', created_at
        from auth.users
        where email is not null
        on conflict (id) do nothing
        """
    )


def downgrade() -> None:
    """Remove automatic profile creation without deleting user data."""
    op.execute("drop trigger if exists on_auth_user_created on auth.users")
    op.execute("drop function if exists public.handle_new_user()")
