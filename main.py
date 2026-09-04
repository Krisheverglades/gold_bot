"""
Main loop: polls OANDA for new closed candles, computes the WaveTrend
signal, and executes trades with ATR-based sizing and stop-loss/take-profit.

Run with env vars set:
    OANDA_API_TOKEN=... OANDA_ACCOUNT_ID=... OANDA_ENV=practice GRANULARITY=H1 python3 main.py
"""

import time
import os
import logging
import pandas as pd
from datetime import datetime, timezone

import config
from oanda_client import OandaClient
from wavetrend_signal import compute_wavetrend, get_latest_signal
from risk_engine import compute_atr, compute_position_size, compute_sl_tp

os.makedirs(config.DATA_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(config.LOG_FILE),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


def kill_switch_active() -> bool:
    return os.path.exists(config.KILL_SWITCH_FILE)


def check_daily_loss_limit(client: OandaClient, day_start_balance: float) -> bool:
    """Returns True if the daily loss limit has been breached."""
    current_balance = client.get_account_balance()
    loss_pct = (day_start_balance - current_balance) / day_start_balance
    if loss_pct >= config.MAX_DAILY_LOSS_PCT:
        log.warning(f"Daily loss limit breached: {loss_pct:.2%} >= {config.MAX_DAILY_LOSS_PCT:.2%}")
        return True
    return False


def run_once(client: OandaClient, last_candle_time: str):
    """One iteration: fetch candles, check for new signal, act on it. Returns latest candle time."""
    df = client.get_candles(config.INSTRUMENT, config.GRANULARITY, count=200)
    if df.empty:
        log.warning("No candle data returned")
        return last_candle_time

    latest_time = df.iloc[-1]["time"]
    if latest_time == last_candle_time:
        return last_candle_time  # no new closed candle yet

    df = compute_wavetrend(df, n1=config.WT_N1, n2=config.WT_N2, sma_len=config.WT_SMA_LEN)
    df["atr"] = compute_atr(df, config.ATR_PERIOD)
    signal = get_latest_signal(df)

    if signal is None:
        log.info(f"New candle at {latest_time}, no signal")
        return latest_time

    log.info(f"Signal detected: {signal.upper()} at candle {latest_time}")

    if kill_switch_active():
        log.warning("Kill switch active — skipping trade execution")
        return latest_time

    entry_price = df.iloc[-1]["close"]
    atr_value = df.iloc[-1]["atr"]

    if pd.isna(atr_value) or atr_value <= 0:
        log.warning("ATR not available yet, skipping trade")
        return latest_time

    sl_price, tp_price, sl_distance = compute_sl_tp(entry_price, atr_value, signal)
    balance = client.get_account_balance()
    units = compute_position_size(balance, sl_distance)

    if units <= 0:
        log.warning("Computed position size is 0, skipping trade")
        return latest_time

    # Close any existing opposite position first
    existing = client.get_open_position(config.INSTRUMENT)
    if existing is not None:
        currently_long = existing["units"] > 0
        signal_is_buy = signal == "buy"
        if currently_long != signal_is_buy:
            log.info("Closing existing opposite position before entering new one")
            client.close_position(config.INSTRUMENT)

    order_units = units if signal == "buy" else -units
    log.info(
        f"Placing {signal.upper()} order: {abs(order_units)} units, "
        f"entry~{entry_price:.2f}, SL={sl_price:.2f}, TP={tp_price:.2f}"
    )
    result = client.place_market_order(
        config.INSTRUMENT, order_units, stop_loss_price=sl_price, take_profit_price=tp_price
    )
    log.info(f"Order result: {result.get('orderFillTransaction', {}).get('id', 'see log')}")

    return latest_time


def main():
    client = OandaClient()
    log.info(f"Starting bot | instrument={config.INSTRUMENT} granularity={config.GRANULARITY} "
              f"env={config.OANDA_ENV} risk={config.RISK_PCT_PER_TRADE:.1%}")

    if config.OANDA_ENV == "live":
        log.warning("Running against LIVE account. Real money is at risk.")

    day_start_balance = client.get_account_balance()
    current_day = datetime.now(timezone.utc).date()
    last_candle_time = None
    trading_halted_for_day = False

    while True:
        try:
            today = datetime.now(timezone.utc).date()
            if today != current_day:
                current_day = today
                day_start_balance = client.get_account_balance()
                trading_halted_for_day = False
                log.info(f"New trading day, balance reset reference: {day_start_balance:.2f}")

            if not trading_halted_for_day and check_daily_loss_limit(client, day_start_balance):
                trading_halted_for_day = True
                log.warning("Trading halted for the rest of the day due to loss limit")

            if not trading_halted_for_day and not kill_switch_active():
                last_candle_time = run_once(client, last_candle_time)
            else:
                # still track candle time so we don't miss the resume point
                pass

        except Exception as e:
            log.exception(f"Error in main loop: {e}")

        time.sleep(config.POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
