from __future__ import annotations

from app.web.api import create_app


def test_web_api_has_signal_and_market_endpoints():
    app = create_app()
    routes = {route.path for route in app.routes}
    assert "/api/health" in routes
    assert "/api/signals" in routes
    assert "/api/market/{symbol}" in routes
    assert "/api/ask" in routes
    assert "/api/paper-trades" in routes
