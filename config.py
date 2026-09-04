"""
Central config. Secrets come from environment variables — never hardcode
your API token here.
"""

import os

# --- OANDA connection ---
OANDA_API_TOKEN = os.environ.get("OANDA_API_TOKEN", "")
OANDA_ACCOUNT_ID = os.environ.get("OANDA_ACCOUNT_ID", "")
OANDA_ENV = os.environ.get("OANDA_ENV", "practice")  # "practice" or "live"

# --- Instrument & timeframe ---
INSTRUMENT = "XAU_USD"
# OANDA granularity codes: H1 = 1 hour, H4 = 4 hour
GRANULARITY = os.environ.get("GRANULARITY", "H1")

# --- WaveTrend signal params (from the Pine Script) ---
WT_N1 = 14
WT_N2 = 21
WT_SMA_LEN = 4

# --- Risk management ---
RISK_PCT_PER_TRADE = 0.01      # 1% of account balance risked per trade
ATR_PERIOD = 14
ATR_SL_MULTIPLIER = 1.5        # stop-loss distance = ATR * this
ATR_TP_MULTIPLIER = 3.0        # take-profit distance = ATR * this (2:1 reward:risk)

MAX_DAILY_LOSS_PCT = 0.03      # kill-switch: stop trading if daily loss exceeds 3% of balance
POLL_INTERVAL_SECONDS = 60     # how often the main loop checks for a new closed candle

# --- Safety ---
KILL_SWITCH_FILE = "killswitch.flag"  # if this file exists, bot halts all new trades
