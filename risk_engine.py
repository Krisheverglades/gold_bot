"""
Position sizing based on: risk_amount = balance * risk_pct
units = risk_amount / stop_distance_in_price

This ties position size directly to how far away the ATR-based stop is,
so every trade risks roughly the same dollar amount regardless of
current volatility.
"""

import pandas as pd
import config


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def compute_position_size(balance: float, stop_distance_price: float) -> int:
    """
    Returns whole units (OANDA XAU_USD allows fractional-ish sizing but we
    keep it as an int for simplicity — 1 unit of XAU_USD = 1 troy ounce equivalent
    exposure at most brokers, but confirm this on your OANDA account before trading).
    """
    if stop_distance_price <= 0:
        return 0
    risk_amount = balance * config.RISK_PCT_PER_TRADE
    units = risk_amount / stop_distance_price
    return int(units)


def compute_sl_tp(entry_price: float, atr_value: float, direction: str):
    """
    direction: 'buy' or 'sell'
    Returns (stop_loss_price, take_profit_price)
    """
    sl_distance = atr_value * config.ATR_SL_MULTIPLIER
    tp_distance = atr_value * config.ATR_TP_MULTIPLIER

    if direction == "buy":
        sl = entry_price - sl_distance
        tp = entry_price + tp_distance
    else:  # sell
        sl = entry_price + sl_distance
        tp = entry_price - tp_distance

    return sl, tp, sl_distance
