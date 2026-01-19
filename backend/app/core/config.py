# app/core/config.py
import base64
import json
import os
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import quote_plus

from dotenv import load_dotenv  # type: ignore[import]


def _hydrate_from_mapping(values: Mapping[str, Any]) -> None:
    """
    Add key/value pairs to os.environ if the key is not already set.
    Values are coerced to strings because environ only stores text.
    """
    for key, value in values.items():
        if key in os.environ:
            continue
        if value is None:
            continue
        if isinstance(value, bool):
            os.environ[key] = "true" if value else "false"
        else:
            os.environ[key] = str(value)


def _parse_bundle(raw: str, *, source: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{source} must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"{source} must be a JSON object of key/value pairs")
    return parsed


def _hydrate_json_bundle(var_name: str) -> None:
    blob = os.getenv(var_name)
    if not blob:
        return
    data = _parse_bundle(blob, source=var_name)
    _hydrate_from_mapping(data)


def _hydrate_secret_bundle(var_name: str) -> None:
    arn = os.getenv(var_name)
    if not arn:
        return
    import boto3  # type: ignore[import]
    from botocore.exceptions import BotoCoreError, ClientError  # type: ignore[import]

    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or None
    client = boto3.client("secretsmanager", region_name=region)
    try:
        resp = client.get_secret_value(SecretId=arn)
    except (BotoCoreError, ClientError) as exc:
        raise RuntimeError(f"Failed to load secret bundle from {var_name}: {exc}") from exc

    raw = resp.get("SecretString")
    if raw is None:
        binary = resp.get("SecretBinary")
        if binary is None:
            raise RuntimeError(f"Secret {arn} did not contain SecretString or SecretBinary")
        if isinstance(binary, str):
            binary = binary.encode("utf-8")
        raw = base64.b64decode(binary).decode("utf-8")

    data = _parse_bundle(raw, source=var_name)
    _hydrate_from_mapping(data)


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
        # Load .env first (local dev convenience)
        load_dotenv()

        # Allow bundling many settings into a single secret.
        _hydrate_secret_bundle("SETTINGS_BUNDLE_SECRET_ARN")

        # Now resolve ENV after potential overrides.
        self.ENV = os.getenv("ENV", "dev").strip().lower()  # dev | prod

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
        legacy_rate_toggle = os.getenv("ENABLE_RATE_LIMITING", "false")
        self.DDB_RATE_LIMIT_TABLE = os.getenv("DDB_RATE_LIMIT_TABLE", "jobapptracker-rate-limits").strip()
        self.RATE_LIMIT_ENABLED = str_to_bool(os.getenv("RATE_LIMIT_ENABLED", legacy_rate_toggle))
        self.RATE_LIMIT_DEFAULT_WINDOW_SECONDS = max(1, int(os.getenv("RATE_LIMIT_DEFAULT_WINDOW_SECONDS", "60")))
        self.RATE_LIMIT_DEFAULT_MAX_REQUESTS = max(1, int(os.getenv("RATE_LIMIT_DEFAULT_MAX_REQUESTS", "60")))
        self.AI_RATE_LIMIT_WINDOW_SECONDS = max(1, int(os.getenv("AI_RATE_LIMIT_WINDOW_SECONDS", "60")))
        self.AI_RATE_LIMIT_MAX_REQUESTS = max(1, int(os.getenv("AI_RATE_LIMIT_MAX_REQUESTS", "10")))
        self.DOC_SCAN_SHARED_SECRET = os.getenv("DOC_SCAN_SHARED_SECRET", "")

        self.MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))
        self.MAX_PENDING_UPLOADS_PER_JOB = int(os.getenv("MAX_PENDING_UPLOADS_PER_JOB", "5"))

        self.AWS_REGION = os.getenv("AWS_REGION", "")
        self.S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "")
        self.S3_PREFIX = os.getenv("S3_PREFIX", "")
        self.AI_ARTIFACTS_BUCKET = os.getenv("AI_ARTIFACTS_BUCKET", "").strip()
        self.AI_ARTIFACTS_S3_PREFIX = os.getenv("AI_ARTIFACTS_S3_PREFIX", "users/").strip() or "users/"
        self.AI_ARTIFACTS_SQS_QUEUE_URL = os.getenv("AI_ARTIFACTS_SQS_QUEUE_URL", "").strip()
        self.MAX_ARTIFACT_VERSIONS = max(1, int(os.getenv("MAX_ARTIFACT_VERSIONS", "5")))

        # ----------------------------
        # Stripe billing
        # ----------------------------
        self.STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
        self.STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
        self.STRIPE_DEFAULT_CURRENCY = (os.getenv("STRIPE_DEFAULT_CURRENCY", "usd").strip().lower() or "usd")
        stripe_price_map_raw = os.getenv("STRIPE_PRICE_MAP", "")
        self.STRIPE_PRICE_MAP = self._parse_stripe_price_map(stripe_price_map_raw)
        self.ENABLE_BILLING_DEBUG_ENDPOINT = str_to_bool(os.getenv("ENABLE_BILLING_DEBUG_ENDPOINT", "false"))

        # ----------------------------
        # OpenAI / AI usage
        # ----------------------------
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
        self.OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip() or "gpt-4.1-mini"
        self.AI_CREDITS_RESERVE_BUFFER_PCT = max(0, int(os.getenv("AI_CREDITS_RESERVE_BUFFER_PCT", "25")))
        self.AI_COMPLETION_TOKENS_MAX = max(1, int(os.getenv("AI_COMPLETION_TOKENS_MAX", "3000")))
        self.AI_MAX_INPUT_CHARS = max(1, int(os.getenv("AI_MAX_INPUT_CHARS", "4000")))
        self.AI_MAX_CONTEXT_MESSAGES = max(1, int(os.getenv("AI_MAX_CONTEXT_MESSAGES", "20")))
        self.AI_REQUESTS_PER_MINUTE = max(1, int(os.getenv("AI_REQUESTS_PER_MINUTE", "5")))
        self.AI_MAX_CONCURRENT_REQUESTS = max(1, int(os.getenv("AI_MAX_CONCURRENT_REQUESTS", "2")))
        self.AI_OPENAI_MAX_RETRIES = max(1, int(os.getenv("AI_OPENAI_MAX_RETRIES", "3")))
        self.AI_CONTEXT_TOKEN_BUDGET = max(1, int(os.getenv("AI_CONTEXT_TOKEN_BUDGET", "12000")))
        self.AI_SUMMARY_MESSAGE_THRESHOLD = max(0, int(os.getenv("AI_SUMMARY_MESSAGE_THRESHOLD", "24")))
        self.AI_SUMMARY_TOKEN_THRESHOLD = max(0, int(os.getenv("AI_SUMMARY_TOKEN_THRESHOLD", "6000")))
        self.AI_SUMMARY_MAX_TOKENS = max(1, int(os.getenv("AI_SUMMARY_MAX_TOKENS", "300")))
        self.AI_SUMMARY_CHUNK_SIZE = max(1, int(os.getenv("AI_SUMMARY_CHUNK_SIZE", "12")))
        summary_model = os.getenv("AI_SUMMARY_MODEL", "").strip()
        self.AI_SUMMARY_MODEL = summary_model or None

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
        if not self.OPENAI_API_KEY:
            missing.append("OPENAI_API_KEY")
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

        if not self.AI_ARTIFACTS_BUCKET:
            missing.append("AI_ARTIFACTS_BUCKET")
        if not self.AI_ARTIFACTS_SQS_QUEUE_URL:
            missing.append("AI_ARTIFACTS_SQS_QUEUE_URL")

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