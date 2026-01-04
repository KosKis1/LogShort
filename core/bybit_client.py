# ===== core/bybit_client.py =====
# Клиент для Bybit API v5
# ==========================

import time
from typing import Dict, List, Optional, Tuple
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Suppress warnings
import warnings
warnings.filterwarnings("ignore", message=".*Connection pool.*")
import urllib3
urllib3.disable_warnings()


BYBIT_BASE = "https://api.bybit.com"


class BybitClient:
    """
    Клиент для Bybit API v5 (public endpoints).
    
    Особенности:
    - Connection pooling для предотвращения warnings
    - Retry strategy для надёжности
    - TTL кэширование для уменьшения нагрузки
    """
    
    def __init__(self, api_key: str = "", api_secret: str = ""):
        self.api_key = api_key
        self.api_secret = api_secret
        
        # Session с правильным connection pooling
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "ShortScanner/v3.0"})
        
        retry = Retry(
            total=3,
            backoff_factor=0.3,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=retry)
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)
        
        # TTL кэши
        self._tickers_cache: Optional[Tuple[float, List[Dict]]] = None
        self._kline_cache: Dict[str, Tuple[float, List[Dict]]] = {}
    
    def _get(self, path: str, params: Dict, timeout: int = 12) -> Dict:
        """Базовый GET запрос."""
        url = BYBIT_BASE + path
        r = self.session.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        
        rc = data.get("retCode", 0)
        if rc not in (0, "0", None):
            raise RuntimeError(f"Bybit retCode={rc} retMsg={data.get('retMsg')}")
        
        return data
    
    # ===== Тикеры =====
    
    def get_tickers(self, ttl_sec: int = 30) -> List[Dict]:
        """
        Получить все USDT linear тикеры.
        Кэшируется на ttl_sec секунд.
        """
        now = time.time()
        
        if self._tickers_cache:
            exp_ts, cached = self._tickers_cache
            if now < exp_ts:
                return cached
        
        data = self._get("/v5/market/tickers", {"category": "linear"})
        lst = (data.get("result") or {}).get("list") or []
        
        # Фильтруем только USDT
        tickers = [t for t in lst if t.get("symbol", "").endswith("USDT")]
        
        self._tickers_cache = (now + ttl_sec, tickers)
        return tickers
    
    def get_top_by_turnover(self, top_n: int = 200, ttl_sec: int = 600) -> List[Dict]:
        """
        Топ N монет по обороту за 24ч.
        """
        tickers = self.get_tickers(ttl_sec=ttl_sec)
        
        # Сортируем по turnover24h
        def turnover(t):
            try:
                return float(t.get("turnover24h", 0) or 0)
            except:
                return 0.0
        
        sorted_tickers = sorted(tickers, key=turnover, reverse=True)
        return sorted_tickers[:top_n]
    
    def get_ticker(self, symbol: str) -> Optional[Dict]:
        """Получить тикер для одного символа."""
        tickers = self.get_tickers()
        for t in tickers:
            if t.get("symbol") == symbol:
                return t
        return None
    
    def get_last_price(self, symbol: str) -> float:
        """Текущая цена символа."""
        ticker = self.get_ticker(symbol)
        if ticker:
            return float(ticker.get("lastPrice", 0) or 0)
        return 0.0
    
    def get_high_24h(self, symbol: str) -> float:
        """Максимум за 24ч."""
        ticker = self.get_ticker(symbol)
        if ticker:
            return float(ticker.get("highPrice24h", 0) or 0)
        return 0.0
    
    # ===== Свечи =====
    
    def get_klines(
        self, 
        symbol: str, 
        interval: str = "60",  # 1, 5, 15, 60, 240, D
        limit: int = 100,
        ttl_sec: int = 60
    ) -> List[Dict]:
        """
        Получить свечи (klines).
        
        interval: "1", "5", "15", "60", "240", "D"
        """
        cache_key = f"{symbol}_{interval}_{limit}"
        now = time.time()
        
        if cache_key in self._kline_cache:
            exp_ts, cached = self._kline_cache[cache_key]
            if now < exp_ts:
                return cached
        
        data = self._get("/v5/market/kline", {
            "category": "linear",
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        })
        
        lst = (data.get("result") or {}).get("list") or []
        
        # Bybit возвращает в обратном порядке, переворачиваем
        klines = []
        for item in reversed(lst):
            klines.append({
                "timestamp": int(item[0]),
                "open": float(item[1]),
                "high": float(item[2]),
                "low": float(item[3]),
                "close": float(item[4]),
                "volume": float(item[5]),
                "turnover": float(item[6]) if len(item) > 6 else 0,
            })
        
        self._kline_cache[cache_key] = (now + ttl_sec, klines)
        return klines
    
    def get_klines_multi_interval(
        self, 
        symbol: str,
        intervals: List[str] = ["5", "15", "60", "240"]
    ) -> Dict[str, List[Dict]]:
        """Получить свечи нескольких интервалов."""
        result = {}
        for interval in intervals:
            result[interval] = self.get_klines(symbol, interval)
        return result
    
    # ===== Funding =====
    
    def get_funding_rate(self, symbol: str) -> float:
        """Текущий funding rate."""
        ticker = self.get_ticker(symbol)
        if ticker:
            return float(ticker.get("fundingRate", 0) or 0)
        return 0.0
    
    # ===== Утилиты =====
    
    def clear_cache(self):
        """Очистить все кэши."""
        self._tickers_cache = None
        self._kline_cache = {}
    
    def parse_ticker(self, ticker: Dict) -> Dict:
        """Парсинг тикера в удобный формат."""
        return {
            "symbol": ticker.get("symbol", ""),
            "price": float(ticker.get("lastPrice", 0) or 0),
            "high_24h": float(ticker.get("highPrice24h", 0) or 0),
            "low_24h": float(ticker.get("lowPrice24h", 0) or 0),
            "change_24h_pct": float(ticker.get("price24hPcnt", 0) or 0) * 100,
            "turnover_24h": float(ticker.get("turnover24h", 0) or 0),
            "volume_24h": float(ticker.get("volume24h", 0) or 0),
            "funding_rate": float(ticker.get("fundingRate", 0) or 0),
        }


# Singleton instance
_client: Optional[BybitClient] = None


def get_client() -> BybitClient:
    """Получить глобальный экземпляр клиента."""
    global _client
    if _client is None:
        _client = BybitClient()
    return _client


def fetch_prices_batch(symbols: List[str], timeout: float = 5.0) -> Dict[str, float]:
    """
    Получить цены для списка символов.
    Используется в Trainer.
    """
    result = {}
    if not symbols:
        return result
    
    try:
        client = get_client()
        tickers = client.get_tickers()
        symbols_upper = set(s.upper() for s in symbols)
        
        for t in tickers:
            sym = t.get("symbol", "")
            if sym in symbols_upper:
                lp = t.get("lastPrice")
                if lp:
                    result[sym] = float(lp)
        
        return result
    except Exception:
        return result


def fetch_last_price(symbol: str) -> float:
    """Получить цену одного символа."""
    return get_client().get_last_price(symbol)


def fetch_high_24h(symbol: str) -> float:
    """Получить high за 24ч."""
    return get_client().get_high_24h(symbol)
