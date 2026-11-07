"""Maker-checker validation helpers.

Pure validation only. No database access or data modification.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentActors:
    created_by: int
    approved_by: int | None = None
    posted_by: int | None = None


def _validate_user_id(value: int, field_name: str) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer user ID")


def validate_document_actors(actors: DocumentActors) -> None:
    """Enforce separation of creator, approver and poster identities."""

    _validate_user_id(actors.created_by, "created_by")

    if actors.approved_by is not None:
        _validate_user_id(actors.approved_by, "approved_by")

    if actors.posted_by is not None:
        _validate_user_id(actors.posted_by, "posted_by")

    if actors.approved_by == actors.created_by:
        raise ValueError("The document creator cannot approve their own document")

    if actors.posted_by is not None:
        if actors.approved_by is None:
            raise ValueError("A document must be approved before posting")

        if actors.posted_by == actors.created_by:
            raise ValueError("The document creator cannot post their own document")

        if actors.posted_by == actors.approved_by:
            raise ValueError("The approver cannot post the same document")