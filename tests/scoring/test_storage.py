"""Tests for the storage layer (in-memory repository + factories)."""

from __future__ import annotations

import datetime

from app.config.settings import FirestoreConfig
from app.storage import (
    InMemoryRepository,
    collection_for,
    create_repository,
)
from app.models import MarketCandle, MarketQuote, MarketSnapshot
from app.models.time import IST


def _quote() -> MarketQuote:
    return MarketQuote(
        symbol="NIFTY",
        timestamp=datetime.datetime(2025, 6, 27, 15, 29, 0, tzinfo=IST),
        bid=100.5,
        ask=100.7,
    )


class TestInMemoryRepository:
    def test_upsert_get(self):
        repo = InMemoryRepository(MarketQuote, "quotes")
        q = _quote()
        repo.upsert("nifty", q)
        assert repo.get("nifty") == q
        assert repo.count() == 1

    def test_get_missing_returns_none(self):
        repo = InMemoryRepository(MarketQuote, "quotes")
        assert repo.get("missing") is None

    def test_delete(self):
        repo = InMemoryRepository(MarketQuote, "quotes")
        repo.upsert("1", _quote())
        repo.delete("1")
        assert repo.count() == 0

    def test_upsert_overwrites(self):
        repo = InMemoryRepository(MarketQuote, "quotes")
        repo.upsert("1", _quote())
        other = _quote().model_copy(update={"bid": 200.0})
        repo.upsert("1", other)
        assert repo.get("1").bid == 200.0

    def test_list_all(self):
        repo = InMemoryRepository(MarketQuote, "quotes")
        repo.upsert("1", _quote())
        repo.upsert("2", _quote().model_copy(update={"symbol": "BANKNIFTY"}))
        assert len(repo.list_all()) == 2


class TestFactories:
    def test_collection_mapping(self):
        assert collection_for("MarketSnapshot") == "marketSnapshots"
        assert collection_for("PaperTrade") == "paperTrades"
        assert collection_for("RiskState") == "riskState"
        assert collection_for("UnknownModel") == "unknownmodels"

    def test_empty_config_yields_in_memory(self):
        repo = create_repository(MarketQuote, FirestoreConfig(project_id=""))
        assert isinstance(repo, InMemoryRepository)

    def test_snapshot_model_roundtrip(self):
        repo = InMemoryRepository(MarketSnapshot, "marketSnapshots")
        snap = MarketSnapshot(timestamp=datetime.datetime.now(IST))
        repo.upsert("2025-06-27", snap)
        got = repo.get("2025-06-27")
        assert got is not None
        assert got.timestamp.tzinfo is not None


def _repos():
    from app.analysis.regime import RegimeAssessment
    from app.models.events import SystemEvent
    from app.models.options import OptionChainSnapshot
    from app.models.risk import RiskAssessment, RiskState
    from app.models.trading import Signal

    return {
        "marketSnapshots": InMemoryRepository(MarketSnapshot, "marketSnapshots"),
        "optionSnapshots": InMemoryRepository(OptionChainSnapshot, "optionSnapshots"),
        "signals": InMemoryRepository(Signal, "signals"),
        "marketRegimes": InMemoryRepository(RegimeAssessment, "marketRegimes"),
        "systemEvents": InMemoryRepository(SystemEvent, "systemEvents"),
        "riskAssessments": InMemoryRepository(RiskAssessment, "riskAssessments"),
        "riskState": InMemoryRepository(RiskState, "riskState"),
    }


class TestMarketStore:
    def test_persist_snapshot_and_option_chains(self):
        from app.models import OptionChainEntry, OptionChainSnapshot, OptionType
        from app.storage.market_store import MarketStore

        store = MarketStore(FirestoreConfig(project_id=""), repositories=_repos())
        ts = datetime.datetime(2025, 6, 27, 15, 29, tzinfo=IST)
        chain = OptionChainSnapshot(
            underlying_symbol="NIFTY",
            timestamp=ts,
            spot_price=24000,
            expiry_date=datetime.datetime(2025, 7, 31, tzinfo=IST),
            entries=[
                OptionChainEntry(
                    strike=24000,
                    option_type=OptionType.CALL,
                    expiry_date=datetime.datetime(2025, 7, 31, tzinfo=IST),
                    open_interest=10,
                    last_price=100,
                )
            ],
        )
        snap = MarketSnapshot(timestamp=ts, option_chains={"NIFTY": chain})
        assert store.persist_market_snapshot(snap)
        assert store.snapshots.count() == 1
        assert store.option_snapshots.count() == 1

    def test_risk_state_roundtrip(self):
        from app.models.risk import RiskState
        from app.storage.market_store import MarketStore

        store = MarketStore(FirestoreConfig(project_id=""), repositories=_repos())
        state = RiskState(account_size=1_000_000, trades_today=2)
        assert store.save_risk_state(state)
        loaded = store.load_risk_state(default_account_size=1_000_000)
        assert loaded.trades_today == 2
        assert loaded.storage_available is True

    def test_missing_risk_state_uses_default(self):
        from app.storage.market_store import MarketStore

        store = MarketStore(FirestoreConfig(project_id=""), repositories=_repos())
        loaded = store.load_risk_state(default_account_size=50_000)
        assert loaded.account_size == 50_000
        assert loaded.storage_available is True

    def test_upsert_failure_is_fail_soft(self):
        from app.storage.base import StorageError
        from app.storage.market_store import MarketStore

        class Boom(InMemoryRepository):
            def upsert(self, doc_id, document):
                raise StorageError("firestore down")

        repos = _repos()
        repos["marketSnapshots"] = Boom(MarketSnapshot, "marketSnapshots")
        store = MarketStore(FirestoreConfig(project_id=""), repositories=repos)
        snap = MarketSnapshot(timestamp=datetime.datetime.now(IST))
        assert store.persist_market_snapshot(snap) is False

    def test_risk_state_load_failure_marks_unavailable(self):
        from app.models.risk import RiskState
        from app.storage.base import StorageError
        from app.storage.market_store import MarketStore

        class Boom(InMemoryRepository):
            def get(self, doc_id):
                raise StorageError("firestore down")

        repos = _repos()
        repos["riskState"] = Boom(RiskState, "riskState")
        store = MarketStore(FirestoreConfig(project_id=""), repositories=repos)
        loaded = store.load_risk_state(1_000_000)
        assert loaded.storage_available is False