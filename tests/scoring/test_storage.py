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