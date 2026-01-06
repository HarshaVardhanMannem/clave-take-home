"""
Application Settings Configuration
Loads environment variables and provides typed configuration
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Database - supports multiple naming conventions
    supabase_db_url: str | None = None

    # Alternative Supabase config (will be converted to db_url)
    supabase_url: str | None = None
    supabase_key: str | None = None  # Not used for direct DB, but allowed
    supabase_password: str | None = None  # DB password

    # LLM Provider Selection
    llm_provider: str = "nvidia"  # "nvidia" or "grok"
    
    # NVIDIA API (kept for backward compatibility, disabled when llm_provider != "nvidia")
    nvidia_api_key: str | None = None
    nvidia_model: str = "ai-nemotron-3-nano-30b-a3b"
    
    # Grok/XAI API
    grok_api_key: str | None = None
    grok_model: str = "grok-2"  # Default Grok model (grok-2, grok-beta, or grok-2-1212)
    grok_base_url: str = "https://api.x.ai/v1"  # xAI API base URL

    # JWT Authentication
    jwt_secret_key: str | None = None  # Optional - will derive from API key if not set
    jwt_access_token_expire_minutes: int = 60 * 24  # 24 hours

    # Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Query settings
    max_query_timeout: int = 30
    max_retries: int = 2

    # Logging
    log_level: str = "INFO"

    # Database pool settings
    db_pool_min_size: int = 5
    db_pool_max_size: int = 20
    db_command_timeout: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra environment variables
    )

    def get_database_url(self) -> str:
        """Get the database connection URL, constructing it if necessary"""
        # If full URL is provided, use it
        if self.supabase_db_url:
            return self.supabase_db_url

        # Try to construct from supabase_url
        if self.supabase_url and self.supabase_password:
            # Extract project ref from URL like https://xxxxx.supabase.co
            project_ref = self.supabase_url.replace("https://", "").replace(".supabase.co", "")
            return f"postgresql://postgres:{self.supabase_password}@db.{project_ref}.supabase.co:5432/postgres"

        raise ValueError(
            "Database URL not configured. Please set either:\n"
            "  1. SUPABASE_DB_URL=postgresql://postgres:PASSWORD@db.PROJECT.supabase.co:5432/postgres\n"
            "  OR\n"
            "  2. SUPABASE_URL + SUPABASE_PASSWORD"
        )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
