"""cTrader Open API configuration for Strategy 2.

Credentials are read only from environment variables. Never commit real values.
"""
import os

CTRADER_ENV = os.environ.get("CTRADER_ENV", "demo").lower()
CTRADER_CLIENT_ID = os.environ.get("CTRADER_CLIENT_ID", "")
CTRADER_CLIENT_SECRET = os.environ.get("CTRADER_CLIENT_SECRET", "")
CTRADER_ACCESS_TOKEN = os.environ.get("CTRADER_ACCESS_TOKEN", "")
CTRADER_REFRESH_TOKEN = os.environ.get("CTRADER_REFRESH_TOKEN", "")
CTRADER_ACCOUNT_ID = os.environ.get("CTRADER_ACCOUNT_ID", "")
CTRADER_SYMBOL = os.environ.get("CTRADER_SYMBOL", "XAUUSD")

def validate_ctrader_config(require_trading=False):
    missing = []
    for name, value in (
        ("CTRADER_CLIENT_ID", CTRADER_CLIENT_ID),
        ("CTRADER_CLIENT_SECRET", CTRADER_CLIENT_SECRET),
        ("CTRADER_ACCESS_TOKEN", CTRADER_ACCESS_TOKEN),
        ("CTRADER_ACCOUNT_ID", CTRADER_ACCOUNT_ID),
    ):
        if not value:
            missing.append(name)
    if missing:
        raise ValueError("Missing cTrader configuration: " + ", ".join(missing))
    if CTRADER_ENV not in ("demo", "live"):
        raise ValueError("CTRADER_ENV must be demo or live")
    if require_trading and os.environ.get("RAPID_LIVE_CONFIRM", "") != "YES":
        raise RuntimeError("Real execution requires RAPID_LIVE_CONFIRM=YES")
