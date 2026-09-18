"""Broker-independent rapid XAUUSD decision engine."""
from collections import deque
from dataclasses import dataclass
from time import monotonic
import ctrader_config as cfg


@dataclass(frozen=True)
class Tick:
    bid: float
    ask: float

    @property
    def mid(self):
        return (self.bid + self.ask) / 2.0

    @property
    def spread(self):
        return self.ask - self.bid


class RapidScalper:
    def __init__(self):
        self.prices = deque(maxlen=max(2, cfg.MOMENTUM_WINDOW))
        self.last_entry_price = None
        self.last_entry_time = 0.0

    def on_tick(self, tick: Tick, open_positions: int):
        """Return buy/sell when momentum, spread and stacking rules allow it."""
        self.prices.append(tick.mid)
        if tick.spread > cfg.MAX_SPREAD or open_positions >= cfg.MAX_POSITIONS:
            return None
        if len(self.prices) < self.prices.maxlen:
            return None
        if monotonic() - self.last_entry_time < cfg.COOLDOWN_SECONDS:
            return None

        move = self.prices[-1] - self.prices[0]
        if abs(move) < cfg.MOMENTUM_TRIGGER:
            return None
        if self.last_entry_price is not None:
            if abs(tick.mid - self.last_entry_price) < cfg.ENTRY_SPACING:
                return None

        side = "buy" if move > 0 else "sell"
        self.last_entry_price = tick.mid
        self.last_entry_time = monotonic()
        return side

    @staticmethod
    def basket_action(floating_pnl: float, daily_realized_pnl: float):
        if daily_realized_pnl <= -abs(cfg.MAX_DAILY_LOSS):
            return "halt"
        if floating_pnl >= abs(cfg.BASKET_TP):
            return "close_all"
        if floating_pnl <= -abs(cfg.BASKET_SL):
            return "close_all"
        return None
