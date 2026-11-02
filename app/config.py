from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # SQLite works locally; point this at PostgreSQL (e.g. Amazon RDS) in production:
    # postgresql+psycopg://user:pass@host:5432/extractor
    database_url: str = "sqlite:///./extractor.db"

    # "local" keeps uploads on disk; "s3" stores them in S3_BUCKET.
    storage_backend: str = "local"
    local_storage_dir: str = "./uploads"
    s3_bucket: str | None = None

    claude_model: str = "claude-opus-5-5"
    max_upload_mb: int = 20


settings = Settings()
