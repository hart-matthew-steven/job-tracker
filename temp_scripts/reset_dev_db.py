"""
Dev-only reset script for Job Tracker.

What it does:
- Deletes S3 objects referenced by job_documents.s3_key (best-effort).
- Truncates these tables with identity reset:
  job_application_notes, job_applications, job_documents, refresh_tokens, users
  using TRUNCATE ... RESTART IDENTITY CASCADE;

Guardrails:
- Requires ENV=dev
- Requires confirmation prompt unless --yes is passed
- Logs actions to logs/ with a timestamped file
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Iterable


# Allow `import app.*` from backend/
REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))


from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.services.s3 import delete_object  # noqa: E402


TABLES_TO_TRUNCATE = [
    "job_application_notes",
    "job_applications",
    "job_documents",
    "refresh_tokens",
    "users",
]


def utc_now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def iter_s3_keys(db) -> list[str]:
    rows = db.execute(text("SELECT s3_key FROM job_documents")).fetchall()
    keys: list[str] = []
    for (k,) in rows:
        if not k:
            continue
        k = str(k).strip()
        if k:
            keys.append(k)
    # De-dupe while preserving order
    seen = set()
    out: list[str] = []
    for k in keys:
        if k in seen:
            continue
        seen.add(k)
        out.append(k)
    return out


def log_write(fp: Path, lines: Iterable[str]) -> None:
    fp.parent.mkdir(parents=True, exist_ok=True)
    with fp.open("a", encoding="utf-8") as f:
        for line in lines:
            f.write(line.rstrip("\n") + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Dev reset: S3 cleanup + truncate tables.")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt.")
    args = parser.parse_args()

    if (settings.ENV or "").strip().lower() != "dev":
        print(f"Refusing to run: ENV must be 'dev' (got {settings.ENV!r})")
        return 2

    log_path = REPO_ROOT / "logs" / f"reset_dev_db_{utc_now_stamp()}.log"
    log_write(log_path, [f"[start] {datetime.now(timezone.utc).isoformat()} env={settings.ENV}"])
    log_write(log_path, [f"[db] host_db={settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME} (creds redacted)"])

    if not args.yes:
        msg = (
            "WARNING: This will DELETE S3 objects referenced by job_documents and TRUNCATE tables:\n"
            f"  {', '.join(TABLES_TO_TRUNCATE)}\n\n"
            "Type RESET to continue: "
        )
        resp = input(msg).strip()
        if resp != "RESET":
            print("Cancelled.")
            log_write(log_path, ["[cancelled] user did not confirm"])
            return 1

    deleted = 0
    delete_failed = 0

    with SessionLocal() as db:
        # 1) Collect S3 keys before truncating job_documents
        keys = iter_s3_keys(db)
        log_write(log_path, [f"[s3] found_keys={len(keys)} bucket={settings.S3_BUCKET_NAME!r}"])

        # 2) Best-effort delete in S3
        if settings.S3_BUCKET_NAME and settings.AWS_REGION:
            for k in keys:
                try:
                    delete_object(k)
                    deleted += 1
                    log_write(log_path, [f"[s3] deleted key={k}"])
                except Exception as e:
                    delete_failed += 1
                    log_write(log_path, [f"[s3] delete_failed key={k} err={type(e).__name__}: {e}"])
        else:
            log_write(log_path, ["[s3] skipped deletion: S3_BUCKET_NAME/AWS_REGION not configured"])

        # 3) Truncate tables
        sql = "TRUNCATE " + ", ".join(TABLES_TO_TRUNCATE) + " RESTART IDENTITY CASCADE;"
        log_write(log_path, [f"[db] executing: {sql}"])
        db.execute(text(sql))
        db.commit()

    log_write(
        log_path,
        [
            f"[done] s3_deleted={deleted} s3_failed={delete_failed}",
            f"[done] {datetime.now(timezone.utc).isoformat()}",
        ],
    )
    print(f"Done. Log written to: {log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())




