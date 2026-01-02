from fastapi import HTTPException

from app.core.password_policy import ensure_strong_password, evaluate_password


def test_evaluate_password_reports_all_violations():
    violations = evaluate_password("password", email="user@example.com", username="User Example")
    assert "min_length" in violations
    assert "uppercase" in violations
    assert "number" in violations
    assert "special_char" in violations
    assert "contains_email" in violations
    assert "contains_name" in violations


def test_ensure_strong_password_raises_http_exception():
    try:
        ensure_strong_password("password", email="user@example.com", username="User")
    except HTTPException as exc:
        assert exc.status_code == 400
        details = exc.detail["details"]
        assert details["code"] == "WEAK_PASSWORD"
        assert "uppercase" in details["violations"]
    else:
        raise AssertionError("Weak password should raise HTTPException")


def test_ensure_strong_password_accepts_strong_password():
    ensure_strong_password("Valid_Password123!", email="user@example.com", username="User")

