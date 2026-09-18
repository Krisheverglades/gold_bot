"""cTrader rapid XAUUSD paper-trading runner."""
import logging, os
import ctrader_config as cfg
from ctrader_client import CTraderClient
from rapid_scalper import RapidScalper, Tick

os.makedirs(cfg.DATA_DIR, exist_ok=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [RAPID] %(levelname)s %(message)s",
    handlers=[logging.FileHandler(cfg.LOG_FILE), logging.StreamHandler()])
log=logging.getLogger("rapid")
strategy=RapidScalper()
paper_positions=[]
paper_realized=0.0


def ready(client):
    s=client.symbol
    log.info("cTrader ready | account=%s env=%s symbol=%s id=%s digits=%s minVolume=%s maxVolume=%s stepVolume=%s paper=%s",
        client.account_id,cfg.CTRADER_ENV,cfg.SYMBOL_NAME,client.symbol_id,s.digits,
        getattr(s,"minVolume",None),getattr(s,"maxVolume",None),getattr(s,"stepVolume",None),cfg.PAPER_TRADING)


def floating_pnl(bid, ask):
    total=0.0
    for p in paper_positions:
        exit_price=bid if p["side"]=="buy" else ask
        total += (exit_price-p["entry"]) if p["side"]=="buy" else (p["entry"]-exit_price)
    return total


def on_tick(client,bid,ask):
    global paper_realized
    if os.path.exists(cfg.KILL_SWITCH_FILE):
        return
    pnl=floating_pnl(bid,ask)
    action=strategy.basket_action(pnl,paper_realized)
    if action=="halt":
        log.warning("Daily loss halt | realized=%.2f",paper_realized); return
    if action=="close_all" and paper_positions:
        paper_realized += pnl
        log.info("PAPER basket close | positions=%d pnl=%.4f realized=%.4f",len(paper_positions),pnl,paper_realized)
        paper_positions.clear(); return

    side=strategy.on_tick(Tick(bid,ask),len(paper_positions))
    if side and cfg.PAPER_TRADING:
        entry=ask if side=="buy" else bid
        paper_positions.append({"side":side,"entry":entry})
        log.info("PAPER %s | entry=%.2f spread=%.3f stack=%d",side.upper(),entry,ask-bid,len(paper_positions))


if __name__=="__main__":
    CTraderClient(on_ready=ready,on_tick=on_tick).start()
