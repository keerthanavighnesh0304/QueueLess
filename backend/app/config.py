import os
import urllib.parse
from pathlib import Path
from typing import Any
from pydantic_settings import BaseSettings
from pydantic import Field, model_validator

# Path to the backend root directory (where .env lives)
BACKEND_DIR = Path(__file__).resolve().parent.parent

# Insecure fallbacks and placeholders that must never be permitted in production
INSECURE_DEV_JWT_SECRET = "insecure_dev_secret_please_change_in_env_file_123456789"
EXAMPLE_PLACEHOLDER_JWT_SECRET = "change_this_to_a_secure_random_secret_in_production"


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # MySQL Database Settings
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = Field(default="", repr=False)
    DB_NAME: str = "queueless_db"
    DATABASE_URL: str | None = None
    DB_SSL_CA: str | None = None
    DB_SSL_CHECK_HOSTNAME: bool = True
    DB_SSL_MODE: str | None = None

    # JWT Settings
    JWT_SECRET_KEY: str = Field(default=INSECURE_DEV_JWT_SECRET, repr=False)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Initial Admin Seed Credentials
    ADMIN_EMAIL: str = "admin@queueless.local"
    ADMIN_INITIAL_PASSWORD: str | None = Field(default=None, repr=False)
    ADMIN_FULL_NAME: str = "Platform Administrator"

    # Demo Accounts Seed Password (Development Only)
    DEMO_ACCOUNTS_PASSWORD: str | None = Field(default=None, repr=False)

    # CORS Allowed Origins
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    model_config = {
        "env_file": str(BACKEND_DIR / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def is_production(self) -> bool:
        """Determines if the application is running in production mode."""
        return (self.ENVIRONMENT or "").strip().lower() in {"production", "prod"}

    @model_validator(mode="after")
    def validate_production_jwt_secret(self) -> "Settings":
        """
        Guards against starting in production with missing, empty, or default JWT secrets.
        In production, a dedicated secret must be provided via the environment.
        """
        if self.is_production:
            secret = (self.JWT_SECRET_KEY or "").strip()
            if not secret:
                raise ValueError(
                    "JWT_SECRET_KEY must be set and non-empty in production. "
                    "Configure a strong secret via the JWT_SECRET_KEY environment variable."
                )
            if secret in {INSECURE_DEV_JWT_SECRET, EXAMPLE_PLACEHOLDER_JWT_SECRET}:
                raise ValueError(
                    "Insecure default JWT_SECRET_KEY detected in production. "
                    "Configure a unique, cryptographically strong secret via the JWT_SECRET_KEY environment variable."
                )
        return self

    def get_database_url(self) -> str:
        """
        Returns the SQLAlchemy database connection URL.
        Uses explicit DATABASE_URL if configured; otherwise builds it
        from individual DB_* components.
        Normalizes mysql:// scheme to mysql+pymysql:// to ensure PyMySQL is used,
        and sanitizes driver-incompatible query parameters (such as ssl-mode).
        """
        if self.DATABASE_URL:
            url = self.DATABASE_URL.strip()
            if url.startswith("mysql://"):
                url = "mysql+pymysql://" + url[len("mysql://"):]

            parsed = urllib.parse.urlsplit(url)
            q_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
            clean_q = [
                (k, v) for k, v in q_pairs
                if k.lower() not in ("ssl-mode", "ssl_mode")
            ]
            new_query = urllib.parse.urlencode(clean_q)
            return urllib.parse.urlunsplit(
                (parsed.scheme, parsed.netloc, parsed.path, new_query, parsed.fragment)
            )

        user = urllib.parse.quote_plus(self.DB_USER)
        password = urllib.parse.quote_plus(self.DB_PASSWORD)
        return (
            f"mysql+pymysql://{user}:{password}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )

    def get_database_connect_args(self) -> dict[str, Any]:
        """
        Constructs DBAPI connection arguments for PyMySQL, configuring TLS/SSL
        when a CA certificate or SSL mode is specified via configuration or DATABASE_URL.
        Returns an empty dictionary in local development when SSL is not configured.
        """
        connect_args: dict[str, Any] = {}
        ssl_dict: dict[str, Any] = {}

        if self.DB_SSL_CA:
            ca_path = self.DB_SSL_CA.strip()
            p = Path(ca_path)
            if not p.is_absolute() and (BACKEND_DIR / p).exists():
                ca_path = str(BACKEND_DIR / p)
            ssl_dict["ca"] = ca_path
            if not self.DB_SSL_CHECK_HOSTNAME:
                ssl_dict["check_hostname"] = False
            else:
                ssl_dict["check_hostname"] = True

        elif self.DB_SSL_MODE and self.DB_SSL_MODE.strip().upper() in {
            "REQUIRED", "VERIFY_CA", "VERIFY_IDENTITY", "1", "TRUE"
        }:
            ssl_dict["check_hostname"] = self.DB_SSL_CHECK_HOSTNAME

        elif self.DATABASE_URL:
            parsed = urllib.parse.urlsplit(self.DATABASE_URL)
            q_dict = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
            for k, v in q_dict.items():
                if k.lower() in ("ssl-mode", "ssl_mode"):
                    if v.strip().upper() in {"REQUIRED", "VERIFY_CA", "VERIFY_IDENTITY", "1", "TRUE"}:
                        ssl_dict["check_hostname"] = self.DB_SSL_CHECK_HOSTNAME
                    break

        if ssl_dict:
            connect_args["ssl"] = ssl_dict

        return connect_args

    def get_cors_origins(self) -> list[str]:
        """Parses comma-separated allowed origins into a Python list."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]


settings = Settings()
