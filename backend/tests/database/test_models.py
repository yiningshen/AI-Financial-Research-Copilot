"""Guards the one failure mode of one-model-per-file: an unimported module.

Alembic only sees tables registered on `Base.metadata`. A new model file that
nobody imports produces no table and no migration, silently.
"""

import pkgutil

from app.database import models
from app.database.models import Base

EXPECTED_TABLES = {
    "users",
    "chat_threads",
    "chat_messages",
    "message_citations",
    "source_documents",
    "document_chunks",
}


def test_metadata_matches_expected_tables():
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_every_model_module_is_imported():
    """Every module in the package must contribute a table, so none is orphaned."""
    modules = {
        name
        for _, name, _ in pkgutil.iter_modules(models.__path__)
        if name not in {"base"}
    }
    tables_by_module = {
        table.__module__.rsplit(".", 1)[-1] for table in Base.__subclasses__()
    }
    assert modules == tables_by_module, (
        f"model modules not registered on Base.metadata: {modules - tables_by_module}"
    )
