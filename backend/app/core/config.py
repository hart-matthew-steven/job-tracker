# app/core/config.py
import os
from dataclasses import dataclass
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


@dataclass(frozen=True)
class StripeCreditPack:
    key: str
    price_id: str
    credits: int


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
        # Authentication mode is now fixed to Cognito.
        self.COGNITO_REGION = os.getenv("COGNITO_REGION", "").strip()
        self.COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID", "").strip()
        self.COGNITO_APP_CLIENT_ID = os.getenv("COGNITO_APP_CLIENT_ID", "").strip()
        self.COGNITO_JWKS_CACHE_SECONDS = int(os.getenv("COGNITO_JWKS_CACHE_SECONDS", "900"))

        # ----------------------------
        # Email verification / Resend
        # ----------------------------
        self.EMAIL_VERIFICATION_ENABLED = str_to_bool(os.getenv("EMAIL_VERIFICATION_ENABLED", "false"))
        self.EMAIL_VERIFICATION_CODE_TTL_SECONDS = int(os.getenv("EMAIL_VERIFICATION_CODE_TTL_SECONDS", "900"))
        self.EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS = int(
            os.getenv("EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS", "60")
        )
        self.EMAIL_VERIFICATION_MAX_ATTEMPTS = int(os.getenv("EMAIL_VERIFICATION_MAX_ATTEMPTS", "10"))
        self.RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
        self.RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "").strip()
        frontend_base = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173").strip()
        self.FRONTEND_BASE_URL = frontend_base.rstrip("/") or "http://localhost:5173"

        # ----------------------------
        # Bot protection
        # ----------------------------
        self.TURNSTILE_SITE_KEY = os.getenv("TURNSTILE_SITE_KEY", "").strip()
        self.TURNSTILE_SECRET_KEY = os.getenv("TURNSTILE_SECRET_KEY", "").strip()

        # ----------------------------
        # GuardDuty callbacks
        # ----------------------------
        self.GUARD_DUTY_ENABLED = str_to_bool(os.getenv("GUARD_DUTY_ENABLED"), default=False)

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

        # ----------------------------
        # Stripe billing
        # ----------------------------
        self.STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
        self.STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
        self.STRIPE_DEFAULT_CURRENCY = (os.getenv("STRIPE_DEFAULT_CURRENCY", "usd").strip().lower() or "usd")
        stripe_price_map_raw = os.getenv("STRIPE_PRICE_MAP", "")
        self.STRIPE_PRICE_MAP = self._parse_stripe_price_map(stripe_price_map_raw)
        self.ENABLE_BILLING_DEBUG_ENDPOINT = str_to_bool(os.getenv("ENABLE_BILLING_DEBUG_ENDPOINT", "false"))

        # Final: fail fast in prod
        self._validate_prod()

    def _validate_prod(self) -> None:
        if self.ENV != "prod":
            return

        missing: list[str] = []

        # hard requirements for prod
        if not self.DB_HOST:
            missing.append("DB_HOST")
        if not self.DB_NAME:
            missing.append("DB_NAME")
        if not self.DB_APP_USER:
            missing.append("DB_APP_USER")
        if not self.DB_APP_PASSWORD:
            missing.append("DB_APP_PASSWORD")
        if not self.STRIPE_SECRET_KEY:
            missing.append("STRIPE_SECRET_KEY")
        if not self.STRIPE_WEBHOOK_SECRET:
            missing.append("STRIPE_WEBHOOK_SECRET")
        if not self.STRIPE_PRICE_MAP:
            missing.append("STRIPE_PRICE_MAP")
        if not self.TURNSTILE_SITE_KEY:
            missing.append("TURNSTILE_SITE_KEY")
        if not self.TURNSTILE_SECRET_KEY:
            missing.append("TURNSTILE_SECRET_KEY")
        if self.EMAIL_VERIFICATION_ENABLED:
            if not self.RESEND_API_KEY:
                missing.append("RESEND_API_KEY")
            if not self.RESEND_FROM_EMAIL:
                missing.append("RESEND_FROM_EMAIL")
            if not self.FRONTEND_BASE_URL or "localhost" in self.FRONTEND_BASE_URL:
                raise RuntimeError("FRONTEND_BASE_URL must be set to the production domain when email verification is enabled.")

        # URLs should be explicitly set in prod
        if self.DB_SSLMODE != "require":
            raise RuntimeError("DB_SSLMODE must be 'require' in prod")

        # urls/origins should be explicit
        if not self.CORS_ORIGINS:
            missing.append("CORS_ORIGINS")

        cors_joined = ",".join(self.CORS_ORIGINS)
        if "localhost" in cors_joined or "127.0.0.1" in cors_joined:
            raise RuntimeError("CORS_ORIGINS contains localhost/dev origins in prod")

        if missing:
            raise RuntimeError(f"Missing required prod env vars: {', '.join(missing)}")

    @property
    def is_prod(self) -> bool:
        return self.ENV == "prod"

    @property
    def cognito_issuer(self) -> str:
        """
        Build the Cognito issuer URL used for JWT validation.
        Returns empty string if region or pool ID not configured.
        """
        if not self.COGNITO_REGION or not self.COGNITO_USER_POOL_ID:
            return ""
        return f"https://cognito-idp.{self.COGNITO_REGION}.amazonaws.com/{self.COGNITO_USER_POOL_ID}"

    @property
    def cognito_jwks_url(self) -> str:
        """
        Build the JWKS URL for fetching Cognito signing keys.
        Returns empty string if issuer is not configured.
        """
        issuer = self.cognito_issuer
        if not issuer:
            return ""
        return f"{issuer}/.well-known/jwks.json"

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

    def _parse_stripe_price_map(self, raw: str) -> dict[str, StripeCreditPack]:
        """
        Parse STRIPE_PRICE_MAP entries formatted as
        pack_key:price_id:credits,pack_key2:price_id2:credits2
        """
        packs: dict[str, StripeCreditPack] = {}
        if not raw:
            return packs
        for entry in raw.split(","):
            token = entry.strip()
            if not token:
                continue
            parts = [p.strip() for p in token.split(":")]
            if len(parts) != 3:
                continue
            pack_key, price_id, credits_raw = parts
            if not pack_key or not price_id:
                continue
            try:
                credits = int(credits_raw)
            except ValueError:
                continue
            if credits <= 0:
                continue
            packs[pack_key] = StripeCreditPack(key=pack_key, price_id=price_id, credits=credits)
        return packs

    def get_stripe_pack(self, pack_key: str) -> StripeCreditPack | None:
        """Lookup a configured Stripe credit pack."""
        return self.STRIPE_PRICE_MAP.get((pack_key or "").strip())


settings = Settings()