"""Backtest the isolated rapid XAU/USD momentum/stacking strategy."""
import argparse
import pandas as pd
from rapid_scalper import RapidState, momentum_signal, can_stack, add_position, close_basket, basket_exit_reason

def simulate(df, starting_balance=1000.0, units=1.0, lookback=3, momentum=0.50,
             max_positions=5, spacing=0.25, basket_tp=5.0, basket_sl=5.0,
             max_drawdown=0.10, spread=0.15, cooldown=1):
    state = RapidState(balance=starting_balance, starting_balance=starting_balance)
    equity_curve, exits = [], []
    for i in range(len(df)):
        price = float(df.iloc[i]["close"])
        reason = basket_exit_reason(state, price, basket_tp, basket_sl, max_drawdown) if state.positions else None
        if reason:
            pnl = close_basket(state, price, spread)
            exits.append({"time": df.iloc[i]["time"], "reason": reason, "pnl": pnl})
        if state.equity(price) <= starting_balance * (1.0 - max_drawdown):
            equity_curve.append(state.equity(price))
            continue
        signal = momentum_signal(df, i, lookback, momentum)
        if signal and can_stack(state, signal, price, i, max_positions, spacing, cooldown):
            add_position(state, signal, price, units, i, spread)
        equity_curve.append(state.equity(price))
    if state.positions:
        price = float(df.iloc[-1]["close"])
        pnl = close_basket(state, price, spread)
        exits.append({"time": df.iloc[-1]["time"], "reason": "END_OF_DATA", "pnl": pnl})
    return state, equity_curve, exits

def report(state, equity_curve, exits):
    peak = equity_curve[0] if equity_curve else state.starting_balance
    max_dd = 0.0
    for eq in equity_curve:
        peak = max(peak, eq)
        if peak > 0:
            max_dd = min(max_dd, (eq - peak) / peak)
    win_rate = state.wins / state.trades if state.trades else 0.0
    print("=" * 52)
    print("RAPID SCALPER BACKTEST")
    print("=" * 52)
    print("Start balance:  $%0.2f" % state.starting_balance)
    print("Final balance:  $%0.2f" % state.balance)
    print("Realized P/L:   $%0.2f" % state.realized_pnl)
    print("Baskets closed: %d" % state.trades)
    print("Win rate:       %0.1f%%" % (win_rate * 100))
    print("Max drawdown:   %0.2f%%" % (max_dd * 100))
    reasons = {}
    for e in exits:
        reasons[e["reason"]] = reasons.get(e["reason"], 0) + 1
    print("Exit reasons:", reasons)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--csv", required=True)
    p.add_argument("--balance", type=float, default=1000.0)
    p.add_argument("--units", type=float, default=1.0)
    p.add_argument("--lookback", type=int, default=3)
    p.add_argument("--momentum", type=float, default=0.50)
    p.add_argument("--max-positions", type=int, default=5)
    p.add_argument("--spacing", type=float, default=0.25)
    p.add_argument("--basket-tp", type=float, default=5.0)
    p.add_argument("--basket-sl", type=float, default=5.0)
    p.add_argument("--max-drawdown", type=float, default=0.10)
    p.add_argument("--spread", type=float, default=0.15)
    p.add_argument("--cooldown", type=int, default=1)
    a = p.parse_args()
    df = pd.read_csv(a.csv)
    required = {"time", "open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError("CSV missing columns: %s" % missing)
    state, curve, exits = simulate(df, a.balance, a.units, a.lookback, a.momentum,
        a.max_positions, a.spacing, a.basket_tp, a.basket_sl, a.max_drawdown, a.spread, a.cooldown)
    report(state, curve, exits)
