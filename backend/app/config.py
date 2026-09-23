"""Single source of truth for backend environment configuration.

Import `settings` from this module. Never call `os.getenv` or `load_dotenv`
anywhere else in the backend.
"""

from pathlib import Path
from typing import Annotated
from urllib.parse import urlsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    # --- Supabase (Auth + API) ---
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str

    # --- Postgres ---
    # Direct/session connection. Alembic migrations, `create extension`, and index
    # creation all need session-level behaviour the transaction pooler doesn't give.
    database_url: str

    # --- OpenAI (embeddings) ---
    # The key stays optional until the embedding layer lands (build step 8); make it
    # required then so a missing key fails at startup, not mid-ingestion.
    openai_api_key: str | None = None
    openai_embedding_model: str = "text-embedding-3-small"
    # Must match the `vector(N)` column width in the migrations. Changing this after
    # ingestion means re-embedding the whole corpus.
    openai_embedding_dimensions: int = 1536

    # --- DeepSeek (generation) ---
    # OpenAI-wire-compatible, so the OpenAI SDK works against this base URL. DeepSeek
    # serves no embeddings endpoint, which is why embeddings stay on OpenAI above.
    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_chat_model: str = "deepseek-flash"

    # --- Server ---
    # Comma-separated in the environment: "http://localhost:5173,https://app.example.com"
    allowed_origins: Annotated[list[str], NoDecode]

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: str) -> list[str]:
        return [origin.strip() for origin in value.split(",") if origin.strip()]

    @property
    def sqlalchemy_database_url(self) -> str:
        """`database_url` with the psycopg3 driver named explicitly.

        SQLAlchemy resolves a bare `postgresql://` to psycopg2, which this project
        doesn't install. Supabase hands out bare URLs, so rewrite rather than ask
        everyone to remember the `+psycopg` suffix in their `.env`.
        """
        _, _, rest = self.database_url.partition("://")
        return f"postgresql+psycopg://{rest}"

    @field_validator("database_url")
    @classmethod
    def _reject_transaction_pooler(cls, value: str) -> str:
        # Port 6543 is Supabase's transaction pooler, which can't run migrations,
        # `create extension`, or index creation. The session pooler (5432) and the
        # direct connection both can, so key on the port rather than the host.
        if urlsplit(value).port == 6543:
            raise ValueError(
                "DATABASE_URL points at the Supabase transaction pooler (port 6543). "
                "Use the session pooler or direct connection on port 5432."
            )
        return value


settings = Settings()
