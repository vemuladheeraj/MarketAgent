"""In-memory repository — deterministic storage for development and tests."""

from __future__ import annotations

from typing import Generic

from pydantic import BaseModel

from app.storage.base import Doc, Repository


class InMemoryRepository(Repository[Doc], Generic[Doc]):
    """Repository backed by an in-process dict.

    Deterministic and dependency-free; used by unit tests and as a fallback
    when Firestore credentials are unavailable.
    """

    def __init__(self, document_type: type[Doc], collection: str) -> None:
        self._model = document_type
        self.collection = collection
        self._store: dict[str, Doc] = {}

    def upsert(self, doc_id: str, document: Doc) -> None:
        self._store[doc_id] = document

    def get(self, doc_id: str) -> Doc | None:
        return self._store.get(doc_id)

    def list_all(self) -> list[Doc]:
        return list(self._store.values())

    def delete(self, doc_id: str) -> None:
        self._store.pop(doc_id, None)

    def count(self) -> int:
        return len(self._store)