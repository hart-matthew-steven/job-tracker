import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.middleware.identity import register_identity_middleware
from app.routes.auth_cognito import router as auth_cognito_router
from app.routes.job_applications import router as jobs_router
from app.routes.notes import router as notes_router
from app.routes.documents import router as documents_router
from app.routes.users import router as users_router
from app.routes.saved_views import router as saved_views_router
from app.routes.activity import router as activity_router
from app.routes.interviews import router as interviews_router
from app.routes.internal_documents import router as internal_documents_router
from app.routes.stripe_billing import router as stripe_billing_router
from app.routes.billing import router as billing_router
from app.routes.ai_demo import router as ai_demo_router
from app.routes.ai_chat import router as ai_chat_router
from app.routes.ai_conversations import router as ai_conversations_router
from app.routes.admin_rate_limits import router as admin_rate_limits_router


# -------------------------------------------------------------------
# Logging (must be configured BEFORE anything else)
# -------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# App initialization
# -------------------------------------------------------------------
app = FastAPI(title="Job Application Tracker")


# -------------------------------------------------------------------
# Startup
# -------------------------------------------------------------------
@app.on_event("startup")
async def startup_event() -> None:
    try:
        logger.info("Starting Job Tracker API (ENV=%s)", settings.ENV)

        logger.info("Startup config: GUARD_DUTY_ENABLED=%s", settings.GUARD_DUTY_ENABLED)
    except Exception:
        logger.exception("Startup failed")
        raise


# -------------------------------------------------------------------
# Error handling
# -------------------------------------------------------------------
_ERROR_CODE_BY_STATUS: dict[int, str] = {
    400: "VALIDATION_ERROR",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
}


def _error_code(status_code: int) -> str:
    return _ERROR_CODE_BY_STATUS.get(int(status_code), "HTTP_ERROR")


@app.exception_handler(HTTPException)
def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    message: str
    details: dict | None = None

    if isinstance(detail, str):
        message = detail
    elif isinstance(detail, dict):
        # Allow raising HTTPException(detail={"message": "...", "details": {...}}) if needed later.
        msg = detail.get("message")
        message = msg if isinstance(msg, str) and msg else "Request failed"
        det = detail.get("details")
        details = det if isinstance(det, dict) else None
    else:
        message = str(detail) if detail is not None else "Request failed"

    payload: dict = {"error": _error_code(exc.status_code), "message": message}
    if details:
        payload["details"] = details
    headers = getattr(exc, "headers", None)
    return JSONResponse(status_code=exc.status_code, content=payload, headers=headers)


@app.exception_handler(RequestValidationError)
def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": "VALIDATION_ERROR",
            "message": "Invalid request payload",
            "details": {"errors": exc.errors()},
        },
    )


# -------------------------------------------------------------------
# Middleware
# -------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_identity_middleware(app)

# -------------------------------------------------------------------
# Routers
# -------------------------------------------------------------------
app.include_router(auth_cognito_router)
app.include_router(jobs_router)
app.include_router(notes_router)
app.include_router(documents_router)
app.include_router(users_router)
app.include_router(saved_views_router)
app.include_router(activity_router)
app.include_router(interviews_router)
app.include_router(internal_documents_router)
app.include_router(stripe_billing_router)
app.include_router(billing_router)
app.include_router(ai_demo_router)
app.include_router(ai_chat_router)
app.include_router(ai_conversations_router)
app.include_router(admin_rate_limits_router)


# -------------------------------------------------------------------
# Health check (used by App Runner)
# -------------------------------------------------------------------
@app.get("/health")
def health_check():
    logger.info("Health check OK")
    return {"status": "ok"}