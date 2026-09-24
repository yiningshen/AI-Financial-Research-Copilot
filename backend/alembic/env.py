from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from app.config import settings
from app.database.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


# Lives in the migration rather than the models, because the models can't express a
# foreign key into the Supabase-owned `auth` schema. Autogenerate sees it in the
# database, doesn't find it in the metadata, and proposes dropping it every run.
MIGRATION_OWNED_CONSTRAINTS = {"fk_users_auth_users"}


def include_object(obj, name, type_, reflected, compare_to):
    """Keep autogenerate off objects the app doesn't own.

    Without this, a diff against the live database proposes dropping everything in
    `auth`, `storage`, and friends.
    """
    if type_ == "table" and obj.schema not in (None, "public"):
        return False
    return not (
        type_ == "foreign_key_constraint" and name in MIGRATION_OWNED_CONSTRAINTS
    )


def run_migrations_offline() -> None:
    context.configure(
        url=settings.sqlalchemy_database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Built from settings rather than alembic.ini: ConfigParser would try to
    # interpolate a `%` in the database password, and config.py is the one place
    # environment is read.
    engine = create_engine(settings.sqlalchemy_database_url, pool_pre_ping=True)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
