"""
Minimal OANDA v20 REST API client using requests directly (no SDK dependency).
Docs: https://developer.oanda.com/rest-live-v20/introduction/
"""

import requests
import pandas as pd
import config

BASE_URLS = {
    "practice": "https://api-fxpractice.oanda.com",
    "live": "https://api-fxtrade.oanda.com",
}


class OandaClient:
    def __init__(self):
        if not config.OANDA_API_TOKEN or not config.OANDA_ACCOUNT_ID:
            raise ValueError(
                "OANDA_API_TOKEN and OANDA_ACCOUNT_ID must be set as environment variables"
            )
        self.base_url = BASE_URLS[config.OANDA_ENV]
        self.account_id = config.OANDA_ACCOUNT_ID
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {config.OANDA_API_TOKEN}",
            "Content-Type": "application/json",
        })

    def get_candles(self, instrument: str, granularity: str, count: int = 200) -> pd.DataFrame:
        """Fetch recent completed candles as a DataFrame with columns: time, open, high, low, close"""
        url = f"{self.base_url}/v3/instruments/{instrument}/candles"
        params = {"count": count, "granularity": granularity, "price": "M"}  # mid prices
        resp = self.session.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()["candles"]

        rows = []
        for c in data:
            if not c["complete"]:
                continue  # skip the currently-forming candle
            rows.append({
                "time": c["time"],
                "open": float(c["mid"]["o"]),
                "high": float(c["mid"]["h"]),
                "low": float(c["mid"]["l"]),
                "close": float(c["mid"]["c"]),
            })
        return pd.DataFrame(rows)

    def get_historical_candles(self, instrument: str, granularity: str, from_time: str, to_time: str) -> pd.DataFrame:
        """
        Fetch a full historical range, paginating since OANDA caps each
        request at 5000 candles. from_time/to_time are ISO 8601 strings
        (e.g. '2023-01-01T00:00:00Z').
        """
        all_rows = []
        cursor = from_time
        url = f"{self.base_url}/v3/instruments/{instrument}/candles"

        while True:
            params = {
                "granularity": granularity,
                "price": "M",
                "from": cursor,
                "to": to_time,
                "count": 5000,
            }
            resp = self.session.get(url, params=params)
            resp.raise_for_status()
            candles = resp.json()["candles"]
            if not candles:
                break

            for c in candles:
                if not c["complete"]:
                    continue
                all_rows.append({
                    "time": c["time"],
                    "open": float(c["mid"]["o"]),
                    "high": float(c["mid"]["h"]),
                    "low": float(c["mid"]["l"]),
                    "close": float(c["mid"]["c"]),
                })

            if len(candles) < 5000:
                break  # reached the end
            cursor = candles[-1]["time"]  # continue from last candle

        df = pd.DataFrame(all_rows).drop_duplicates(subset="time").reset_index(drop=True)
        return df

    def get_account_balance(self) -> float:
        url = f"{self.base_url}/v3/accounts/{self.account_id}/summary"
        resp = self.session.get(url)
        resp.raise_for_status()
        return float(resp.json()["account"]["balance"])

    def get_open_position(self, instrument: str):
        """Returns dict with 'units' (positive=long, negative=short) or None if flat"""
        url = f"{self.base_url}/v3/accounts/{self.account_id}/positions/{instrument}"
        resp = self.session.get(url)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        pos = resp.json()["position"]
        long_units = float(pos["long"]["units"])
        short_units = float(pos["short"]["units"])
        if long_units == 0 and short_units == 0:
            return None
        return {"units": long_units if long_units != 0 else short_units}

    def close_position(self, instrument: str):
        url = f"{self.base_url}/v3/accounts/{self.account_id}/positions/{instrument}/close"
        body = {"longUnits": "ALL", "shortUnits": "ALL"}
        resp = self.session.put(url, json=body)
        # 404 means nothing was open, which is fine
        if resp.status_code not in (200, 404):
            resp.raise_for_status()
        return resp.json() if resp.status_code == 200 else None

    def place_market_order(self, instrument: str, units: int, stop_loss_price: float = None,
                            take_profit_price: float = None):
        """
        units: positive = buy/long, negative = sell/short
        """
        order = {
            "order": {
                "type": "MARKET",
                "instrument": instrument,
                "units": str(units),
                "timeInForce": "FOK",
                "positionFill": "DEFAULT",
            }
        }
        if stop_loss_price is not None:
            order["order"]["stopLossOnFill"] = {"price": f"{stop_loss_price:.2f}"}
        if take_profit_price is not None:
            order["order"]["takeProfitOnFill"] = {"price": f"{take_profit_price:.2f}"}

        url = f"{self.base_url}/v3/accounts/{self.account_id}/orders"
        resp = self.session.post(url, json=order)
        resp.raise_for_status()
        return resp.json()
