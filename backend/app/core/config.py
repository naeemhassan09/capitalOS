"""Application configuration with fail-fast validation.

Settings are loaded from environment variables (and an optional ``.env`` file in
development). In production the application refuses to boot when required secrets
are missing or left at their insecure defaults.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Sentinel used in .env.example — must never be used in production.
INSECURE_PLACEHOLDER = "change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App ---
    app_env: str = Field(default="development")
    app_name: str = Field(default="CapitalOS")
    app_url: str = Field(default="http://localhost:5173")
    domain: str = Field(default="localhost")
    log_level: str = Field(default="INFO")

    # --- Secrets ---
    secret_key: str = Field(default=INSECURE_PLACEHOLDER)
    # Fernet key: 32 url-safe base64-encoded bytes (44 chars ending with '=')
    encryption_key: str = Field(default="")

    # --- Database ---
    database_url: str = Field(default="")
    postgres_db: str = Field(default="capitalos")
    postgres_user: str = Field(default="capitalos")
    postgres_password: str = Field(default=INSECURE_PLACEHOLDER)
    postgres_host: str = Field(default="postgres")
    postgres_port: int = Field(default=5432)

    # --- Redis (reserved for future background jobs; unused in core build) ---
    redis_url: str = Field(default="")

    # --- Sessions / auth ---
    session_cookie_name: str = Field(default="capitalos_session")
    session_max_age: int = Field(default=60 * 60 * 24 * 14)  # 14 days
    session_cookie_secure: bool = Field(default=False)  # True behind HTTPS
    totp_issuer: str = Field(default="CapitalOS")
    login_max_attempts: int = Field(default=10)
    login_window_seconds: int = Field(default=300)

    # --- CORS / hosts ---
    cors_allowed_origins: str = Field(default="http://localhost:5173")
    trusted_hosts: str = Field(default="*")

    # --- Uploads / imports ---
    max_upload_size_mb: int = Field(default=10)
    file_encryption_enabled: bool = Field(default=True)
    upload_dir: str = Field(default="/app/var/uploads")

    # --- Backups (documented; not wired in core build) ---
    backup_retention_days: int = Field(default=30)
    backup_s3_endpoint: str = Field(default="")
    backup_s3_bucket: str = Field(default="")
    backup_encryption_passphrase: str = Field(default="")

    # --- FX ---
    # Daily background sync of exchange rates from a free external source.
    fx_auto_sync: bool = Field(default=True)

    # --- Investment prices ---
    # Daily background sync of holding prices (PSX / MUFAP / stooq-Yahoo).
    price_auto_sync: bool = Field(default=True)

    # --- Open Banking (feature-flagged off) ---
    open_banking_enabled: bool = Field(default=False)
    gocardless_bank_data_secret_id: str = Field(default="")
    gocardless_bank_data_secret_key: str = Field(default="")

    # --- Enable Banking (activates when an app id + private key are present) ---
    enable_banking_app_id: str = Field(default="")
    enable_banking_private_key_path: str = Field(default="/app/secrets/enablebanking.pem")
    enable_banking_auto_sync: bool = Field(default=True)

    # --- Observability ---
    sentry_dsn: str = Field(default="")

    # ---------------------------------------------------------------- helpers
    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}

    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def trusted_host_list(self) -> list[str]:
        return [h.strip() for h in self.trusted_hosts.split(",") if h.strip()] or ["*"]

    @property
    def enable_banking_configured(self) -> bool:
        """True when an app id is set and the private key file actually exists."""
        return bool(self.enable_banking_app_id) and Path(
            self.enable_banking_private_key_path
        ).is_file()

    # ------------------------------------------------------------- validation
    @field_validator("encryption_key")
    @classmethod
    def _validate_fernet_key(cls, v: str) -> str:
        if not v:
            return v
        # Validate the key is a usable Fernet key without importing at module load.
        from cryptography.fernet import Fernet

        try:
            Fernet(v.encode())
        except Exception as exc:  # noqa: BLE001
            raise ValueError(
                "ENCRYPTION_KEY must be a valid Fernet key "
                "(generate with: python -c 'from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())')"
            ) from exc
        return v

    @model_validator(mode="after")
    def _fail_fast_in_production(self) -> Settings:
        if not self.is_production:
            return self
        problems: list[str] = []
        if self.secret_key in ("", INSECURE_PLACEHOLDER):
            problems.append("SECRET_KEY must be set to a strong random value.")
        if not self.encryption_key:
            problems.append("ENCRYPTION_KEY must be set (valid Fernet key).")
        if self.postgres_password in ("", INSECURE_PLACEHOLDER) and not self.database_url:
            problems.append("POSTGRES_PASSWORD must be set to a strong value.")
        if not self.session_cookie_secure:
            problems.append("SESSION_COOKIE_SECURE must be true in production (HTTPS).")
        if problems:
            raise RuntimeError(
                "Refusing to start in production with insecure configuration:\n  - "
                + "\n  - ".join(problems)
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
