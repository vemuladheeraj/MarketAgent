"""News analysis and macro context provider."""

from __future__ import annotations

from datetime import datetime

from app.models.ai import NewsItem
from app.models.time import now_ist


class NewsContextManager:
    """Stores and retrieves relevant macro/market news items."""

    def __init__(self) -> None:
        self._news_items: list[NewsItem] = []

    def add_news(self, news: NewsItem) -> None:
        self._news_items.append(news)

    def get_recent_news(self, symbol: str | None = None, limit: int = 10) -> list[NewsItem]:
        items = self._news_items
        if symbol:
            items = [n for n in items if not n.symbols or symbol in n.symbols]
        return sorted(items, key=lambda n: n.timestamp, reverse=True)[:limit]

    def aggregate_sentiment(self, symbol: str | None = None) -> float:
        recent = self.get_recent_news(symbol, limit=10)
        if not recent:
            return 0.0
        return sum(n.sentiment_score for n in recent) / len(recent)
