"""
Automated unit tests for production configuration hardening and JWT secret validation.
Ensures the backend fails fast if insecure, empty, or default secrets are used in production,
while maintaining seamless local development ergonomics.
"""

import pytest
from pydantic import ValidationError

from app.config import (
    Settings,
    INSECURE_DEV_JWT_SECRET,
    EXAMPLE_PLACEHOLDER_JWT_SECRET,
)


def test_development_allows_default_jwt_secret():
    """Development environment must permit default fallback credentials."""
    s = Settings(_env_file=None, ENVIRONMENT="development")
    assert s.is_production is False
    assert s.JWT_SECRET_KEY == INSECURE_DEV_JWT_SECRET


def test_production_rejects_omitted_jwt_secret():
    """Production environment must refuse to boot if JWT_SECRET_KEY is not overridden."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None, ENVIRONMENT="production")

    errors = str(exc_info.value)
    assert "Insecure default JWT_SECRET_KEY detected in production" in errors


def test_production_rejects_empty_jwt_secret():
    """Production environment must reject empty or whitespace-only secret keys."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None, ENVIRONMENT="production", JWT_SECRET_KEY="   ")

    errors = str(exc_info.value)
    assert "JWT_SECRET_KEY must be set and non-empty in production" in errors


def test_production_rejects_example_placeholder_secret():
    """Production environment must reject copying the example placeholder directly."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None,
            ENVIRONMENT="production",
            JWT_SECRET_KEY=EXAMPLE_PLACEHOLDER_JWT_SECRET,
        )

    errors = str(exc_info.value)
    assert "Insecure default JWT_SECRET_KEY detected in production" in errors


def test_production_accepts_valid_strong_secret():
    """Production environment must successfully initialize when a valid secret is provided."""
    dummy_prod_secret = "7d89b1426466fbfd620573e04375b42d87e07a21394cbbda58763567824b20a3"
    s = Settings(
        _env_file=None,
        ENVIRONMENT="production",
        JWT_SECRET_KEY=dummy_prod_secret,
    )
    assert s.is_production is True
    assert s.JWT_SECRET_KEY == dummy_prod_secret


def test_settings_repr_does_not_leak_secrets():
    """String and repr representations of Settings must not print sensitive credentials."""
    dummy_secret = "sensitive_secret_value_must_not_appear_in_logs"
    s = Settings(
        _env_file=None,
        ENVIRONMENT="development",
        JWT_SECRET_KEY=dummy_secret,
        DB_PASSWORD="sensitive_db_password",
    )
    repr_str = repr(s)
    assert dummy_secret not in repr_str
    assert "sensitive_db_password" not in repr_str


def test_database_config_local_development_defaults():
    """Local development must use standard MySQL URL with empty connect_args (no SSL overhead)."""
    s = Settings(_env_file=None, ENVIRONMENT="development")
    db_url = s.get_database_url()
    connect_args = s.get_database_connect_args()

    assert db_url.startswith("mysql+pymysql://")
    assert "charset=utf8mb4" in db_url
    assert connect_args == {}


def test_database_config_discrete_ssl_ca():
    """Setting DB_SSL_CA must configure PyMySQL connect_args with CA path and hostname verification."""
    s = Settings(
        _env_file=None,
        DB_HOST="mysql-service.aivencloud.com",
        DB_PORT=12345,
        DB_USER="avnadmin",
        DB_NAME="defaultdb",
        DB_SSL_CA="/etc/ssl/certs/aiven-ca.pem",
        DB_SSL_CHECK_HOSTNAME=True,
    )
    connect_args = s.get_database_connect_args()
    assert "ssl" in connect_args
    assert connect_args["ssl"]["ca"] == "/etc/ssl/certs/aiven-ca.pem"
    assert connect_args["ssl"]["check_hostname"] is True


def test_database_config_discrete_ssl_ca_disable_check_hostname():
    """Setting DB_SSL_CHECK_HOSTNAME=False must disable hostname verification in SSL parameters."""
    s = Settings(
        _env_file=None,
        DB_SSL_CA="/etc/ssl/certs/aiven-ca.pem",
        DB_SSL_CHECK_HOSTNAME=False,
    )
    connect_args = s.get_database_connect_args()
    assert connect_args["ssl"]["check_hostname"] is False


def test_database_config_ssl_mode_required():
    """Setting DB_SSL_MODE=REQUIRED without custom CA must enable TLS using system certificate store."""
    s = Settings(_env_file=None, DB_SSL_MODE="REQUIRED")
    connect_args = s.get_database_connect_args()
    assert "ssl" in connect_args
    assert "ca" not in connect_args["ssl"]
    assert connect_args["ssl"]["check_hostname"] is True


def test_database_config_normalizes_aiven_mysql_url_scheme():
    """Aiven mysql:// scheme must be normalized to mysql+pymysql:// for PyMySQL driver compatibility."""
    aiven_uri = "mysql://avnadmin:securepassword@mysql-project.aivencloud.com:17890/defaultdb"
    s = Settings(_env_file=None, DATABASE_URL=aiven_uri)
    normalized_url = s.get_database_url()

    assert normalized_url.startswith("mysql+pymysql://")
    assert "mysql-project.aivencloud.com:17890/defaultdb" in normalized_url


def test_database_config_strips_ssl_mode_from_url_and_sets_connect_args():
    """Driver-incompatible ssl-mode parameters in DATABASE_URL must be sanitized and mapped to connect_args."""
    aiven_uri = "mysql://avnadmin:pass@mysql-project.aivencloud.com:17890/defaultdb?ssl-mode=REQUIRED&charset=utf8mb4"
    s = Settings(_env_file=None, DATABASE_URL=aiven_uri)
    sanitized_url = s.get_database_url()
    connect_args = s.get_database_connect_args()

    assert "ssl-mode" not in sanitized_url
    assert "ssl_mode" not in sanitized_url
    assert sanitized_url.startswith("mysql+pymysql://")
    assert "ssl" in connect_args
    assert connect_args["ssl"]["check_hostname"] is True
