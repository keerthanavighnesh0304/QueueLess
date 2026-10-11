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
