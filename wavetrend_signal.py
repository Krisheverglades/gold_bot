"""
WaveTrend crossover signal engine.
Ported from the Pine Script's core buy/sell logic (WaveTrend oscillator,
LazyBear-style), stripped of all charting/visual elements.

Given a DataFrame of OHLC candles, this computes wt1/wt2 and returns
buy/sell signals with the same "no duplicate same-direction signal"
state logic as the original script.
"""

import pandas as pd
import numpy as np


def compute_wavetrend(df: pd.DataFrame, n1: int = 14, n2: int = 21, sma_len: int = 4) -> pd.DataFrame:
    """
    df must have columns: 'high', 'low', 'close'
    Returns df with added columns: wt1, wt2, buy_signal, sell_signal
    """
    df = df.copy()

    # hlc3 source, same as Pine's ap = hlc3
    ap = (df["high"] + df["low"] + df["close"]) / 3.0

    esa = ap.ewm(span=n1, adjust=False).mean()
    d = (ap - esa).abs().ewm(span=n1, adjust=False).mean()

    # avoid div by zero when d is ~0 (flat price)
    ci = (ap - esa) / (0.015 * d.replace(0, np.nan))
    ci = ci.fillna(0)

    tci = ci.ewm(span=n2, adjust=False).mean()
    wt1 = tci
    wt2 = wt1.rolling(sma_len).mean()

    df["wt1"] = wt1
    df["wt2"] = wt2

    # crossover / crossunder detection
    prev_diff = (wt1 - wt2).shift(1)
    curr_diff = wt1 - wt2
    crossover = (prev_diff <= 0) & (curr_diff > 0)
    crossunder = (prev_diff >= 0) & (curr_diff < 0)

    # replicate the buy/sell state-flag logic from Pine:
    # buySignal = not sell and crossover(wt1, wt2)
    # sellSignal = not buy and crossunder(wt1, wt2)
    # state flips: buySignal -> sell=True, buy=False
    #              sellSignal -> sell=False, buy=True
    buy_signals = []
    sell_signals = []
    sell_state = False  # "sell" flag from Pine (true after a buy signal fired)
    buy_state = False    # "buy" flag from Pine (true after a sell signal fired)

    for i in range(len(df)):
        co = bool(crossover.iloc[i]) if not pd.isna(crossover.iloc[i]) else False
        cu = bool(crossunder.iloc[i]) if not pd.isna(crossunder.iloc[i]) else False

        buy_sig = (not sell_state) and co
        sell_sig = (not buy_state) and cu

        if buy_sig:
            sell_state = True
            buy_state = False
        if sell_sig:
            sell_state = False
            buy_state = True

        buy_signals.append(buy_sig)
        sell_signals.append(sell_sig)

    df["buy_signal"] = buy_signals
    df["sell_signal"] = sell_signals

    return df


def get_latest_signal(df: pd.DataFrame) -> str | None:
    """
    Call this after compute_wavetrend(). Returns 'buy', 'sell', or None
    based on the most recently closed candle (last row of df).
    """
    if len(df) == 0:
        return None
    last = df.iloc[-1]
    if last["buy_signal"]:
        return "buy"
    if last["sell_signal"]:
        return "sell"
    return None


if __name__ == "__main__":
    # Quick smoke test with synthetic data
    import numpy as np
    rng = np.random.default_rng(42)
    n = 300
    price = 2000 + np.cumsum(rng.normal(0, 3, n))
    test_df = pd.DataFrame({
        "high": price + rng.uniform(0, 2, n),
        "low": price - rng.uniform(0, 2, n),
        "close": price,
    })
    result = compute_wavetrend(test_df)
    signals = result[result["buy_signal"] | result["sell_signal"]]
    print(f"Generated {len(signals)} signals out of {n} bars")
    print(signals[["close", "wt1", "wt2", "buy_signal", "sell_signal"]].tail(10))
