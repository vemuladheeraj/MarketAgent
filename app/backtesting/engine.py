"""Deterministic, no-lookahead backtesting engine.

This engine steps through historical market candles bar-by-bar, strictly
enforcing that decisions at time t only observe information up to t.
Trades are sized using the risk engine, executed with realistic transaction
costs and slippage, and evaluated against stop-loss, targets, and time exits.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Literal
import uuid

from app.analysis.regime.classifier import RegimeAssessment, RegimeClassifier
from app.analysis.technical.engine import TechnicalAnalyzer
from app.config.settings import (
    RiskConfig,
    SignalConfig,
    StrategyConfig,
    TransactionCostConfig,
)
from app.logging.setup import get_logger, log_event
from app.models.backtesting import (
    BacktestResult,
    BacktestTrade,
    ExitReason,
)
from app.models.candle import MarketCandle
from app.models.enums import DataQuality, Direction, MarketRegime
from app.models.options import OptionChainSnapshot
from app.models.options_analysis import OptionMetrics
from app.models.risk import RiskAssessment, RiskState
from app.models.snapshots import BreadthSnapshot
from app.models.trading import Signal, StrategyCandidate
from app.risk.costs import TransactionCostModel
from app.risk.engine import RiskEngine
from app.risk.position_sizing import PositionSizer
from app.scoring.signal_scorer import SignalScorer
from app.strategies.base.strategy import BaseStrategy, StrategyContext
from app.strategies.implementations import default_strategies
from app.backtesting.metrics import calculate_performance


class BacktestEngine:
    """Historical event-driven bar-by-bar backtesting engine."""

    def __init__(
        self,
        *,
        strategies: list[BaseStrategy] | None = None,
        risk_config: RiskConfig | None = None,
        cost_config: TransactionCostConfig | None = None,
        signal_config: SignalConfig | None = None,
        strategy_config: StrategyConfig | None = None,
        lot_size: int = 1,
        point_value: float = 1.0,
        min_lookback_bars: int = 30,
        max_holding_bars: int | None = None,
        execution_timing: Literal["next_open", "current_close"] = "next_open",
        pessimistic_intrabar_exit: bool = True,
        risk_free_rate: float = 0.06,
    ) -> None:
        self.strategies = strategies if strategies is not None else default_strategies()
        self.risk_config = risk_config or RiskConfig()
        self.cost_config = cost_config or TransactionCostConfig()
        self.signal_config = signal_config or SignalConfig()
        self.strategy_config = strategy_config or StrategyConfig()
        self.lot_size = lot_size
        self.point_value = point_value
        self.min_lookback_bars = min_lookback_bars
        self.max_holding_bars = max_holding_bars
        self.execution_timing = execution_timing
        self.pessimistic_intrabar_exit = pessimistic_intrabar_exit
        self.risk_free_rate = risk_free_rate

        self.technical_analyzer = TechnicalAnalyzer()
        self.regime_classifier = RegimeClassifier()
        self.scorer = SignalScorer(self.signal_config)
        self.cost_model = TransactionCostModel(self.cost_config)
        self.risk_engine = RiskEngine(
            self.risk_config,
            self.cost_model,
            lot_size=self.lot_size,
            point_value=self.point_value,
        )
        self._logger = get_logger("backtesting")

    def run(
        self,
        candles: Sequence[MarketCandle],
        *,
        option_chains: dict[datetime, OptionChainSnapshot] | None = None,
        option_metrics: dict[datetime, OptionMetrics] | None = None,
        breadth_history: dict[datetime, BreadthSnapshot] | None = None,
        vix_history: dict[datetime, float] | None = None,
        initial_capital: float | None = None,
        strategy_name: str | None = None,
    ) -> BacktestResult:
        """Execute a backtest run on historical candles.

        Parameters
        ----------
        candles:
            Chronologically ordered market candles.
        option_chains:
            Optional mapping of timestamp -> OptionChainSnapshot.
        option_metrics:
            Optional mapping of timestamp -> OptionMetrics.
        breadth_history:
            Optional mapping of timestamp -> BreadthSnapshot.
        vix_history:
            Optional mapping of timestamp -> India VIX value.
        initial_capital:
            Starting portfolio cash in INR.
        strategy_name:
            Optional filter to run only a single specific strategy by name.
        """
        if not candles:
            raise ValueError("cannot backtest with empty candle sequence")

        # Verify sorted timestamps
        for i in range(1, len(candles)):
            if candles[i].timestamp < candles[i - 1].timestamp:
                raise ValueError("candles must be sorted in ascending chronological order")

        capital = initial_capital if initial_capital is not None else self.risk_config.account_size
        symbol = candles[0].symbol
        backtest_id = f"bt_{uuid.uuid4().hex[:8]}"

        selected_strategies = [
            s for s in self.strategies
            if (strategy_name is None or s.name == strategy_name)
            and self._is_strategy_enabled(s.name)
        ]

        active_strategies_label = strategy_name or (
            selected_strategies[0].name if len(selected_strategies) == 1 else "multi_strategy"
        )

        risk_state = RiskState(
            account_size=capital,
            daily_realized_pnl=0.0,
            trades_today=0,
            open_positions=0,
            consecutive_losses=0,
            storage_available=True,
        )

        completed_trades: list[BacktestTrade] = []
        pending_orders: list[dict] = []  # orders generated at t to enter at t+1 open
        active_positions: list[dict] = []

        total_bars = len(candles)
        last_day = candles[0].timestamp.date()

        for idx in range(total_bars):
            current_bar = candles[idx]
            current_date = current_bar.timestamp.date()

            # Reset daily trade count and daily PnL on new calendar day
            if current_date != last_day:
                risk_state.daily_realized_pnl = 0.0
                risk_state.trades_today = 0
                last_day = current_date

            # -------------------------------------------------------------
            # 1. Execute Pending Orders (Scheduled at previous bar for next open)
            # -------------------------------------------------------------
            if self.execution_timing == "next_open" and pending_orders:
                orders_to_process = list(pending_orders)
                pending_orders.clear()
                for order in orders_to_process:
                    if risk_state.open_positions >= self.risk_config.max_concurrent_paper_trades:
                        continue
                    entry_price = current_bar.open_price
                    pos = self._create_active_position(
                        order=order,
                        entry_price=entry_price,
                        entry_time=current_bar.timestamp,
                        entry_bar_idx=idx,
                    )
                    active_positions.append(pos)
                    risk_state.open_positions = len(active_positions)
                    risk_state.trades_today += 1

            # -------------------------------------------------------------
            # 2. Update Active Positions & Check Intrabar Exits
            # -------------------------------------------------------------
            remaining_positions: list[dict] = []
            for pos in active_positions:
                # Track excursion (MAE / MFE)
                self._update_excursion(pos, current_bar)
                pos["holding_bars"] = idx - pos["entry_bar_idx"] + 1

                exit_info = self._check_intrabar_exit(pos, current_bar, is_final_bar=(idx == total_bars - 1))
                if exit_info is not None:
                    exit_price, exit_reason = exit_info
                    closed_trade = self._finalize_trade(
                        pos=pos,
                        exit_price=exit_price,
                        exit_time=current_bar.timestamp,
                        exit_reason=exit_reason,
                    )
                    completed_trades.append(closed_trade)
                    # Update risk state
                    risk_state.daily_realized_pnl += closed_trade.net_pnl
                    if closed_trade.net_pnl < 0:
                        risk_state.consecutive_losses += 1
                        risk_state.last_loss_at = current_bar.timestamp
                    elif closed_trade.net_pnl > 0:
                        risk_state.consecutive_losses = 0
                else:
                    remaining_positions.append(pos)

            active_positions = remaining_positions
            risk_state.open_positions = len(active_positions)

            # -------------------------------------------------------------
            # 3. Strategy Evaluation with STRICT No-Lookahead Slice (0..idx)
            # -------------------------------------------------------------
            if idx + 1 < self.min_lookback_bars:
                continue

            # Strict slice: only past & present up to idx
            historical_slice = list(candles[: idx + 1])
            technical = self.technical_analyzer.analyze(historical_slice)

            vix_val = vix_history.get(current_bar.timestamp) if vix_history else None
            breadth_val = breadth_history.get(current_bar.timestamp) if breadth_history else None
            opt_metrics = option_metrics.get(current_bar.timestamp) if option_metrics else None

            regime_assessment = self.regime_classifier.classify(
                technical,
                vix=vix_val,
                breadth=breadth_val,
            )

            context = StrategyContext(
                technical=technical,
                regime=regime_assessment,
                options=opt_metrics,
                breadth_score=regime_assessment.breadth_score,
            )

            extra = {"breadth": max(0.0, min(1.0, (regime_assessment.breadth_score + 1.0) / 2.0))}

            for strategy in selected_strategies:
                if not strategy.is_applicable(context):
                    continue
                candidate = strategy.generate_candidate(context)
                if candidate is None:
                    continue

                signal = self.scorer.score(
                    candidate,
                    data_quality=DataQuality.VALID,
                    extra_factors=extra,
                )
                if not signal.accepted:
                    continue

                # Size and assess risk using RiskEngine
                risk_assessment = self.risk_engine.assess(signal, risk_state)
                if not risk_assessment.approved or risk_assessment.position_size is None:
                    continue
                if risk_assessment.position_size.quantity <= 0:
                    continue

                order_payload = {
                    "signal": signal,
                    "candidate": candidate,
                    "assessment": risk_assessment,
                    "regime": regime_assessment.regime,
                }

                if self.execution_timing == "next_open":
                    # Queue for next bar open
                    pending_orders.append(order_payload)
                else:
                    # Execute on current close
                    if risk_state.open_positions < self.risk_config.max_concurrent_paper_trades:
                        pos = self._create_active_position(
                            order=order_payload,
                            entry_price=current_bar.close_price,
                            entry_time=current_bar.timestamp,
                            entry_bar_idx=idx,
                        )
                        active_positions.append(pos)
                        risk_state.open_positions = len(active_positions)
                        risk_state.trades_today += 1

        # Final metrics and performance calculation
        metrics, equity_curve = calculate_performance(
            completed_trades,
            initial_capital=capital,
            risk_free_rate=self.risk_free_rate,
            start_time=candles[0].timestamp,
        )

        final_cap = equity_curve[-1].net_equity if equity_curve else capital

        return BacktestResult(
            backtest_id=backtest_id,
            strategy_name=active_strategies_label,
            symbol=symbol,
            start_time=candles[0].timestamp,
            end_time=candles[-1].timestamp,
            initial_capital=capital,
            final_capital=round(final_cap, 4),
            metrics=metrics,
            trades=completed_trades,
            equity_curve=equity_curve,
            config_summary={
                "lot_size": self.lot_size,
                "point_value": self.point_value,
                "execution_timing": self.execution_timing,
                "pessimistic_intrabar_exit": self.pessimistic_intrabar_exit,
                "max_holding_bars": self.max_holding_bars,
            },
        )

    def _create_active_position(
        self,
        *,
        order: dict,
        entry_price: float,
        entry_time: datetime,
        entry_bar_idx: int,
    ) -> dict:
        candidate: StrategyCandidate = order["candidate"]
        assessment: RiskAssessment = order["assessment"]
        pos_size = assessment.position_size

        return {
            "trade_id": f"tr_{uuid.uuid4().hex[:8]}",
            "strategy_name": candidate.strategy_name,
            "symbol": candidate.symbol,
            "direction": candidate.direction,
            "entry_time": entry_time,
            "entry_price": entry_price,
            "entry_bar_idx": entry_bar_idx,
            "quantity": pos_size.quantity if pos_size else 1,
            "lot_size": pos_size.lot_size if pos_size else self.lot_size,
            "point_value": pos_size.point_value if pos_size else self.point_value,
            "stop_loss": candidate.stop_loss,
            "target_price": candidate.targets[0],
            "regime": order.get("regime"),
            "signal_score": order["signal"].score,
            "mae": 0.0,
            "mfe": 0.0,
            "holding_bars": 0,
        }

    def _update_excursion(self, pos: dict, bar: MarketCandle) -> None:
        entry = pos["entry_price"]
        direction = pos["direction"]
        if direction == Direction.LONG:
            fav = max(0.0, bar.high_price - entry)
            adv = max(0.0, entry - bar.low_price)
        else:
            fav = max(0.0, entry - bar.low_price)
            adv = max(0.0, bar.high_price - entry)

        if adv > pos["mae"]:
            pos["mae"] = adv
        if fav > pos["mfe"]:
            pos["mfe"] = fav

    def _check_intrabar_exit(
        self,
        pos: dict,
        bar: MarketCandle,
        *,
        is_final_bar: bool,
    ) -> tuple[float, ExitReason] | None:
        direction: Direction = pos["direction"]
        stop_loss = pos["stop_loss"]
        target = pos["target_price"]

        if direction == Direction.LONG:
            hit_stop = bar.low_price <= stop_loss
            hit_target = bar.high_price >= target

            if hit_stop and hit_target:
                if self.pessimistic_intrabar_exit:
                    return min(bar.open_price, stop_loss), ExitReason.STOP_LOSS
                return max(bar.open_price, target), ExitReason.TARGET

            if hit_stop:
                # Gap slippage: if opened below stop, exit at open
                exit_px = min(bar.open_price, stop_loss)
                return exit_px, ExitReason.STOP_LOSS

            if hit_target:
                # Gap profit: if opened above target, exit at open
                exit_px = max(bar.open_price, target)
                return exit_px, ExitReason.TARGET

        else:  # SHORT
            hit_stop = bar.high_price >= stop_loss
            hit_target = bar.low_price <= target

            if hit_stop and hit_target:
                if self.pessimistic_intrabar_exit:
                    return max(bar.open_price, stop_loss), ExitReason.STOP_LOSS
                return min(bar.open_price, target), ExitReason.TARGET

            if hit_stop:
                # Gap slippage: if opened above stop, exit at open
                exit_px = max(bar.open_price, stop_loss)
                return exit_px, ExitReason.STOP_LOSS

            if hit_target:
                # Gap profit: if opened below target, exit at open
                exit_px = min(bar.open_price, target)
                return exit_px, ExitReason.TARGET

        if self.max_holding_bars is not None and pos["holding_bars"] >= self.max_holding_bars:
            return bar.close_price, ExitReason.TIME_EXIT

        if is_final_bar:
            return bar.close_price, ExitReason.END_OF_DATA

        return None

    def _finalize_trade(
        self,
        *,
        pos: dict,
        exit_price: float,
        exit_time: datetime,
        exit_reason: ExitReason,
    ) -> BacktestTrade:
        entry_px = pos["entry_price"]
        direction: Direction = pos["direction"]
        quantity = pos["quantity"]
        lot_size = pos["lot_size"]
        point_value = pos["point_value"]
        units = quantity * lot_size

        if direction == Direction.LONG:
            gross_pnl = (exit_price - entry_px) * units * point_value
        else:
            gross_pnl = (entry_px - exit_price) * units * point_value

        cost = self.cost_model.round_trip(
            entry=entry_px,
            exit_price=exit_price,
            quantity=quantity,
            lot_size=lot_size,
            point_value=point_value,
            direction=direction,
        )

        net_pnl = gross_pnl - cost.total
        initial_risk_points = abs(entry_px - pos["stop_loss"])
        initial_risk_value = initial_risk_points * units * point_value
        r_multiple = (net_pnl / initial_risk_value) if initial_risk_value > 0 else 0.0

        return BacktestTrade(
            trade_id=pos["trade_id"],
            strategy_name=pos["strategy_name"],
            symbol=pos["symbol"],
            direction=direction,
            entry_time=pos["entry_time"],
            exit_time=exit_time,
            entry_price=round(entry_px, 4),
            exit_price=round(exit_price, 4),
            quantity=quantity,
            lot_size=lot_size,
            point_value=point_value,
            stop_loss=pos["stop_loss"],
            target_price=pos["target_price"],
            exit_reason=exit_reason,
            gross_pnl=round(gross_pnl, 4),
            net_pnl=round(net_pnl, 4),
            cost=cost,
            r_multiple=round(r_multiple, 4),
            holding_period_bars=pos["holding_bars"],
            regime=pos["regime"],
            mae=round(pos["mae"], 4),
            mfe=round(pos["mfe"], 4),
            signal_score=pos["signal_score"],
        )

    def _is_strategy_enabled(self, name: str) -> bool:
        flags = self.strategy_config.enabled
        if not flags:
            return True
        return flags.get(name, False)
