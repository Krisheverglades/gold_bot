"""Rapid XAU/USD scalper signal and paper-trading engine.

This strategy is deliberately isolated from the existing H1/H4 WaveTrend bot.
It uses short completed candles, detects directional momentum, allows controlled
same-direction stacking, and exits the whole basket on profit/loss/equity limits.

Paper mode is the default. Live execution is intentionally not implemented here:
the current OANDA position model does not reproduce MetaTrader-style independent
simultaneous long/short tickets.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class RapidPosition:
    direction: str
    entry: float
    units: float


@dataclass
class RapidState:
    balance: float
    starting_balance: float
    positions: List[RapidPosition] = field(default_factory=list)
    realized_pnl: float = 0.0
    trades: int = 0
    wins: int = 0
    losses: int = 0
    last_entry_index: int = -10_000

    def floating_pnl(self, price: float) -> float:
        total = 0.0
        for p in self.positions:
            sign = 1.0 if p.direction == "buy" else -1.0
            total += (price - p.entry) * p.units * sign
        return total

    def equity(self, price: float) -> float:
        return self.balance + self.floating_pnl(price)


def momentum_signal(df, index: int, lookback: int, threshold: float) -> Optional[str]:
    """Return buy/sell when the short-term price move exceeds threshold."""
    if index < lookback:
        return None
    now = float(df.iloc[index]["close"])
    old = float(df.iloc[index - lookback]["close"])
    move = now - old
    if move >= threshold:
        return "buy"
    if move <= -threshold:
        return "sell"
    return None


def can_stack(state: RapidState, direction: str, price: float, index: int,
              max_positions: int, spacing: float, cooldown_bars: int) -> bool:
    if len(state.positions) >= max_positions:
        return False
    if index - state.last_entry_index < cooldown_bars:
        return False
    same_side = [p for p in state.positions if p.direction == direction]
    opposite = [p for p in state.positions if p.direction != direction]
    if opposite:
        return False
    if not same_side:
        return True
    return abs(price - same_side[-1].entry) >= spacing


def add_position(state: RapidState, direction: str, price: float, units: float,
                 index: int, spread_cost: float = 0.0) -> None:
    state.positions.append(RapidPosition(direction, price, units))
    state.balance -= abs(units) * spread_cost
    state.last_entry_index = index


def close_basket(state: RapidState, price: float, spread_cost: float = 0.0) -> float:
    pnl = state.floating_pnl(price)
    pnl -= sum(abs(p.units) * spread_cost for p in state.positions)
    state.balance += pnl
    state.realized_pnl += pnl
    state.trades += 1
    if pnl > 0:
        state.wins += 1
    else:
        state.losses += 1
    state.positions.clear()
    return pnl


def basket_exit_reason(state: RapidState, price: float, profit_target: float,
                       loss_limit: float, max_drawdown_pct: float) -> Optional[str]:
    pnl = state.floating_pnl(price)
    if pnl >= profit_target:
        return "BASKET_TP"
    if pnl <= -loss_limit:
        return "BASKET_SL"
    equity = state.equity(price)
    if state.starting_balance > 0:
        dd = (state.starting_balance - equity) / state.starting_balance
        if dd >= max_drawdown_pct:
            return "EQUITY_STOP"
    return None
