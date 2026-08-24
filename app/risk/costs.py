"""Configurable Indian transaction-cost model.

Percentages in :class:`~app.config.settings.TransactionCostConfig` are percent
of notional per side unless noted. Stamp duty is applied on the buy side only.
GST is applied to (brokerage + exchange + SEBI) per side.

This model is a research approximation. It does not replace a broker contract
note and must not be presented as an official tax calculation.
"""

from __future__ import annotations

from app.config.settings import TransactionCostConfig
from app.models.enums import Direction
from app.models.risk import CostBreakdown


class TransactionCostModel:
    """Deterministic round-trip cost calculator."""

    def __init__(self, config: TransactionCostConfig) -> None:
        self.config = config

    def round_trip(
        self,
        entry: float,
        exit_price: float,
        quantity: int,
        *,
        lot_size: int = 1,
        point_value: float = 1.0,
        direction: Direction = Direction.LONG,
    ) -> CostBreakdown:
        units = max(0, quantity) * max(1, lot_size)
        notional_entry = abs(entry) * units * point_value
        notional_exit = abs(exit_price) * units * point_value
        if direction == Direction.LONG:
            buy_notional, sell_notional = notional_entry, notional_exit
        else:
            buy_notional, sell_notional = notional_exit, notional_entry

        buy = self._side(buy_notional, is_buy=True)
        sell = self._side(sell_notional, is_buy=False)
        total = {key: buy[key] + sell[key] for key in buy}
        formula = (
            "per_side: brokerage=n*brokerage% ; exchange=n*exchange% ; "
            "sebi=n*sebi% ; gst=(brokerage+exchange+sebi)*gst% ; "
            "stt=n*stt_buy%|stt_sell% ; stamp=n*stamp% on buy only ; "
            "slippage=n*slippage% ; spread=n*spread% ; round_trip=buy+sell"
        )
        return CostBreakdown(
            notional_entry=notional_entry,
            notional_exit=notional_exit,
            brokerage=total["brokerage"],
            stt=total["stt"],
            gst=total["gst"],
            exchange_charges=total["exchange"],
            sebi_charges=total["sebi"],
            stamp_duty=total["stamp"],
            slippage=total["slippage"],
            spread=total["spread"],
            total=sum(total.values()),
            formula=formula,
        )

    def _side(self, notional: float, *, is_buy: bool) -> dict[str, float]:
        cfg = self.config
        brokerage = notional * cfg.brokerage / 100.0
        exchange = notional * cfg.exchange_charges_pct / 100.0
        sebi = notional * cfg.sebi_charges_pct / 100.0
        gst = (brokerage + exchange + sebi) * cfg.gst_pct / 100.0
        stamp = (notional * cfg.stamp_duty_pct / 100.0) if is_buy else 0.0
        stt_pct = cfg.stt_buy_pct if is_buy else cfg.stt_sell_pct
        stt = notional * stt_pct / 100.0
        slippage = notional * cfg.slippage_pct / 100.0
        spread = notional * cfg.bid_ask_spread_pct / 100.0
        return {
            "brokerage": brokerage,
            "exchange": exchange,
            "sebi": sebi,
            "gst": gst,
            "stamp": stamp,
            "stt": stt,
            "slippage": slippage,
            "spread": spread,
        }
