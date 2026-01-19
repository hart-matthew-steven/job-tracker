from __future__ import annotations

from datetime import datetime
from difflib import SequenceMatcher
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ai import AIConversation
from app.models.artifact import (
    AIArtifact,
    AIConversationArtifact,
    ArtifactSourceType,
    ArtifactStatus,
    ArtifactType,
)
from app.models.user import User
from app.services import artifact_storage
from app.tasks import artifacts as artifact_tasks
from app.celery_app import enqueue


class ArtifactNotFoundError(Exception):
    pass


class ArtifactService:
    def __init__(self, db: Session, user: User) -> None:
        self.db = db
        self.user = user

    def issue_upload(self, conversation_id: int, artifact_type: ArtifactType, filename: str, content_type: str | None):
        conversation = self._get_conversation(conversation_id)
        artifact = self._create_artifact(
            conversation,
            artifact_type=artifact_type,
            source_type=ArtifactSourceType.upload,
            initial_status=ArtifactStatus.pending,
            source_details={"filename": filename, "content_type": content_type},
        )

        key = artifact_storage.build_s3_key(self.user.id, artifact.id, filename)
        artifact.s3_key = key
        upload_url = artifact_storage.presign_upload(key, content_type)
        self._link_artifact(conversation, artifact_type, artifact)
        self._trim_versions(artifact_type)
        self.db.commit()
        self.db.refresh(artifact)
        return artifact, upload_url

    def mark_upload_complete(self, artifact_id: int) -> AIArtifact:
        artifact = self._get_artifact(artifact_id)
        if artifact.source_type != ArtifactSourceType.upload:
            raise ValueError("Artifact is not an upload.")
        artifact.status = ArtifactStatus.pending
        artifact.failure_reason = None
        self.db.commit()
        enqueue(artifact_tasks.process_uploaded_artifact, artifact_id)
        return artifact

    def create_from_text(
        self,
        conversation_id: int,
        artifact_type: ArtifactType,
        content: str,
        source_type: ArtifactSourceType = ArtifactSourceType.paste,
        source_details: dict | None = None,
    ) -> AIArtifact:
        conversation = self._get_conversation(conversation_id)
        artifact = self._create_artifact(
            conversation,
            artifact_type=artifact_type,
            source_type=source_type,
            initial_status=ArtifactStatus.ready,
            source_details=source_details or {},
            text_content=content.strip(),
        )
        self._link_artifact(conversation, artifact_type, artifact)
        self._trim_versions(artifact_type)
        self.db.commit()
        self.db.refresh(artifact)
        return artifact

    def create_from_url(self, conversation_id: int, artifact_type: ArtifactType, url: str) -> AIArtifact:
        conversation = self._get_conversation(conversation_id)
        artifact = self._create_artifact(
            conversation,
            artifact_type=artifact_type,
            source_type=ArtifactSourceType.url,
            initial_status=ArtifactStatus.pending,
            source_details={"url": url},
        )
        self._link_artifact(conversation, artifact_type, artifact)
        self._trim_versions(artifact_type)
        self.db.commit()
        enqueue(artifact_tasks.scrape_job_description, artifact.id)
        return artifact

    def pin_artifact(self, conversation_id: int, artifact_id: int) -> AIArtifact:
        conversation = self._get_conversation(conversation_id)
        artifact = self._get_artifact(artifact_id)
        if artifact.user_id != self.user.id:
            raise ArtifactNotFoundError
        self._link_artifact(conversation, artifact.artifact_type, artifact)
        self.db.commit()
        return artifact

    def list_conversation_artifacts(self, conversation_id: int) -> Sequence[AIConversationArtifact]:
        conversation = self._get_conversation(conversation_id)
        return (
            self.db.query(AIConversationArtifact)
            .filter_by(conversation_id=conversation.id)
            .join(AIArtifact)
            .order_by(AIConversationArtifact.role.asc(), AIConversationArtifact.pinned_at.desc())
            .all()
        )

    def list_role_history(self, conversation_id: int, role: ArtifactType) -> list[AIArtifact]:
        conversation = self._get_conversation(conversation_id)
        return (
            self.db.query(AIArtifact)
            .filter(
                AIArtifact.user_id == self.user.id,
                AIArtifact.conversation_id == conversation.id,
                AIArtifact.artifact_type == role,
            )
            .order_by(AIArtifact.version_number.desc())
            .all()
        )

    def get_artifact_diff(
        self,
        artifact_id: int,
        compare_to_id: int | None = None,
    ) -> tuple[AIArtifact, AIArtifact, list[tuple[str, str]]]:
        base_artifact = self._get_artifact(artifact_id)
        compare_artifact: AIArtifact | None = None
        if compare_to_id:
            compare_artifact = self._get_artifact(compare_to_id)
        elif base_artifact.previous_version_id:
            compare_artifact = self._get_artifact(base_artifact.previous_version_id)
        if not compare_artifact:
            raise ValueError("No comparison artifact available.")
        if base_artifact.text_content is None or compare_artifact.text_content is None:
            raise ValueError("Diff unavailable because one of the artifacts is missing text content.")
        diff = _compute_diff(compare_artifact.text_content, base_artifact.text_content)
        return base_artifact, compare_artifact, diff

    def _get_artifact(self, artifact_id: int) -> AIArtifact:
        artifact = (
            self.db.query(AIArtifact)
            .filter(AIArtifact.id == artifact_id, AIArtifact.user_id == self.user.id)
            .one_or_none()
        )
        if not artifact:
            raise ArtifactNotFoundError
        return artifact

    def _get_conversation(self, conversation_id: int) -> AIConversation:
        conversation = (
            self.db.query(AIConversation)
            .filter(AIConversation.id == conversation_id, AIConversation.user_id == self.user.id)
            .one_or_none()
        )
        if not conversation:
            raise ArtifactNotFoundError
        return conversation

    def _next_version_number(self, artifact_type: ArtifactType) -> int:
        max_version = (
            self.db.execute(
                select(func.max(AIArtifact.version_number)).where(
                    AIArtifact.user_id == self.user.id,
                    AIArtifact.artifact_type == artifact_type,
                )
            )
            .scalar()
            or 0
        )
        return max_version + 1

    def _create_artifact(
        self,
        conversation: AIConversation,
        *,
        artifact_type: ArtifactType,
        source_type: ArtifactSourceType,
        initial_status: ArtifactStatus,
        source_details: dict | None,
        text_content: str | None = None,
    ) -> AIArtifact:
        artifact = AIArtifact(
            user_id=self.user.id,
            conversation_id=conversation.id,
            artifact_type=artifact_type,
            source_type=source_type,
            status=initial_status,
            source_details=source_details or {},
            text_content=text_content,
            version_number=self._next_version_number(artifact_type),
        )
        self.db.add(artifact)
        self.db.flush()
        return artifact

    def _link_artifact(self, conversation: AIConversation, role: ArtifactType, artifact: AIArtifact) -> None:
        link = (
            self.db.query(AIConversationArtifact)
            .filter_by(conversation_id=conversation.id, role=role)
            .one_or_none()
        )
        if link:
            artifact.previous_version_id = link.artifact_id
            link.artifact_id = artifact.id
            link.is_active = True
            link.pinned_at = datetime.utcnow()
        else:
            link = AIConversationArtifact(
                conversation_id=conversation.id,
                artifact_id=artifact.id,
                role=role,
                is_active=True,
                pinned_at=datetime.utcnow(),
            )
            self.db.add(link)

    def _trim_versions(self, artifact_type: ArtifactType) -> None:
        max_versions = settings.MAX_ARTIFACT_VERSIONS
        if max_versions <= 0:
            return

        artifacts = (
            self.db.query(AIArtifact)
            .filter(AIArtifact.user_id == self.user.id, AIArtifact.artifact_type == artifact_type)
            .order_by(AIArtifact.created_at.desc(), AIArtifact.id.desc())
            .all()
        )
        for idx, artifact in enumerate(artifacts, start=1):
            if idx <= max_versions:
                continue
            if artifact.s3_key:
                try:
                    artifact_storage.delete(artifact.s3_key)
                except Exception:
                    pass
            self.db.delete(artifact)


def _compute_diff(old_text: str, new_text: str) -> list[tuple[str, str]]:
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    matcher = SequenceMatcher(a=old_lines, b=new_lines)
    diff: list[tuple[str, str]] = []
    for opcode, i1, i2, j1, j2 in matcher.get_opcodes():
        if opcode == "equal":
            for line in old_lines[i1:i2]:
                diff.append(("equal", line))
        elif opcode == "delete":
            for line in old_lines[i1:i2]:
                diff.append(("delete", line))
        elif opcode == "insert":
            for line in new_lines[j1:j2]:
                diff.append(("insert", line))
        elif opcode == "replace":
            for line in old_lines[i1:i2]:
                diff.append(("delete", line))
            for line in new_lines[j1:j2]:
                diff.append(("insert", line))
    return diff
