"""Storage package (repositories + factories)."""

from app.storage.base import COLLECTIONS, Repository, StorageError
from app.storage.factories import collection_for, create_repository
from app.storage.memory.inmemory_repository import InMemoryRepository

try:
    from app.storage.firestore.firestore_repository import FirestoreRepository
except Exception:  # pragma: no cover - dependency guard
    FirestoreRepository = None  # type: ignore[assignment,misc]

__all__ = [
    "COLLECTIONS",
    "FirestoreRepository",
    "InMemoryRepository",
    "Repository",
    "StorageError",
    "collection_for",
    "create_repository",
]
