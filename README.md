# Gold WaveTrend Trading Bot

Standalone port of the WaveTrend crossover logic from your TradingView Pine
Script. No TradingView dependency — pulls candles directly from OANDA and
trades XAU/USD (CFD) via their v20 REST API.

## Files
- `wavetrend_signal.py` — the ported signal logic (buy/sell crossover detection)
- `risk_engine.py` — ATR-based stop-loss/take-profit + position sizing (1% risk/trade)
- `oanda_client.py` — thin wrapper around OANDA's REST API
- `main.py` — the polling loop that ties it all together
- `config.py` — all tunable parameters
- `gold-trading-bot.service` — systemd unit for running this 24/7 on a VPS

## Setup

1. **Create an OANDA practice account** at oanda.com, generate a v20 API token
   from account settings, and note your account ID.

2. **Install dependencies:**
   ```
   pip install -r requirements.txt --break-system-packages
   ```

3. **Set environment variables** (copy `.env.example` to `.env` and fill in
   your real token/account ID). Keep `OANDA_ENV=practice` until you've watched
   it trade for a while.

4. **Run it directly first** to sanity check:
   ```
   export $(cat .env | xargs)
   python3 main.py
   ```
   Watch `trading_bot.log` — it logs every candle check, signal, and order.

5. **Deploy as a systemd service** once you trust it:
   ```
   sudo cp gold-trading-bot.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now gold-trading-bot
   sudo journalctl -u gold-trading-bot -f   # watch live logs
   ```

## Kill switch
Create a file called `killswitch.flag` in the working directory to
immediately stop the bot from placing any new trades (it keeps running and
logging but won't trade). Delete the file to resume.

## Before going live
- Run against the practice account for several weeks minimum.
- Backtest the WaveTrend logic on historical XAU/USD data — a live crossover
  strategy's real edge (or lack of one) only shows up over many trades and
  market regimes. This bot does not include a backtester yet.
- Confirm OANDA's exact XAU_USD unit sizing and margin requirements on your
  account before trusting the position sizing math.
- Switch `OANDA_ENV=live` and use your funded account token/ID only when
  you're confident.

## Backtesting

Run before ever going live:

```
# against real OANDA historical data (requires OANDA_API_TOKEN/ACCOUNT_ID set)
python3 backtest.py --from 2022-01-01 --to 2024-01-01 --granularity H1

# or against a local CSV export (columns: time,open,high,low,close)
python3 backtest.py --csv my_gold_data.csv
```

Outputs a stats report (return, win rate, profit factor, max drawdown) and
an `equity_curve.png` chart. Read the warnings printed at the top of
`backtest.py` before trusting the numbers — small sample sizes and
overfitting to one historical period are easy traps here.

## Not included yet (ask if you want these built)
- Telegram/notification alerts on trades
- Web dashboard for monitoring
- Walk-forward / out-of-sample testing (more rigorous than a single backtest)

## Running multiple instances on one VM (e.g. H1 + H4)

Two service templates are included: `gold-bot-h1.service` and
`gold-bot-h4.service`, pre-configured for separate working directories.

1. Make two copies of this whole folder on the VM, e.g.:
   ```
   ~/gold-bot-h1/
   ~/gold-bot-h4/
   ```
2. Give each its own `.env` (from `.env.example`) with `GRANULARITY=H1` or
   `GRANULARITY=H4` respectively.
3. **If both trade XAU_USD on the same OANDA account, use two separate
   OANDA accounts (or sub-accounts)** — otherwise the two bots will fight
   over the same position's stop-loss/take-profit. Put each account's
   token/ID in its respective `.env`.
4. Install both services:
   ```
   sudo cp gold-bot-h1.service gold-bot-h4.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now gold-bot-h1 gold-bot-h4
   sudo journalctl -u gold-bot-h1 -f   # or gold-bot-h4
   ```
