"""
Backtest the WaveTrend crossover strategy against historical OANDA data.

Usage (pulling directly from OANDA):
    OANDA_API_TOKEN=... OANDA_ACCOUNT_ID=... python3 backtest.py \
        --from 2022-01-01 --to 2024-01-01 --granularity H1

Or against a local CSV (columns: time,open,high,low,close):
    python3 backtest.py --csv my_gold_data.csv

IMPORTANT — read before trusting any results:
- Signals are computed on a CLOSED candle, but the simulated entry happens
  at the NEXT candle's open (you can't trade the close of a candle that
  just closed in real life — there's always some lag). This avoids
  look-ahead bias but is still an approximation of real execution.
- A basic spread/slippage cost is subtracted on every entry and exit.
- Past performance on historical data, especially over a single continuous
  period, is not a reliable predictor of live results. Watch out for:
    * Overfitting the risk parameters to this specific dataset
    * Regime dependency (a strategy that works in a trend can fail
      in a chop, and vice versa)
    * The backtest making assumptions about fills/slippage that live
      trading won't match exactly
"""

import argparse
import numpy as np
import pandas as pd

import config
from wavetrend_signal import compute_wavetrend
from risk_engine import compute_atr, compute_position_size, compute_sl_tp

SPREAD_COST_PRICE = 0.30  # approx round-trip spread cost in price terms for XAU_USD, adjust to your broker


def load_from_oanda(granularity: str, date_from: str, date_to: str) -> pd.DataFrame:
    from oanda_client import OandaClient
    client = OandaClient()
    from_iso = f"{date_from}T00:00:00Z"
    to_iso = f"{date_to}T00:00:00Z"
    return client.get_historical_candles(config.INSTRUMENT, granularity, from_iso, to_iso)


def load_from_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {"time", "open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")
    return df


def simulate(df: pd.DataFrame, starting_balance: float = 10000.0) -> dict:
    df = compute_wavetrend(df, n1=config.WT_N1, n2=config.WT_N2, sma_len=config.WT_SMA_LEN)
    df["atr"] = compute_atr(df, config.ATR_PERIOD)

    balance = starting_balance
    equity_curve = [balance]
    trades = []

    position = None  # dict with direction, entry_price, units, sl, tp, entry_idx

    for i in range(1, len(df) - 1):  # -1 because entry happens on i+1's open
        row = df.iloc[i]
        next_row = df.iloc[i + 1]

        # --- check exit on open position first (did SL/TP get hit intra-bar?) ---
        if position is not None:
            hit_sl = (row["low"] <= position["sl"]) if position["direction"] == "buy" else (row["high"] >= position["sl"])
            hit_tp = (row["high"] >= position["tp"]) if position["direction"] == "buy" else (row["low"] <= position["tp"])

            exit_price = None
            if hit_sl and hit_tp:
                # ambiguous which hit first intra-bar; conservatively assume SL
                exit_price = position["sl"]
            elif hit_sl:
                exit_price = position["sl"]
            elif hit_tp:
                exit_price = position["tp"]

            if exit_price is not None:
                pnl = (exit_price - position["entry_price"]) * position["units"]
                pnl -= SPREAD_COST_PRICE * abs(position["units"])  # exit cost
                balance += pnl
                trades.append({
                    "direction": position["direction"], "entry": position["entry_price"],
                    "exit": exit_price, "pnl": pnl, "exit_reason": "SL" if exit_price == position["sl"] else "TP",
                })
                position = None

        # --- check for new signal to enter (or flip) ---
        if row["buy_signal"] or row["sell_signal"]:
            direction = "buy" if row["buy_signal"] else "sell"

            # close existing opposite position at next open if flipping
            if position is not None and position["direction"] != direction:
                exit_price = next_row["open"]
                pnl = (exit_price - position["entry_price"]) * position["units"]
                pnl -= SPREAD_COST_PRICE * abs(position["units"])
                balance += pnl
                trades.append({
                    "direction": position["direction"], "entry": position["entry_price"],
                    "exit": exit_price, "pnl": pnl, "exit_reason": "FLIP",
                })
                position = None

            if position is None and not pd.isna(row["atr"]) and row["atr"] > 0:
                entry_price = next_row["open"]
                sl, tp, sl_distance = compute_sl_tp(entry_price, row["atr"], direction)
                units = compute_position_size(balance, sl_distance)
                if units > 0:
                    entry_cost = SPREAD_COST_PRICE * units
                    balance -= entry_cost
                    position = {
                        "direction": direction,
                        "entry_price": entry_price,
                        "units": units if direction == "buy" else -units,
                        "sl": sl, "tp": tp,
                    }

        equity_curve.append(balance)

    # close any position still open at the end, mark-to-market
    if position is not None:
        exit_price = df.iloc[-1]["close"]
        pnl = (exit_price - position["entry_price"]) * position["units"]
        balance += pnl
        trades.append({
            "direction": position["direction"], "entry": position["entry_price"],
            "exit": exit_price, "pnl": pnl, "exit_reason": "END_OF_DATA",
        })

    return {
        "final_balance": balance,
        "starting_balance": starting_balance,
        "trades": trades,
        "equity_curve": equity_curve,
    }


def print_report(result: dict):
    trades = result["trades"]
    starting = result["starting_balance"]
    final = result["final_balance"]
    equity = np.array(result["equity_curve"])

    n_trades = len(trades)
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    win_rate = len(wins) / n_trades if n_trades else 0
    gross_profit = sum(t["pnl"] for t in wins)
    gross_loss = abs(sum(t["pnl"] for t in losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    running_max = np.maximum.accumulate(equity)
    drawdown = (equity - running_max) / running_max
    max_drawdown = drawdown.min()

    total_return_pct = (final - starting) / starting * 100

    print("=" * 50)
    print("BACKTEST RESULTS")
    print("=" * 50)
    print(f"Starting balance:   ${starting:,.2f}")
    print(f"Final balance:      ${final:,.2f}")
    print(f"Total return:       {total_return_pct:+.2f}%")
    print(f"Number of trades:   {n_trades}")
    print(f"Win rate:           {win_rate:.1%}")
    print(f"Profit factor:      {profit_factor:.2f}")
    print(f"Max drawdown:       {max_drawdown:.2%}")
    print(f"Avg win:            ${(gross_profit / len(wins)):,.2f}" if wins else "Avg win: n/a")
    print(f"Avg loss:           ${(gross_loss / len(losses)):,.2f}" if losses else "Avg loss: n/a")
    print("=" * 50)

    if n_trades < 30:
        print("\n⚠ Fewer than 30 trades — not enough sample size to draw real conclusions.")
    if max_drawdown < -0.3:
        print("\n⚠ Max drawdown exceeds 30% — this would be extremely painful to hold through live.")


def plot_equity_curve(result: dict, out_path: str = "equity_curve.png"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.figure(figsize=(10, 5))
    plt.plot(result["equity_curve"])
    plt.title("Equity Curve")
    plt.xlabel("Bar #")
    plt.ylabel("Account Balance ($)")
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_path, dpi=120)
    print(f"\nEquity curve saved to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", help="Path to local CSV with time,open,high,low,close columns")
    parser.add_argument("--from", dest="date_from", help="Start date YYYY-MM-DD (OANDA mode)")
    parser.add_argument("--to", dest="date_to", help="End date YYYY-MM-DD (OANDA mode)")
    parser.add_argument("--granularity", default="H1")
    parser.add_argument("--balance", type=float, default=10000.0)
    args = parser.parse_args()

    if args.csv:
        data = load_from_csv(args.csv)
    elif args.date_from and args.date_to:
        data = load_from_oanda(args.granularity, args.date_from, args.date_to)
    else:
        parser.error("Provide either --csv or both --from and --to")

    print(f"Loaded {len(data)} candles")
    result = simulate(data, starting_balance=args.balance)
    print_report(result)
    plot_equity_curve(result)
