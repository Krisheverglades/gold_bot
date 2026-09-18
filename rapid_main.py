"""Standalone loop for Strategy 2: Rapid XAU/USD scalper.

Runs independently from main.py (WaveTrend). PAPER is the default execution
mode. It consumes completed short OANDA candles and maintains its own basket
state, log and kill switch.
"""
import logging
import os
import time

from oanda_client import OandaClient
from rapid_scalper import RapidState, momentum_signal, can_stack, add_position, close_basket, basket_exit_reason

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

def main():
    if MODE != "paper":
        raise RuntimeError("Rapid strategy live execution is locked. Validate paper/backtest results first.")
    client = OandaClient()
    state = RapidState(balance=START_BALANCE, starting_balance=START_BALANCE)
    last_time = None
    bar_index = 0
    log.info("Strategy 2 started | mode=%s granularity=%s balance=%.2f", MODE, GRANULARITY, START_BALANCE)
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
                pnl = close_basket(state, price, SPREAD)
                log.info("%s close | pnl=%.2f balance=%.2f", reason, pnl, state.balance)
            if os.path.exists(KILL_SWITCH):
                log.warning("Rapid kill switch active")
                time.sleep(POLL_SECONDS); continue
            if state.equity(price) <= START_BALANCE * (1 - MAX_DRAWDOWN):
                log.warning("Rapid equity stop reached; no new entries")
                time.sleep(POLL_SECONDS); continue
            signal = momentum_signal(df, len(df)-1, LOOKBACK, MOMENTUM)
            if signal and can_stack(state, signal, price, bar_index, MAX_POSITIONS, SPACING, COOLDOWN):
                add_position(state, signal, price, UNITS, bar_index, SPREAD)
                log.info("%s paper entry | price=%.2f units=%.2f stack=%d equity=%.2f",
                         signal.upper(), price, UNITS, len(state.positions), state.equity(price))
        except Exception:
            log.exception("Rapid strategy loop error")
        time.sleep(POLL_SECONDS)

if __name__ == "__main__":
    main()
