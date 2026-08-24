"""Application-facing persistence facade.

Analysis code never talks to Firestore directly. This store maps domain
models onto the repository interface. When Firebase is not configured the
in-memory repositories are used so development and tests stay deterministic.

Firestore failures are logged and returned as ``False``; they never raise into
the quantitative pipeline. A failed persist/load marks storage as unavailable
so the risk engine can refuse new paper entries instead of sizing unsafely.
"""

from __future__ import annotations

from datetime import datetime

from app.analysis.regime import RegimeAssessment
from app.config.settings import FirestoreConfig
from app.logging.setup import get_logger, log_event
from app.models.events import SystemEvent
from app.models.options import OptionChainSnapshot
from app.models.risk import RiskAssessment, RiskState
from app.models.snapshots import MarketSnapshot
from app.models.trading import Signal
from app.storage.base import Repository, StorageError
from app.storage.factories import create_repository
from app.storage.memory.inmemory_repository import InMemoryRepository


def document_id(*parts: object) -> str:
    """Build a Firestore-safe document id (no slashes)."""
    raw = "_".join(str(p) for p in parts if p is not None and str(p) != "")
    return raw.replace("/", "-")


def compact_timestamp(ts: datetime) -> str:
    return ts.strftime("%Y%m%dT%H%M%S")


class MarketStore:
    """Typed repositories for the collections in specification §25."""

    def __init__(
        self,
        config: FirestoreConfig,
        *,
        repositories: dict[str, Repository] | None = None,
    ) -> None:
        self.config = config
        self._logger = get_logger("storage")
        if repositories is not None:
            self.snapshots = repositories["marketSnapshots"]
            self.option_snapshots = repositories["optionSnapshots"]
            self.signals = repositories["signals"]
            self.regimes = repositories["marketRegimes"]
            self.events = repositories["systemEvents"]
            self.risk_assessments = repositories["riskAssessments"]
            self.risk_state = repositories["riskState"]
            self.backend = "memory"
        else:
            self.snapshots = create_repository(MarketSnapshot, config)
            self.option_snapshots = create_repository(OptionChainSnapshot, config)
            self.signals = create_repository(Signal, config)
            self.regimes = create_repository(RegimeAssessment, config)
            self.events = create_repository(SystemEvent, config)
            self.risk_assessments = create_repository(RiskAssessment, config)
            self.risk_state = create_repository(RiskState, config)
            self.backend = (
                "firestore"
                if config.project_id and not isinstance(self.snapshots, InMemoryRepository)
                else "memory"
            )

    def persist_market_snapshot(self, snapshot: MarketSnapshot) -> bool:
        doc_id = document_id("snap", compact_timestamp(snapshot.timestamp))
        ok = self._upsert(self.snapshots, doc_id, snapshot, "marketSnapshots")
        for symbol, chain in snapshot.option_chains.items():
            chain_ok = self.persist_option_chain(chain)
            ok = ok and chain_ok
        return ok

    def persist_option_chain(self, chain: OptionChainSnapshot) -> bool:
        doc_id = document_id(
            chain.underlying_symbol,
            compact_timestamp(chain.expiry_date),
            compact_timestamp(chain.timestamp),
        )
        return self._upsert(self.option_snapshots, doc_id, chain, "optionSnapshots")

    def persist_signal(self, signal: Signal) -> bool:
        candidate = signal.candidate
        doc_id = document_id(
            candidate.symbol,
            candidate.strategy_name,
            compact_timestamp(signal.timestamp),
        )
        return self._upsert(self.signals, doc_id, signal, "signals")

    def persist_regime(self, assessment: RegimeAssessment) -> bool:
        doc_id = document_id(
            assessment.symbol,
            assessment.regime.value,
            compact_timestamp(assessment.timestamp),
        )
        return self._upsert(self.regimes, doc_id, assessment, "marketRegimes")

    def persist_risk_assessment(self, assessment: RiskAssessment) -> bool:
        doc_id = document_id(
            assessment.symbol,
            assessment.strategy_name,
            compact_timestamp(assessment.timestamp),
        )
        return self._upsert(self.risk_assessments, doc_id, assessment, "riskAssessments")

    def persist_system_event(self, event: SystemEvent) -> bool:
        doc_id = document_id(
            event.event_type.value,
            compact_timestamp(event.timestamp),
            event.source,
        )
        return self._upsert(self.events, doc_id, event, "systemEvents")

    def save_risk_state(self, state: RiskState) -> bool:
        return self._upsert(self.risk_state, "current", state, "riskState")

    def load_risk_state(self, default_account_size: float) -> RiskState:
        try:
            loaded = self.risk_state.get("current")
        except StorageError as exc:
            log_event(
                self._logger,
                "ERROR",
                "risk state load failed; refusing unsafe sizing",
                err=str(exc),
            )
            return RiskState(
                account_size=default_account_size,
                storage_available=False,
            )
        if loaded is None:
            return RiskState(account_size=default_account_size, storage_available=True)
        return loaded.model_copy(update={"storage_available": True})

    def _upsert(self, repo: Repository, doc_id: str, document, collection: str) -> bool:
        try:
            repo.upsert(doc_id, document)
            return True
        except StorageError as exc:
            log_event(
                self._logger,
                "ERROR",
                "storage upsert failed",
                collection=collection,
                doc_id=doc_id,
                err=str(exc),
            )
            return False
