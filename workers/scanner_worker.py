# ===== workers/scanner_worker.py =====
# Фоновый поток сканирования монет
# ==================================

import time
import traceback
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from PySide6.QtCore import QThread, Signal

from core.types import CoinRow
from core.bybit_client import BybitClient
from core.ml_logger import get_ml_logger


class ScannerWorker(QThread):
    """
    Фоновый поток для сканирования монет.
    
    Сигналы:
    - progress(int, int, str) — прогресс (current, total, symbol)
    - coin_ready(str, CoinRow) — монета обработана
    - finished_all(dict) — все монеты обработаны {symbol: CoinRow}
    - error(str) — ошибка
    """
    
    progress = Signal(int, int, str)
    coin_ready = Signal(str, object)
    finished_all = Signal(dict)
    error = Signal(str)
    
    def __init__(
        self,
        client: BybitClient,
        strategy,  # BaseStrategy
        symbols: Optional[List[str]] = None,
        top_n: int = 200,
        max_workers: int = 8,
        parent=None
    ):
        super().__init__(parent)
        self.client = client
        self.strategy = strategy
        self.symbols = symbols
        self.top_n = top_n
        self.max_workers = max_workers
        
        self._stop_flag = False
        self.results: Dict[str, CoinRow] = {}
        
        # BTC данные для контекста
        self.btc_price: float = 0.0
        self.btc_change_24h: float = 0.0
    
    def stop(self):
        """Остановить сканирование."""
        self._stop_flag = True
    
    def run(self):
        """Основной цикл сканирования."""
        try:
            self._stop_flag = False
            self.results = {}
            
            # Получаем список монет
            if self.symbols:
                symbols = self.symbols
            else:
                symbols = self._get_top_symbols()
            
            if not symbols:
                self.error.emit("Не удалось получить список монет")
                return
            
            # Получаем BTC данные
            self._fetch_btc_data()
            
            total = len(symbols)
            processed = 0
            
            # Параллельная обработка
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(self._process_symbol, sym): sym 
                    for sym in symbols
                }
                
                for future in as_completed(futures):
                    if self._stop_flag:
                        break
                    
                    symbol = futures[future]
                    processed += 1
                    
                    try:
                        row = future.result(timeout=30)
                        if row and row.valid:
                            self.results[symbol] = row
                            self.coin_ready.emit(symbol, row)
                    except Exception as e:
                        pass  # Пропускаем ошибки отдельных монет
                    
                    self.progress.emit(processed, total, symbol)
            
            # Логируем сигналы для ML
            self._log_signals()
            
            self.finished_all.emit(self.results)
            
        except Exception as e:
            self.error.emit(f"Scanner error: {e}\n{traceback.format_exc()}")
    
    def _get_top_symbols(self) -> List[str]:
        """Получить топ монет по обороту."""
        try:
            tickers = self.client.get_top_by_turnover(self.top_n)
            return [t.get("symbol", "") for t in tickers if t.get("symbol", "").endswith("USDT")]
        except Exception:
            return []
    
    def _fetch_btc_data(self):
        """Получить данные BTC для контекста."""
        try:
            ticker = self.client.get_ticker("BTCUSDT")
            if ticker:
                self.btc_price = float(ticker.get("lastPrice", 0) or 0)
                self.btc_change_24h = float(ticker.get("price24hPcnt", 0) or 0) * 100
        except Exception:
            pass
    
    def _process_symbol(self, symbol: str) -> Optional[CoinRow]:
        """Обработать одну монету."""
        try:
            # Получаем тикер
            ticker = self.client.get_ticker(symbol)
            if not ticker:
                return None
            
            # Создаём CoinRow из тикера
            row = self._ticker_to_row(ticker)
            
            # Получаем свечи
            klines = self.client.get_klines_multi_interval(
                symbol, 
                intervals=["5", "15", "60", "240"]
            )
            
            # Вычисляем индикаторы через стратегию
            row = self.strategy.compute_indicators(row, klines)
            
            # BTC дивергенция
            if self.btc_change_24h != 0:
                row.btc_div_1h = row.trend_1h_ppm - (self.btc_change_24h / 60)
            row.btc_price = self.btc_price
            row.btc_change_24h = self.btc_change_24h
            
            # Статус и скор
            row.status, row.signal = self.strategy.compute_status(row)
            row.score = self.strategy.compute_score(row)
            row.watch_type = self.strategy.compute_watch_type(row)
            
            row.last_update = time.time()
            
            return row
            
        except Exception:
            return None
    
    def _ticker_to_row(self, ticker: Dict) -> CoinRow:
        """Конвертировать тикер в CoinRow."""
        return CoinRow(
            symbol=ticker.get("symbol", ""),
            price_now=float(ticker.get("lastPrice", 0) or 0),
            high_24h=float(ticker.get("highPrice24h", 0) or 0),
            low_24h=float(ticker.get("lowPrice24h", 0) or 0),
            change_24h_pct=float(ticker.get("price24hPcnt", 0) or 0) * 100,
            vol24_m=int(float(ticker.get("turnover24h", 0) or 0) / 1_000_000),
            funding_rate=float(ticker.get("fundingRate", 0) or 0),
            valid=True
        )
    
    def _log_signals(self):
        """Логировать сигналы для ML."""
        try:
            logger = get_ml_logger()
            for symbol, row in self.results.items():
                if row.status in ("Интерес", "Готовность", "ВХОД"):
                    logger.log_signal(
                        row, 
                        btc_price=self.btc_price,
                        btc_change=self.btc_change_24h,
                        strategy=self.strategy.name
                    )
        except Exception:
            pass


class QuickUpdateWorker(QThread):
    """
    Быстрое обновление цен (без полного пересчёта).
    Используется для обновления таблицы кандидатов.
    """
    
    updated = Signal(dict)  # {symbol: price}
    
    def __init__(self, client: BybitClient, symbols: List[str], parent=None):
        super().__init__(parent)
        self.client = client
        self.symbols = symbols
    
    def run(self):
        """Получить текущие цены."""
        try:
            prices = {}
            tickers = self.client.get_tickers(ttl_sec=5)
            
            symbols_set = set(self.symbols)
            for t in tickers:
                sym = t.get("symbol", "")
                if sym in symbols_set:
                    prices[sym] = float(t.get("lastPrice", 0) or 0)
            
            self.updated.emit(prices)
        except Exception:
            self.updated.emit({})


class CandidatesUpdateWorker(QThread):
    """
    Фоновое обновление кандидатов с полным пересчётом индикаторов.
    Использует параллельные запросы для ускорения.
    """
    
    progress = Signal(int, int, str)  # current, total, symbol
    coin_updated = Signal(str, object)  # symbol, CoinRow
    finished = Signal(dict)  # {symbol: CoinRow}
    error = Signal(str)
    
    def __init__(
        self,
        client: BybitClient,
        strategy,
        rows: Dict[str, CoinRow],
        max_candidates: int = 30,
        parent=None
    ):
        super().__init__(parent)
        self.client = client
        self.strategy = strategy
        self.rows = rows
        self.max_candidates = max_candidates
        self._stop_flag = False
    
    def stop(self):
        self._stop_flag = True
    
    def run(self):
        """Обновление кандидатов с параллельными запросами."""
        import concurrent.futures
        import time as time_module
        
        try:
            if not self.rows:
                self.finished.emit({})
                return
            
            candidates = self._select_candidates()
            if not candidates:
                self.finished.emit(self.rows)
                return
            
            # BTC данные
            btc_row = self.rows.get("BTCUSDT")
            btc_change = btc_row.change_24h_pct if btc_row else 0
            btc_price = btc_row.price_now if btc_row else 0
            
            total = len(candidates)
            updated_rows = dict(self.rows)
            
            # Сначала получаем ВСЕ тикеры одним запросом
            all_tickers = self.client.get_tickers(ttl_sec=2)
            tickers_map = {t.get("symbol"): t for t in all_tickers}
            
            # Функция для обновления одной монеты
            def update_coin(symbol: str) -> tuple:
                if self._stop_flag:
                    return (symbol, None)
                
                try:
                    row = updated_rows.get(symbol)
                    if not row:
                        return (symbol, None)
                    
                    # Тикер из кеша
                    ticker = tickers_map.get(symbol)
                    if not ticker:
                        return (symbol, None)
                    
                    # Обновляем базовые данные
                    row.price_now = float(ticker.get("lastPrice", 0) or 0)
                    row.high_24h = float(ticker.get("highPrice24h", 0) or 0)
                    row.low_24h = float(ticker.get("lowPrice24h", 0) or 0)
                    row.change_24h_pct = float(ticker.get("price24hPcnt", 0) or 0) * 100
                    row.funding_rate = float(ticker.get("fundingRate", 0) or 0)
                    
                    # Пересчитываем позицию
                    if row.high_24h > row.low_24h:
                        row.range_position = (row.price_now - row.low_24h) / (row.high_24h - row.low_24h) * 100
                    row.dist_high_pct = (row.high_24h - row.price_now) / row.high_24h * 100 if row.high_24h > 0 else 0
                    
                    # Получаем свечи (это основная задержка)
                    klines = self.client.get_klines_multi_interval(
                        symbol, 
                        intervals=["5", "15", "60", "240"]
                    )
                    
                    # Пересчитываем индикаторы
                    row = self.strategy.compute_indicators(row, klines)
                    
                    # BTC дивергенция
                    if btc_change != 0:
                        row.btc_div_1h = row.trend_1h_ppm - (btc_change / 60)
                    row.btc_price = btc_price
                    row.btc_change_24h = btc_change
                    
                    # Статус и скор
                    row.status, row.signal = self.strategy.compute_status(row)
                    row.score = self.strategy.compute_score(row)
                    row.watch_type = self.strategy.compute_watch_type(row)
                    row.last_update = time_module.time()
                    
                    return (symbol, row)
                    
                except Exception as e:
                    return (symbol, None)
            
            # Параллельное выполнение (5 потоков)
            completed = 0
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(update_coin, sym): sym for sym in candidates}
                
                for future in concurrent.futures.as_completed(futures):
                    if self._stop_flag:
                        break
                    
                    symbol, row = future.result()
                    completed += 1
                    
                    if row:
                        updated_rows[symbol] = row
                        self.coin_updated.emit(symbol, row)
                    
                    self.progress.emit(completed, total, symbol)
            
            self.finished.emit(updated_rows)
            
        except Exception as e:
            self.error.emit(f"Candidates update error: {e}")
            self.finished.emit(self.rows)
    
    def _select_candidates(self) -> List[str]:
        """Выбрать монеты для обновления."""
        candidates = []
        
        for sym, row in self.rows.items():
            if row.status in ("Интерес", "Готовность", "ВХОД"):
                candidates.append((sym, row.score + 100))
            elif row.status == "Наблюдение" and row.score > 30:
                candidates.append((sym, row.score))
        
        if len(candidates) < self.max_candidates:
            for sym, row in self.rows.items():
                if sym not in [c[0] for c in candidates]:
                    candidates.append((sym, row.score))
        
        candidates.sort(key=lambda x: x[1], reverse=True)
        return [c[0] for c in candidates[:self.max_candidates]]


# ============================================================
# ТРЁХУРОВНЕВАЯ СИСТЕМА СКАНИРОВАНИЯ V2
# ============================================================

class PriceUpdateWorker(QThread):
    """
    УРОВЕНЬ 2: Быстрое обновление цен (каждые 30 сек).
    Обновляет только: price_now, change_24h_pct, range_position, dist_high_pct.
    НЕ запрашивает свечи — только тикеры.
    """
    
    progress = Signal(int, int)  # current, total
    finished = Signal(dict)  # {symbol: updated_row}
    error = Signal(str)
    
    def __init__(
        self,
        client: BybitClient,
        rows: Dict[str, CoinRow],
        parent=None
    ):
        super().__init__(parent)
        self.client = client
        self.rows = rows
        self._stop_flag = False
    
    def stop(self):
        self._stop_flag = True
    
    def run(self):
        """Быстрое обновление цен из тикеров + пересчёт статуса."""
        try:
            if not self.rows:
                self.finished.emit({})
                return
            
            # Один запрос на все тикеры
            tickers = self.client.get_tickers(ttl_sec=5)
            tickers_map = {t.get("symbol"): t for t in tickers}
            
            updated_rows = dict(self.rows)
            total = len(updated_rows)
            processed = 0
            
            for symbol, row in updated_rows.items():
                if self._stop_flag:
                    break
                
                ticker = tickers_map.get(symbol)
                if ticker:
                    # Сохраняем старую цену для расчёта изменения
                    old_price = row.price_now
                    
                    # Обновляем ценовые данные
                    row.price_now = float(ticker.get("lastPrice", 0) or 0)
                    row.high_24h = float(ticker.get("highPrice24h", 0) or 0)
                    row.low_24h = float(ticker.get("lowPrice24h", 0) or 0)
                    row.change_24h_pct = float(ticker.get("price24hPcnt", 0) or 0) * 100
                    row.funding_rate = float(ticker.get("fundingRate", 0) or 0)
                    
                    # Пересчитываем позицию
                    if row.high_24h > row.low_24h:
                        row.range_position = (row.price_now - row.low_24h) / (row.high_24h - row.low_24h) * 100
                    if row.high_24h > 0:
                        row.dist_high_pct = (row.high_24h - row.price_now) / row.high_24h * 100
                    
                    # === БЫСТРЫЙ ПЕРЕСЧЁТ СТАТУСА ===
                    # Логика: позиция > 85% и цена растёт = потенциальный шорт
                    old_status = row.status
                    
                    if row.range_position > 90 and row.change_24h_pct > 5:
                        if row.status not in ("ВХОД",):
                            row.status = "Готовность"
                    elif row.range_position > 85 and row.change_24h_pct > 3:
                        if row.status not in ("Готовность", "ВХОД"):
                            row.status = "Интерес"
                    elif row.range_position > 80 and row.change_24h_pct > 2:
                        if row.status not in ("Интерес", "Готовность", "ВХОД"):
                            row.status = "Наблюдение"
                    
                    # Если статус изменился - устанавливаем время
                    if old_status != row.status and row.added_at == 0:
                        row.added_at = time.time()
                    
                    row.last_update = time.time()
                
                processed += 1
                if processed % 50 == 0:
                    self.progress.emit(processed, total)
            
            self.progress.emit(total, total)
            self.finished.emit(updated_rows)
            
        except Exception as e:
            self.error.emit(f"Price update error: {e}")
            self.finished.emit(self.rows)


class PumpDetectorWorker(QThread):
    """
    УРОВЕНЬ 3: Детектор пампов (каждые 10 сек).
    Проверяет ВСЕ 200 монет на 5м изменения.
    Использует только 1м свечи для скорости.
    """
    
    pump_detected = Signal(str, float, float)  # symbol, change_5m, volume_spike
    finished = Signal(list)  # [(symbol, change_5m, volume_spike), ...]
    error = Signal(str)
    
    def __init__(
        self,
        client: BybitClient,
        rows: Dict[str, CoinRow],
        top_n: int = 200,  # Проверяем ВСЕ монеты
        pump_threshold: float = 1.0,  # +1% за 5 минут
        parent=None
    ):
        super().__init__(parent)
        self.client = client
        self.rows = rows
        self.top_n = top_n
        self.pump_threshold = pump_threshold
        self._stop_flag = False
    
    def stop(self):
        self._stop_flag = True
    
    def run(self):
        """Детектирование пампов по всем 200 монетам."""
        try:
            if not self.rows:
                self.finished.emit([])
                return
            
            # Берём ВСЕ монеты, сортируем по обороту
            sorted_rows = sorted(
                self.rows.items(),
                key=lambda x: x[1].vol24_m,
                reverse=True
            )[:self.top_n]
            
            pumps = []
            
            for symbol, row in sorted_rows:
                if self._stop_flag:
                    break
                
                try:
                    # Получаем только 1м свечи (быстро)
                    klines_1m = self.client.get_klines(symbol, "1", limit=10, ttl_sec=10)
                    
                    if len(klines_1m) >= 5:
                        # Изменение за 5 минут
                        price_now = klines_1m[-1]["close"]
                        price_5m_ago = klines_1m[-5]["close"]
                        
                        if price_5m_ago > 0:
                            change_5m = ((price_now - price_5m_ago) / price_5m_ago) * 100
                            
                            # Volume spike
                            volumes = [k["volume"] for k in klines_1m]
                            avg_vol = sum(volumes[:-1]) / len(volumes[:-1]) if len(volumes) > 1 else 1
                            vol_spike = volumes[-1] / avg_vol if avg_vol > 0 else 1
                            
                            # Обновляем row
                            row.change_5m = change_5m
                            row.volume_spike = vol_spike
                            
                            # Детектируем памп (рост) или дамп (падение для шорта)
                            if abs(change_5m) >= self.pump_threshold:
                                pumps.append((symbol, change_5m, vol_spike))
                                self.pump_detected.emit(symbol, change_5m, vol_spike)
                
                except Exception:
                    pass
            
            self.finished.emit(pumps)
            
        except Exception as e:
            self.error.emit(f"Pump detector error: {e}")
            self.finished.emit([])
