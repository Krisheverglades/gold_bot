"""cTrader entry point for the rapid XAUUSD strategy.

Milestone 1 authenticates against cTrader and keeps real order execution locked
while broker-specific symbol and volume metadata are validated.
"""
import logging
import os
import ctrader_config as cfg
from ctrader_client import CTraderClient

os.makedirs(cfg.DATA_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [RAPID] %(levelname)s %(message)s",
    handlers=[logging.FileHandler(cfg.LOG_FILE), logging.StreamHandler()],
)
log = logging.getLogger("rapid")


def ready(client):
    log.info(
        "cTrader authenticated | account=%s env=%s symbol=%s paper=%s",
        client.account_id, cfg.CTRADER_ENV, cfg.SYMBOL_NAME, cfg.PAPER_TRADING,
    )
    if not cfg.PAPER_TRADING:
        log.warning(
            "Real execution remains locked until cTrader symbolId and "
            "min/max/step volume metadata are validated."
        )


if __name__ == "__main__":
    CTraderClient(on_ready=ready).start()
