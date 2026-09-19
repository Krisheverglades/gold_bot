"""Configuration for the cTrader rapid XAUUSD bot."""
import os
from dotenv import load_dotenv

# Load VPS/local secrets automatically. Existing exported variables keep priority.
load_dotenv(override=False)

CTRADER_CLIENT_ID = os.environ.get("CTRADER_CLIENT_ID", "")
CTRADER_CLIENT_SECRET = os.environ.get("CTRADER_CLIENT_SECRET", "")
CTRADER_ACCESS_TOKEN = os.environ.get("CTRADER_ACCESS_TOKEN", "")
CTRADER_ACCOUNT_ID = int(os.environ.get("CTRADER_ACCOUNT_ID", "0"))
CTRADER_ENV = os.environ.get("CTRADER_ENV", "demo").lower()
SYMBOL_NAME = os.environ.get("CTRADER_SYMBOL", "XAUUSD")
PAPER_TRADING = os.environ.get("PAPER_TRADING", "true").lower() == "true"

MAX_POSITIONS = int(os.environ.get("MAX_POSITIONS", "6"))
MAX_SPREAD = float(os.environ.get("MAX_SPREAD", "0.50"))
MOMENTUM_WINDOW = int(os.environ.get("MOMENTUM_WINDOW", "8"))
MOMENTUM_TRIGGER = float(os.environ.get("MOMENTUM_TRIGGER", "0.35"))
ENTRY_SPACING = float(os.environ.get("ENTRY_SPACING", "0.25"))
BASKET_TP = float(os.environ.get("BASKET_TP", "10.0"))
BASKET_SL = float(os.environ.get("BASKET_SL", "15.0"))
MAX_DAILY_LOSS = float(os.environ.get("MAX_DAILY_LOSS", "30.0"))
COOLDOWN_SECONDS = float(os.environ.get("COOLDOWN_SECONDS", "1.0"))

DATA_DIR = os.environ.get("DATA_DIR", "./data")
KILL_SWITCH_FILE = os.path.join(DATA_DIR, "killswitch.flag")
LOG_FILE = os.path.join(DATA_DIR, "rapid_scalper.log")
