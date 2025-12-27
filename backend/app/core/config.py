# app/core/config.py
import os
from urllib.parse import quote_plus

from dotenv import load_dotenv


def str_to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def merge_unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in items:
        if v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out


class Settings:
    def __init__(self) -> None:
        # Only load .env for local/dev. In App Runner, env vars come from the service config.
        self.ENV = os.getenv("ENV", "dev").strip().lower()  # dev | prod
        if self.ENV != "prod":
            # Load .env only for non-prod so prod can't be accidentally influenced by local files.
            load_dotenv()

        # ----------------------------
        # Database
        # ----------------------------
        self.DB_HOST = os.getenv("DB_HOST", "")
        self.DB_PORT = os.getenv("DB_PORT", "5432")
        self.DB_NAME = os.getenv("DB_NAME", "")
        self.DB_APP_USER = os.getenv("DB_APP_USER", "")
        self.DB_APP_PASSWORD = os.getenv("DB_APP_PASSWORD", "")
        self.DB_MIGRATOR_USER = os.getenv("DB_MIGRATOR_USER", "")
        self.DB_MIGRATOR_PASSWORD = os.getenv("DB_MIGRATOR_PASSWORD", "")
        self.DB_SSLMODE = os.getenv("DB_SSLMODE", "require").strip().lower()

        # ----------------------------
        # Password policy
        # ----------------------------
        self.PASSWORD_MIN_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH", "14"))
        self.PASSWORD_MAX_AGE_DAYS = int(os.getenv("PASSWORD_MAX_AGE_DAYS", "90"))

        # ----------------------------
        # CORS
        # ----------------------------
        dev_defaults = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]

        cors_from_env = parse_csv(os.getenv("CORS_ORIGINS"))
        if self.ENV == "prod":
            # In prod: ONLY allow what you explicitly configure
            self.CORS_ORIGINS = merge_unique(cors_from_env)
        else:
            # In dev: allow env + local defaults
            self.CORS_ORIGINS = merge_unique(cors_from_env + dev_defaults)

        # ----------------------------
        # Auth / JWT
        # ----------------------------
        self.JWT_SECRET = os.getenv("JWT_SECRET", "")
        self.JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
        self.ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))

        self.REFRESH_TOKEN_EXPIRE_HOURS = int(os.getenv("REFRESH_TOKEN_EXPIRE_HOURS", "24"))
        self.REFRESH_COOKIE_NAME = os.getenv("REFRESH_COOKIE_NAME", "refresh_token")
        self.REFRESH_COOKIE_SAMESITE = os.getenv("REFRESH_COOKIE_SAMESITE", "lax")
        self.REFRESH_COOKIE_SECURE = str_to_bool(os.getenv("REFRESH_COOKIE_SECURE"), default=False)
        self.REFRESH_COOKIE_PATH = os.getenv("REFRESH_COOKIE_PATH", "/auth")
        self.REFRESH_COOKIE_DOMAIN = os.getenv("REFRESH_COOKIE_DOMAIN", "") or None

        # ----------------------------
        # Email verification / URLs
        # ----------------------------
        self.EMAIL_VERIFY_TOKEN_EXPIRE_HOURS = int(os.getenv("EMAIL_VERIFY_TOKEN_EXPIRE_HOURS", "24"))

        # Dev defaults are local URLs; prod MUST be explicitly configured (no localhost defaults in prod)
        if self.ENV == "prod":
            self.FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "").strip().rstrip("/")
            self.PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
        else:
            self.FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173").strip().rstrip("/")
            self.PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").strip().rstrip("/")

        # ----------------------------
        # Email delivery
        # ----------------------------
        self.EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "resend").strip().lower()
        self.EMAIL_ENABLED = str_to_bool(os.getenv("EMAIL_ENABLED"), default=False)
        self.GUARD_DUTY_ENABLED = str_to_bool(os.getenv("GUARD_DUTY_ENABLED"), default=False)

        self.FROM_EMAIL = os.getenv("FROM_EMAIL", "")
        self.RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")

        # SMTP (only relevant if EMAIL_PROVIDER=gmail/smtp)
        self.SMTP_HOST = os.getenv("SMTP_HOST", "")
        self.SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
        self.SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
        self.SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
        self.SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "")
        self.SMTP_USE_TLS = str_to_bool(os.getenv("SMTP_USE_TLS", "true"), default=True)
        self.SMTP_USE_SSL = str_to_bool(os.getenv("SMTP_USE_SSL", "false"), default=False)

        # ----------------------------
        # Rate limiting / uploads / AWS
        # ----------------------------
        self.ENABLE_RATE_LIMITING = str_to_bool(os.getenv("ENABLE_RATE_LIMITING", "false"))
        self.DOC_SCAN_SHARED_SECRET = os.getenv("DOC_SCAN_SHARED_SECRET", "")

        self.MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))
        self.MAX_PENDING_UPLOADS_PER_JOB = int(os.getenv("MAX_PENDING_UPLOADS_PER_JOB", "5"))

        self.AWS_REGION = os.getenv("AWS_REGION", "")
        self.S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "")
        self.S3_PREFIX = os.getenv("S3_PREFIX", "")

        # Final: fail fast in prod
        self._validate_prod()

    def _validate_prod(self) -> None:
        if self.ENV != "prod":
            return

        missing: list[str] = []

        # hard requirements for prod
        if not self.JWT_SECRET:
            missing.append("JWT_SECRET")
        if not self.DB_HOST:
            missing.append("DB_HOST")
        if not self.DB_NAME:
            missing.append("DB_NAME")
        if not self.DB_APP_USER:
            missing.append("DB_APP_USER")
        if not self.DB_APP_PASSWORD:
            missing.append("DB_APP_PASSWORD")

        # URLs should be explicitly set in prod
        if not self.FRONTEND_BASE_URL:
            missing.append("FRONTEND_BASE_URL")
        if not self.PUBLIC_BASE_URL:
            missing.append("PUBLIC_BASE_URL")

        if self.DB_SSLMODE != "require":
            raise RuntimeError("DB_SSLMODE must be 'require' in prod")

        # urls/origins should be explicit
        if not self.CORS_ORIGINS:
            missing.append("CORS_ORIGINS")

        cors_joined = ",".join(self.CORS_ORIGINS)
        if "localhost" in cors_joined or "127.0.0.1" in cors_joined:
            raise RuntimeError("CORS_ORIGINS contains localhost/dev origins in prod")

        if self.FRONTEND_BASE_URL and not self.FRONTEND_BASE_URL.startswith("https://"):
            raise RuntimeError("FRONTEND_BASE_URL should be https://... in prod")
        if self.PUBLIC_BASE_URL and not self.PUBLIC_BASE_URL.startswith("https://"):
            raise RuntimeError("PUBLIC_BASE_URL should be https://... in prod")

        if missing:
            raise RuntimeError(f"Missing required prod env vars: {', '.join(missing)}")

    @property
    def is_prod(self) -> bool:
        return self.ENV == "prod"

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


settings = Settings()


def require_jwt_secret() -> None:
    if not settings.JWT_SECRET:
        raise RuntimeError("JWT_SECRET must be set")