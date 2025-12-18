from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings, require_jwt_secret
from app.core.rate_limit import limiter 
from app.routes.auth import router as auth_router
from app.routes.job_applications import router as jobs_router
from app.routes.notes import router as notes_router
from app.routes.documents import router as documents_router
from app.routes.users import router as users_router

require_jwt_secret()

app = FastAPI(title="Job Application Tracker")

if settings.ENABLE_RATE_LIMITING:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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

@app.get("/health")
def health_check():
    return {"status": "ok"}