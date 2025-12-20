from app.services.jobs import normalize_tags


def test_normalize_tags_dedup_trim_lower_limit():
    tags = normalize_tags([None, "  Python  ", "python", "REMOTE", "", "x" * 100])
    assert tags == ["python", "remote", "x" * 64]

    many = normalize_tags([f"t{i}" for i in range(100)])
    assert len(many) == 50


