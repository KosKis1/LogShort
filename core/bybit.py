from __future__ import annotations
import time
from typing import Dict, Any, List, Optional
import requests

class BybitPublic:
    def __init__(self, base_url: str = "https://api.bybit.com", timeout: int = 12) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.sess = requests.Session()
        self.sess.headers.update({"User-Agent":"ShortProject2/step3.2"})

    def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = self.base_url + path
        r = self.sess.get(url, params=params, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        rc = data.get("retCode", 0) if isinstance(data, dict) else 0
        if rc not in (0, "0", None):
            raise RuntimeError(f"Bybit retCode={rc} retMsg={data.get('retMsg')}")
        return data

    def market_tickers(self, category: str = "linear") -> List[Dict[str, Any]]:
        data = self._get("/v5/market/tickers", {"category": category})
        return data.get("result", {}).get("list", []) or []

    def kline(self, symbol: str, interval_min: int, limit: int = 200, category: str = "linear") -> List[List[str]]:
        # returns raw rows: [start, open, high, low, close, volume, turnover]
        data = self._get("/v5/market/kline", {
            "category": category,
            "symbol": symbol,
            "interval": str(int(interval_min)),
            "limit": str(int(limit)),
        })
        rows = data.get("result", {}).get("list", []) or []
        # API returns newest->oldest; convert to oldest->newest
        return list(reversed(rows))
