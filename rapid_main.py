"""Standalone loop for Strategy 2: Rapid XAU/USD scalper.

Runs independently from main.py (WaveTrend). PAPER is the default execution
mode. It consumes completed short OANDA candles and maintains its own basket
state, log and kill switch.
"""
import logging
import os
import time

from oanda_client import OandaClient
from rapid_scalper import RapidState, RapidPosition, momentum_signal, can_stack, add_position, close_basket, basket_exit_reason

MODE = os.environ.get("RAPID_MODE", "paper").lower()
GRANULARITY = os.environ.get("RAPID_GRANULARITY", "S5")
POLL_SECONDS = float(os.environ.get("RAPID_POLL_SECONDS", "2"))
START_BALANCE = float(os.environ.get("RAPID_PAPER_BALANCE", "1000"))
UNITS = float(os.environ.get("RAPID_UNITS", "1"))
LOOKBACK = int(os.environ.get("RAPID_LOOKBACK", "3"))
MOMENTUM = float(os.environ.get("RAPID_MOMENTUM", "0.50"))
MAX_POSITIONS = int(os.environ.get("RAPID_MAX_POSITIONS", "5"))
SPACING = float(os.environ.get("RAPID_SPACING", "0.25"))
BASKET_TP = float(os.environ.get("RAPID_BASKET_TP", "5"))
BASKET_SL = float(os.environ.get("RAPID_BASKET_SL", "5"))
MAX_DRAWDOWN = float(os.environ.get("RAPID_MAX_DRAWDOWN", "0.10"))
SPREAD = float(os.environ.get("RAPID_SPREAD", "0.15"))
COOLDOWN = int(os.environ.get("RAPID_COOLDOWN_BARS", "1"))
DATA_DIR = os.environ.get("DATA_DIR", ".")
KILL_SWITCH = os.path.join(DATA_DIR, "rapid_killswitch.flag")

os.makedirs(DATA_DIR, exist_ok=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [RAPID] %(levelname)s %(message)s",
    handlers=[logging.FileHandler(os.path.join(DATA_DIR, "rapid_scalper.log")), logging.StreamHandler()])
log = logging.getLogger("rapid")

def reconcile_live_state(client, state):
    """Broker is source of truth after restart, reconnect, fill or close."""
    summary = client.get_account_summary()
    trades = client.get_open_trades("XAU_USD")
    state.balance = summary["balance"]
    state.positions = [RapidPosition(t["direction"], t["price"], abs(t["units"])) for t in trades]
    return summary, trades

def main():
    if MODE not in ("paper", "live"):
        raise ValueError("RAPID_MODE must be paper or live")
    client = OandaClient()
    if MODE == "live" and os.environ.get("RAPID_LIVE_CONFIRM", "") != "YES":
        raise RuntimeError("Set RAPID_LIVE_CONFIRM=YES to enable real order execution")
    initial_balance = client.get_account_balance() if MODE == "live" else START_BALANCE
    state = RapidState(balance=initial_balance, starting_balance=initial_balance)
    last_time = None
    bar_index = 0
    if MODE == "live":
        summary, trades = reconcile_live_state(client, state)
        log.info("LIVE broker sync | open_trades=%d NAV=%.2f margin_available=%.2f", len(trades), summary["nav"], summary["margin_available"])
    log.info("Strategy 2 started | mode=%s granularity=%s balance=%.2f", MODE, GRANULARITY, initial_balance)
    while True:
        try:
            df = client.get_candles("XAU_USD", GRANULARITY, count=max(50, LOOKBACK + 5))
            if df.empty:
                time.sleep(POLL_SECONDS); continue
            candle_time = df.iloc[-1]["time"]
            if candle_time == last_time:
                time.sleep(POLL_SECONDS); continue
            last_time = candle_time
            bar_index += 1
            price = float(df.iloc[-1]["close"])
            reason = basket_exit_reason(state, price, BASKET_TP, BASKET_SL, MAX_DRAWDOWN) if state.positions else None
            if reason:
                if MODE == "live":
                    client.close_position("XAU_USD")
                    summary, trades = reconcile_live_state(client, state)
                    log.info("%s LIVE basket close | account balance=%.2f", reason, state.balance)
                else:
                    pnl = close_basket(state, price, SPREAD)
                    log.info("%s PAPER close | pnl=%.2f balance=%.2f", reason, pnl, state.balance)
            if os.path.exists(KILL_SWITCH):
                log.warning("Rapid kill switch active")
                time.sleep(POLL_SECONDS); continue
            reference_balance = initial_balance
            if state.equity(price) <= reference_balance * (1 - MAX_DRAWDOWN):
                log.warning("Rapid equity stop reached; no new entries")
                time.sleep(POLL_SECONDS); continue
            signal = momentum_signal(df, len(df)-1, LOOKBACK, MOMENTUM)
            if signal and can_stack(state, signal, price, bar_index, MAX_POSITIONS, SPACING, COOLDOWN):
                if MODE == "live":
                    order_units = int(UNITS) if signal == "buy" else -int(UNITS)
                    if order_units == 0:
                        log.warning("RAPID_UNITS must be at least 1 for live OANDA orders")
                    else:
                        client.place_market_order("XAU_USD", order_units)
                        summary, trades = reconcile_live_state(client, state)
                        state.last_entry_index = bar_index
                        log.info("%s LIVE entry | requested_units=%d broker_open_trades=%d NAV=%.2f", signal.upper(), abs(order_units), len(trades), summary["nav"])
                else:
                    add_position(state, signal, price, UNITS, bar_index, SPREAD)
                    log.info("%s PAPER entry | price=%.2f units=%.2f stack=%d equity=%.2f", signal.upper(), price, UNITS, len(state.positions), state.equity(price))
        except Exception:
            log.exception("Rapid strategy loop error")
        time.sleep(POLL_SECONDS)

if __name__ == "__main__":
    main()
