# app/auth/__init__.py
"""
Authentication modules for Job Tracker.

This package contains:
- identity.py: Canonical authenticated identity model (auth-provider agnostic)
- cognito.py: Cognito JWT verification (read-only, no enforcement yet)
"""
from app.auth.identity import Identity

__all__ = ["Identity"]

