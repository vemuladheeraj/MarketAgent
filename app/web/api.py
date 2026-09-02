from __future__ import annotations

from typing import Any, Callable

try:
    from fastapi import FastAPI
except Exception:  # pragma: no cover - dependency may be absent in minimal test envs
    class _Route:
        def __init__(self, path: str):
            self.path = path

    class FastAPI:  # type: ignore[override]
        def __init__(self, *args, **kwargs) -> None:
            self.routes: list[_Route] = []

        def get(self, path: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
                self.routes.append(_Route(path))
                return func
            return decorator

        def post(self, path: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
                self.routes.append(_Route(path))
                return func
            return decorator


# Global state for the web API (initialized at startup)
_global_context: Any = None


def set_global_context(context: Any) -> None:
    """Store the AppContext globally for API access."""
    global _global_context
    _global_context = context


def get_global_context() -> Any:
    """Retrieve the stored AppContext."""
    return _global_context


def create_app() -> FastAPI:
    app = FastAPI(title="MarketAgent Dashboard API")

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        """Health check endpoint."""
        return {"status": "ok", "service": "MarketAgent"}

    @app.get("/api/config")
    def runtime_config() -> dict[str, Any]:
        """Get the current runtime market/provider configuration."""
        ctx = get_global_context()
        if ctx is None:
            return {
                "market": "india",
                "provider": "indstocks",
                "available_markets": ["india", "us", "both"],
                "available_providers": ["indstocks", "nse", "us_markets"],
            }

        return {
            "market": ctx.settings.market.active_markets,
            "provider": ctx.settings.provider.name,
            "available_markets": ["india", "us", "both"],
            "available_providers": ["indstocks", "nse", "us_markets"],
        }

    @app.get("/api/system-status")
    def system_status() -> dict[str, Any]:
        """Return the current backend, AI, market, and provider status."""
        ctx = get_global_context()
        if ctx is None:
            return {
                "ok": False,
                "backend": "unhealthy",
                "api": "unhealthy",
                "ai_ready": False,
                "market": "india",
                "provider": "indstocks",
                "market_open": False,
                "message": "runtime context not initialized",
            }

        active_market = getattr(ctx.settings.market, "active_markets", "india")
        provider_name = getattr(ctx.settings.provider, "name", "indstocks")
        ai_ready = ctx.gemini_client is not None
        market_open = False
        try:
            if getattr(ctx, "scheduler", None) is not None:
                market_open = bool(ctx.scheduler.is_any_market_open())
        except Exception:
            market_open = False

        return {
            "ok": True,
            "backend": "healthy",
            "api": "healthy",
            "ai_ready": ai_ready,
            "market": active_market,
            "provider": provider_name,
            "market_open": market_open,
            "message": f"{active_market} / {provider_name} / {'open' if market_open else 'closed'}",
        }

    @app.post("/api/config")
    def update_runtime_config(payload: dict[str, Any]) -> dict[str, Any]:
        """Update runtime market/provider selection from the UI."""
        ctx = get_global_context()
        if ctx is None:
            return {"ok": False, "error": "runtime context not initialized"}

        market = str(payload.get("market", "")).strip().lower()
        provider = str(payload.get("provider", "")).strip().lower()
        allowed_markets = ["india", "us", "both"]
        allowed_providers = ["indstocks", "nse", "us_markets"]

        if market not in allowed_markets:
            return {"ok": False, "error": f"unsupported market: {market}"}
        if provider not in allowed_providers:
            return {"ok": False, "error": f"unsupported provider: {provider}"}

        ctx.settings.market.active_markets = market
        ctx.settings.provider.name = provider

        if getattr(ctx, "scheduler", None) is not None:
            ctx.scheduler.active_markets = market
            ctx.scheduler.config.active_markets = market

        try:
            from app.data.providers.factory import create_provider

            ctx.provider = create_provider(ctx.settings.provider)
            if ctx.pipeline is not None:
                ctx.pipeline.provider = ctx.provider
        except Exception as exc:  # pragma: no cover - provider creation can fail if deps missing
            return {"ok": False, "error": f"provider switch failed: {exc}"}

        return {
            "ok": True,
            "market": ctx.settings.market.active_markets,
            "provider": ctx.settings.provider.name,
        }

    @app.get("/api/signals")
    def signals() -> list[dict[str, Any]]:
        """Get recent signals from the store."""
        ctx = get_global_context()
        if ctx is None or ctx.store is None:
            return []
        
        try:
            all_signals = ctx.store.signals.list_all()
            return [
                {
                    "symbol": s.candidate.symbol,
                    "strategy": s.candidate.strategy_name,
                    "direction": s.candidate.direction.value,
                    "entry": s.candidate.entry,
                    "stop_loss": s.candidate.stop_loss,
                    "targets": s.candidate.targets,
                    "score": s.score,
                    "classification": s.classification.value,
                    "accepted": s.accepted,
                    "timestamp": s.timestamp.isoformat(),
                }
                for s in sorted(all_signals, key=lambda x: x.timestamp, reverse=True)[:50]
            ]
        except Exception:
            return []

    @app.get("/api/market/{symbol}")
    def market(symbol: str) -> dict[str, Any]:
        """Get current market snapshot for a symbol."""
        ctx = get_global_context()
        if ctx is None or ctx.store is None or ctx.provider is None:
            return {"symbol": symbol, "status": "unavailable", "error": "context not initialized"}
        
        try:
            # Try to get latest quote from the snapshot
            all_snapshots = ctx.store.snapshots.list_all()
            if not all_snapshots:
                return {"symbol": symbol, "status": "no_data"}
            
            latest = max(all_snapshots, key=lambda x: x.timestamp)
            quote = latest.quotes.get(symbol.upper())
            if quote is None:
                return {"symbol": symbol, "status": "not_in_latest_snapshot"}
            
            return {
                "symbol": symbol,
                "last_price": quote.last_price,
                "bid": quote.bid,
                "ask": quote.ask,
                "bid_size": quote.bid_size,
                "ask_size": quote.ask_size,
                "volume": quote.volume,
                "timestamp": quote.timestamp.isoformat(),
            }
        except Exception as e:
            return {"symbol": symbol, "status": "error", "error": str(e)}

    @app.get("/api/brief/{symbol}")
    def trade_brief(symbol: str) -> dict[str, Any]:
        """Get the current trade brief (actionable recommendation) for a symbol."""
        ctx = get_global_context()
        if ctx is None or ctx.store is None:
            return {"symbol": symbol, "action": "WAIT", "reason": "Context not initialized"}
        
        try:
            brief = ctx.store.load_current_trade_brief(symbol.upper())
            if brief is None:
                return {"symbol": symbol, "action": "WAIT", "reason": "No brief available yet"}
            
            contract_data = None
            if brief.contract is not None:
                contract_data = {
                    "tradingsymbol": brief.contract.tradingsymbol,
                    "strike": brief.contract.strike,
                    "option_type": brief.contract.option_type.value,
                    "last_price": brief.contract.last_price,
                    "bid": brief.contract.bid,
                    "ask": brief.contract.ask,
                    "delta": brief.contract.delta,
                    "iv": brief.contract.iv,
                    "open_interest": brief.contract.open_interest,
                    "spread_pct": brief.contract.spread_pct,
                }
            
            return {
                "symbol": brief.underlying_symbol,
                "action": brief.action,
                "strategy": brief.strategy_name,
                "direction": brief.underlying_direction.value if brief.underlying_direction else None,
                "entry": brief.entry,
                "stop_loss": brief.stop_loss,
                "targets": brief.targets,
                "contract": contract_data,
                "risk_reward": brief.risk_reward,
                "lots": brief.lots,
                "probability": brief.probability,
                "score": brief.score,
                "regime": brief.regime,
                "rationale": brief.rationale,
                "warnings": brief.warnings,
                "waiting_reason": brief.waiting_reason,
                "generated_at": brief.generated_at.isoformat(),
                "valid_until": brief.valid_until.isoformat(),
            }
        except Exception as e:
            return {"symbol": symbol, "action": "ERROR", "error": str(e)}

    @app.get("/api/paper-trades")
    def paper_trades() -> list[dict[str, Any]]:
        """Get all open and closed paper trading positions."""
        ctx = get_global_context()
        if ctx is None or ctx.store is None:
            return []
        
        try:
            positions = ctx.store.list_paper_positions()
            return [
                {
                    "position_id": p.position_id,
                    "symbol": p.symbol,
                    "entry_price": p.entry_price,
                    "entry_time": p.entry_time.isoformat(),
                    "quantity": p.quantity,
                    "direction": p.direction.value,
                    "strategy": p.strategy_name,
                    "stop_loss": p.stop_loss,
                    "targets": p.targets,
                    "current_price": p.current_price,
                    "stage": p.stage.value,
                    "pnl": p.pnl,
                    "pnl_pct": p.pnl_pct,
                }
                for p in sorted(positions, key=lambda x: x.entry_time, reverse=True)
            ]
        except Exception:
            return []

    @app.post("/api/ask")
    def ask(payload: dict[str, str]) -> dict[str, Any]:
        """Answer trader questions using Gemini AI."""
        ctx = get_global_context()
        if ctx is None or ctx.gemini_client is None:
            return {
                "question": payload.get("question", ""),
                "answer": "Gemini AI is not available. Please check configuration.",
            }
        
        question = payload.get("question", "").strip()
        if not question:
            return {"question": "", "answer": "Please provide a question."}
        
        try:
            # Build a minimal market context from the latest snapshot
            market_context = {}
            try:
                all_snapshots = ctx.store.snapshots.list_all()
                if all_snapshots:
                    latest = max(all_snapshots, key=lambda x: x.timestamp)
                    market_context = {
                        "vix": latest.vix,
                        "timestamp": latest.timestamp.isoformat(),
                        "quotes": {
                            k: {"last_price": v.last_price, "bid": v.bid, "ask": v.ask}
                            for k, v in latest.quotes.items()
                        },
                    }
            except Exception:
                pass
            
            answer = ctx.gemini_client.answer_trader_question(question, market_context)
            return {
                "question": question,
                "answer": answer,
            }
        except Exception as e:
            return {
                "question": question,
                "answer": f"Error: {str(e)}",
            }

    @app.get("/api/regime/{symbol}")
    def regime(symbol: str) -> dict[str, Any]:
        """Get the market regime classification for a symbol."""
        ctx = get_global_context()
        if ctx is None or ctx.store is None:
            return {"symbol": symbol, "regime": "unknown"}
        
        try:
            all_regimes = ctx.store.regimes.list_all()
            matching = [r for r in all_regimes if r.symbol.upper() == symbol.upper()]
            if not matching:
                return {"symbol": symbol, "regime": "unknown"}
            
            latest = max(matching, key=lambda x: x.timestamp)
            return {
                "symbol": symbol,
                "regime": latest.regime.value,
                "confidence": latest.confidence,
                "reasons": latest.reasons,
                "timestamp": latest.timestamp.isoformat(),
            }
        except Exception:
            return {"symbol": symbol, "regime": "error"}

    return app
