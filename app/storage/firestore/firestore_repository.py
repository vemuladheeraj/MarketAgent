"""Firestore-backed repository (Phase 3).

Uses the ``google-cloud-firestore``/``firebase_admin`` SDK. The client is
created lazily so the rest of the application never needs Firestore to be
configured unless a repository is actually requested.

Document IDs default to a stable stringified form of the model's primary
key (``id`` field) or, when missing, are generated deterministically from a
timestamp.
"""

from __future__ import annotations

from typing import Any, Generic

from pydantic import BaseModel, ValidationError

from app.storage.base import Doc, Repository, StorageError

try:  # pragma: no cover - environment-dependent import
    from firebase_admin import credentials, firestore, initialize_app
except ImportError:  # pragma: no cover
    credentials = None  # type: ignore[assignment]
    firestore = None  # type: ignore[assignment]
    initialize_app = None  # type: ignore[assignment]


class FirestoreRepository(Repository[Doc], Generic[Doc]):
    """Firestore-backed repository storing models as documents."""

    def __init__(
        self,
        document_type: type[Doc],
        collection: str,
        credential_path: str | None = None,
        database: str = "market",
    ) -> None:
        if firestore is None:
            raise StorageError(
                "firebase-admin is not installed; run pip install firebase-admin"
            )
        self._model = document_type
        self.collection = collection
        self._credential_path = credential_path
        self._database = database
        self._client: Any | None = None
        self._app: Any | None = None

    # -- client -------------------------------------------------------
    def _ensure_client(self):
        if self._client is not None:
            return self._client
        try:
            if self._credential_path:
                cred = credentials.Certificate(self._credential_path)
                self._app = initialize_app(
                    credentials=cred, options={"projectId": "market-agent"}
                )
            else:
                self._app = initialize_app()  # GOOGLE_APPLICATION_CREDENTIALS
        except Exception as exc:  # pragma: no cover - environment-dependent
            raise StorageError(f"cannot initialize firebase app: {exc}") from exc
        self._client = firestore.client(app=self._app, database=self._database)
        return self._client

    # -- repository interface ------------------------------------------
    def upsert(self, doc_id: str, document: Doc) -> None:
        data = document.model_dump(mode="json", exclude_none=True)
        try:
            self._coll_ref().document(doc_id).set(data)
        except Exception as exc:
            raise StorageError(f"firestore upsert failed: {exc}") from exc

    def get(self, doc_id: str) -> Doc | None:
        try:
            doc = self._coll_ref().document(doc_id).get()
        except Exception as exc:
            raise StorageError(f"firestore get failed: {exc}") from exc
        if not doc.exists:
            return None
        try:
            return self._model.model_validate(doc.to_dict())
        except ValidationError as exc:
            raise StorageError(
                f"firestore document {doc_id!r} failed validation: {exc}"
            ) from exc

    def list_all(self) -> list[Doc]:
        try:
            snapshots = self._coll_ref().stream()
        except Exception as exc:
            raise StorageError(f"firestore list failed: {exc}") from exc
        docs = []
        for doc in snapshots:
            try:
                docs.append(self._model.model_validate(doc.to_dict()))
            except ValidationError:
                continue  # skip malformed documents
        return docs

    def delete(self, doc_id: str) -> None:
        try:
            self._coll_ref().document(doc_id).delete()
        except Exception as exc:
            raise StorageError(f"firestore delete failed: {exc}") from exc

    def count(self) -> int:
        # Firestore count queries are limited; stream-based count is fine for
        # the small doc volumes this system writes.
        return len(self.list_all())

    def _coll_ref(self):
        return self._ensure_client().collection(self.collection)