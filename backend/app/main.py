import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from slowapi.errors import RateLimitExceeded

from app.core.config import settings, require_jwt_secret
from app.core.rate_limit import limiter 
from app.routes.auth import router as auth_router
from app.routes.job_applications import router as jobs_router
from app.routes.notes import router as notes_router
from app.routes.documents import router as documents_router
from app.routes.users import router as users_router
from app.routes.saved_views import router as saved_views_router
from app.routes.activity import router as activity_router
from app.routes.interviews import router as interviews_router
from app.routes.internal_documents import router as internal_documents_router

logger = logging.getLogger(__name__)

require_jwt_secret()

app = FastAPI(title="Job Application Tracker")
logger.info(
    "Startup config: EMAIL_ENABLED=%s provider=%s GUARD_DUTY_ENABLED=%s",
    settings.EMAIL_ENABLED,
    (settings.EMAIL_PROVIDER or "resend"),
    settings.GUARD_DUTY_ENABLED,
)

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
def http_exception_handler(request: Request, exc: HTTPException):  # noqa: ARG001
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
    return JSONResponse(status_code=exc.status_code, content=payload)


@app.exception_handler(RequestValidationError)
def validation_exception_handler(request: Request, exc: RequestValidationError):  # noqa: ARG001
    return JSONResponse(
        status_code=422,
        content={
            "error": "VALIDATION_ERROR",
            "message": "Invalid request payload",
            "details": {"errors": exc.errors()},
        },
    )


if settings.ENABLE_RATE_LIMITING:
    app.state.limiter = limiter
    # Provide our standard error shape for rate limits, instead of slowapi's default.
    app.add_exception_handler(
        RateLimitExceeded,
        lambda request, exc: JSONResponse(  # noqa: ARG005
            status_code=429,
            content={"error": "RATE_LIMITED", "message": "Too many requests"},
        ),
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(notes_router)
app.include_router(documents_router)
app.include_router(users_router)
app.include_router(saved_views_router)
app.include_router(activity_router)
app.include_router(interviews_router)
app.include_router(internal_documents_router)

@app.get("/health")
def health_check():
    return {"status": "ok"}