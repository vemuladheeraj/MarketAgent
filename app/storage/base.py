"""Storage repository abstractions.

A :class:`Repository` is a typed, model-backed store per document type. The
concrete implementations are:

* :class:`InMemoryRepository` — deterministic dev/test storage.
* :class:`FirestoreRepository` — Google Cloud Firestore (Phase 3).

Firestore is *optional*: the rest of the system only depends on the
Repository interface, so analysis works without any network/credentials.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from pydantic import BaseModel

Doc = TypeVar("Doc", bound=BaseModel)

#: Mapping of collection names used by the storage layer.
COLLECTIONS = tuple(
    [
        "marketSnapshots",
        "optionSnapshots",
        "signals",
        "paperTrades",
        "completedTrades",
        "strategies",
        "strategyPerformance",
        "marketRegimes",
        "geminiAnalyses",
        "alerts",
        "configuration",
        "systemEvents",
        "riskAssessments",
        "riskState",
    ]
)


class StorageError(Exception):
    """Raised when a storage operation fails."""


class Repository(ABC, Generic[Doc]):
    """Minimal repository interface modelled after Firestore semantics."""

    collection: str

    @abstractmethod
    def upsert(self, doc_id: str, document: Doc) -> None: ...

    @abstractmethod
    def get(self, doc_id: str) -> Doc | None: ...

    @abstractmethod
    def list_all(self) -> list[Doc]: ...

    @abstractmethod
    def delete(self, doc_id: str) -> None: ...

    @abstractmethod
    def count(self) -> int: ...