# app/core/config.py
import os
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()

def str_to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

def parse_csv(value: str | None, default: list[str]) -> list[str]:
    if not value:
        return default
    return [v.strip() for v in value.split(",") if v.strip()]

def merge_unique(items: list[str]) -> list[str]:
    seen = set()
    out: list[str] = []
    for v in items:
        if v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out

class Settings:
    # Environment
    ENV = os.getenv("ENV", "dev")  # dev | prod

    # Database
    DB_HOST = os.getenv("DB_HOST", "")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "")
    DB_APP_USER = os.getenv("DB_APP_USER", "")
    DB_APP_PASSWORD = os.getenv("DB_APP_PASSWORD", "")
    DB_MIGRATOR_USER = os.getenv("DB_MIGRATOR_USER", "")
    DB_MIGRATOR_PASSWORD = os.getenv("DB_MIGRATOR_PASSWORD", "")
    DB_SSLMODE = os.getenv("DB_SSLMODE", "require")

    # Password policy
    PASSWORD_MIN_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH", "14"))
    PASSWORD_MAX_AGE_DAYS = int(os.getenv("PASSWORD_MAX_AGE_DAYS", "90"))

    # CORS (CSV)
    # Keep your matts-macbook.local default AND localhost as a sane dev default:
    _CORS_DEFAULTS = ["http://matts-macbook.local:5173", "http://localhost:5173", "http://127.0.0.1:5173"]
    CORS_ORIGINS = merge_unique(
        parse_csv(os.getenv("CORS_ORIGINS"), default=_CORS_DEFAULTS) + _CORS_DEFAULTS
    )

    # Auth / JWT
    JWT_SECRET = os.getenv("JWT_SECRET", "")
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
    REFRESH_TOKEN_EXPIRE_HOURS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_HOURS", "24"))
    REFRESH_COOKIE_NAME: str = os.getenv("REFRESH_COOKIE_NAME", "refresh_token")
    REFRESH_COOKIE_SAMESITE: str = os.getenv("REFRESH_COOKIE_SAMESITE", "lax")
    REFRESH_COOKIE_SECURE: bool = str_to_bool(os.getenv("REFRESH_COOKIE_SECURE"), default=False)
    REFRESH_COOKIE_PATH = os.getenv("REFRESH_COOKIE_PATH", "/auth")
    REFRESH_COOKIE_DOMAIN = os.getenv("REFRESH_COOKIE_DOMAIN", "") or None

    # Email verification
    EMAIL_VERIFY_TOKEN_EXPIRE_HOURS = int(os.getenv("EMAIL_VERIFY_TOKEN_EXPIRE_HOURS", "24"))

    # Frontend base URL used to build email verification links
    # (Keep dev pointing at Vite; prod should be your real frontend domain)
    FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://matts-macbook.local:5173").rstrip("/")

    # SMTP (email delivery)
    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "")
    SMTP_USE_TLS: bool = str_to_bool(os.getenv("SMTP_USE_TLS", "true"), default=True)
    SMTP_USE_SSL: bool = str_to_bool(os.getenv("SMTP_USE_SSL", "false"), default=False)

    # Email provider
    # Supported providers:
    # - "resend" (default)
    # - "ses"
    # - "gmail"
    # Legacy alias:
    # - "smtp" -> treated as "gmail" (handled in app.services.email)
    EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "resend").strip().lower()

    # Public backend base URL (ngrok later) - used for server-side links if needed
    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")

    # Rate limiting (you already have slowapi + _maybe_limit)
    ENABLE_RATE_LIMITING = str_to_bool(os.getenv("ENABLE_RATE_LIMITING", "false"))

    # Document scan shared secret (Lambda → backend webhook auth)
    DOC_SCAN_SHARED_SECRET = os.getenv("DOC_SCAN_SHARED_SECRET", "")

    # Upload guardrails
    MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))
    MAX_PENDING_UPLOADS_PER_JOB = int(os.getenv("MAX_PENDING_UPLOADS_PER_JOB", "5"))

    # AWS
    AWS_REGION = os.getenv("AWS_REGION", "")
    S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "")
    S3_PREFIX = os.getenv("S3_PREFIX", "")

    # Email (provider-specific)
    # Used by: ses, resend
    FROM_EMAIL = os.getenv("FROM_EMAIL", "")
    # Used by: resend
    RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
    EMAIL_ENABLED = str_to_bool(os.getenv("EMAIL_ENABLED"), default=False)
    GUARD_DUTY_ENABLED = str_to_bool(os.getenv("GUARD_DUTY_ENABLED"), default=False)

    def _build_database_url(self, user: str, password: str) -> str:
        encoded_password = quote_plus(password)
        return (
            f"postgresql+psycopg2://{user}:{encoded_password}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            f"?sslmode={self.DB_SSLMODE}"
        )

    @property
    def database_url(self) -> str:
        return self._build_database_url(self.DB_APP_USER, self.DB_APP_PASSWORD)

    @property
    def migrations_database_url(self) -> str:
        return self._build_database_url(self.DB_MIGRATOR_USER, self.DB_MIGRATOR_PASSWORD)

    @property
    def is_prod(self) -> bool:
        return self.ENV.strip().lower() == "prod"

settings = Settings()

def require_jwt_secret():
    if not settings.JWT_SECRET:
        raise RuntimeError("JWT_SECRET must be set")