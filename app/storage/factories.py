"""Repository factories and per-model collection-name mapping."""

from __future__ import annotations

from typing import Callable

from app.config.settings import FirestoreConfig
from app.storage.base import Doc, Repository
from app.storage.memory.inmemory_repository import InMemoryRepository

try:
    from app.storage.firestore.firestore_repository import FirestoreRepository
except Exception:  # pragma: no cover - dependency guard
    FirestoreRepository = None  # type: ignore[assignment,misc]


#: Model type -> collection name (see specification §25).
def collection_for(model_name: str) -> str:
    mapping = {
        "MarketSnapshot": "marketSnapshots",
        "OptionChainSnapshot": "optionSnapshots",
        "Signal": "signals",
        "PaperTrade": "paperTrades",
        "TradeResult": "completedTrades",
        "StrategyPerformance": "strategyPerformance",
        "RegimeAssessment": "marketRegimes",
        "RiskAssessment": "riskAssessments",
        "RiskState": "riskState",
        "GeminiAnalysis": "geminiAnalyses",
        "Alert": "alerts",
        "SystemEvent": "systemEvents",
        "TradeBrief": "tradeBriefs",
    }
    return mapping.get(model_name, f"{model_name.lower()}s")


def create_repository(
    document_type: type[Doc],
    config: FirestoreConfig,
) -> Repository[Doc]:
    """Return the appropriate repository for the provided Firestore config.

    When a project is configured, a Firestore repository is returned;
    otherwise the deterministic :class:`InMemoryRepository` is used so the
    system keeps running for development/tests.
    """
    collection = collection_for(document_type.__name__)
    if FirestoreRepository is not None and config.project_id:
        return FirestoreRepository(
            document_type=document_type,
            collection=collection,
            credential_path=config.credentials_path or None,
            database=config.database,
            project_id=config.project_id or None,
        )
    return InMemoryRepository(document_type=document_type, collection=collection)