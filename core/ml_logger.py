# ===== core/ml_logger.py =====
# Логирование данных для машинного обучения
# =========================================

import os
import json
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime

from core.types import CoinRow, TradeResult


# Пути по умолчанию
DEFAULT_ML_DIR = r"C:\Pythone\Log_Short\ml_data"


@dataclass
class SignalRecord:
    """Запись сигнала для ML."""
    ts: int
    symbol: str
    
    # Рыночные данные
    price: float
    high_24h: float
    low_24h: float
    change_24h_pct: float
    turnover_24h: int
    funding_rate: float
    
    # Позиция
    range_position: float
    dist_to_high_pct: float
    
    # Тренды
    trend_1h_ppm: float = 0.0
    trend_3h_ppm: float = 0.0
    trend_24h_ppm: float = 0.0
    
    # Индикаторы
    volume_score: float = 0.0
    structure_score: float = 0.0
    exhaustion: float = 0.0
    btc_div_1h: float = 0.0
    
    # Вычисленные метрики
    short_prob: float = 0.0
    short_conf: float = 0.0
    candidate_pct: float = 0.0
    
    # Статус и гейты
    watch_type: str = ""
    status: str = ""
    score: float = 0.0
    
    gate0_passed: bool = False
    gate1_passed: bool = False
    gate2_passed: bool = False
    gate3_passed: bool = False
    gates_signal: str = ""
    
    # Торговый план
    entry_price: float = 0.0
    sl_price: float = 0.0
    tp1_price: float = 0.0
    tp2_price: float = 0.0
    rr_ratio: float = 0.0
    
    # Контекст
    btc_price: float = 0.0
    btc_change_24h: float = 0.0
    strategy: str = ""


@dataclass
class TradeRecord:
    """Запись сделки для ML."""
    ts: int
    symbol: str
    action: str  # OPEN, CLOSE, PARTIAL_CLOSE
    
    # Цены
    entry_price: float
    exit_price: float = 0.0
    
    # Результат
    pnl_pct: float = 0.0
    pnl_usd: float = 0.0
    
    # Параметры
    leverage: float = 1.0
    amount_usdt: float = 0.0
    
    # Метаданные входа
    entry_status: str = ""
    entry_score: float = 0.0
    entry_watch_type: str = ""
    
    # Причина закрытия
    close_reason: str = ""  # SL_HIT, TP1_HIT, TP2_HIT, TIMEOUT
    duration_sec: float = 0.0
    
    # Гейты на момент входа
    gate0: bool = False
    gate1: bool = False
    gate2: bool = False
    gate3: bool = False
    
    # Контекст
    btc_price: float = 0.0
    balance_after: float = 0.0
    strategy: str = ""


class MLLogger:
    """
    Логгер для ML данных.
    
    Записывает:
    - signals.jsonl — все сигналы (для обучения предсказанию)
    - trades.jsonl — все сделки (для оценки результатов)
    - features.jsonl — фичи для ML моделей
    """
    
    def __init__(self, ml_dir: str = DEFAULT_ML_DIR):
        self.ml_dir = ml_dir
        self.signals_path = os.path.join(ml_dir, "signals.jsonl")
        self.trades_path = os.path.join(ml_dir, "trades.jsonl")
        self.features_path = os.path.join(ml_dir, "features.jsonl")
        
        os.makedirs(ml_dir, exist_ok=True)
    
    # ===== Логирование сигналов =====
    
    def log_signal(self, row: CoinRow, btc_price: float = 0.0, btc_change: float = 0.0, strategy: str = ""):
        """Залогировать сигнал."""
        record = SignalRecord(
            ts=int(time.time()),
            symbol=row.symbol,
            price=row.price_now,
            high_24h=row.high_24h,
            low_24h=row.low_24h,
            change_24h_pct=row.change_24h_pct,
            turnover_24h=row.vol24_m * 1_000_000,
            funding_rate=row.funding_rate,
            range_position=row.range_position,
            dist_to_high_pct=row.dist_high_pct,
            trend_1h_ppm=row.trend_1h_ppm,
            trend_3h_ppm=row.trend_3h_ppm,
            trend_24h_ppm=row.trend_24h_ppm,
            volume_score=row.volume_score,
            structure_score=row.structure_score,
            exhaustion=row.exhaustion,
            btc_div_1h=row.btc_div_1h,
            short_prob=row.short_prob,
            short_conf=row.short_conf,
            candidate_pct=row.candidate_pct,
            watch_type=row.watch_type,
            status=row.status,
            score=row.score,
            gate0_passed=row.gate0_passed,
            gate1_passed=row.gate1_passed,
            gate2_passed=row.gate2_passed,
            gate3_passed=row.gate3_passed,
            gates_signal=row.gates_signal,
            entry_price=row.entry_price,
            sl_price=row.sl_price,
            tp1_price=row.tp1,
            tp2_price=row.tp2,
            rr_ratio=row.rr,
            btc_price=btc_price,
            btc_change_24h=btc_change,
            strategy=strategy
        )
        
        self._append_jsonl(self.signals_path, asdict(record))
    
    def log_signals_batch(self, rows: List[CoinRow], btc_price: float = 0.0, btc_change: float = 0.0, strategy: str = ""):
        """Залогировать пачку сигналов."""
        for row in rows:
            # Логируем только интересные (статус не пустой)
            if row.status and row.status != "":
                self.log_signal(row, btc_price, btc_change, strategy)
    
    # ===== Логирование сделок =====
    
    def log_trade_open(
        self,
        symbol: str,
        entry_price: float,
        leverage: float,
        amount_usdt: float,
        status: str,
        score: float,
        watch_type: str,
        gates: tuple,
        btc_price: float = 0.0,
        strategy: str = ""
    ):
        """Залогировать открытие сделки."""
        record = TradeRecord(
            ts=int(time.time()),
            symbol=symbol,
            action="OPEN",
            entry_price=entry_price,
            leverage=leverage,
            amount_usdt=amount_usdt,
            entry_status=status,
            entry_score=score,
            entry_watch_type=watch_type,
            gate0=gates[0] if len(gates) > 0 else False,
            gate1=gates[1] if len(gates) > 1 else False,
            gate2=gates[2] if len(gates) > 2 else False,
            gate3=gates[3] if len(gates) > 3 else False,
            btc_price=btc_price,
            strategy=strategy
        )
        
        self._append_jsonl(self.trades_path, asdict(record))
    
    def log_trade_close(
        self,
        symbol: str,
        entry_price: float,
        exit_price: float,
        pnl_pct: float,
        pnl_usd: float,
        leverage: float,
        amount_usdt: float,
        reason: str,
        duration_sec: float,
        balance_after: float,
        entry_status: str = "",
        entry_score: float = 0.0,
        strategy: str = ""
    ):
        """Залогировать закрытие сделки."""
        record = TradeRecord(
            ts=int(time.time()),
            symbol=symbol,
            action="CLOSE",
            entry_price=entry_price,
            exit_price=exit_price,
            pnl_pct=pnl_pct,
            pnl_usd=pnl_usd,
            leverage=leverage,
            amount_usdt=amount_usdt,
            close_reason=reason,
            duration_sec=duration_sec,
            balance_after=balance_after,
            entry_status=entry_status,
            entry_score=entry_score,
            strategy=strategy
        )
        
        self._append_jsonl(self.trades_path, asdict(record))
    
    def log_trade_partial(
        self,
        symbol: str,
        entry_price: float,
        exit_price: float,
        pnl_pct: float,
        pnl_usd: float,
        fraction: float,
        reason: str,
        strategy: str = ""
    ):
        """Залогировать частичное закрытие (TP1)."""
        record = TradeRecord(
            ts=int(time.time()),
            symbol=symbol,
            action="PARTIAL_CLOSE",
            entry_price=entry_price,
            exit_price=exit_price,
            pnl_pct=pnl_pct,
            pnl_usd=pnl_usd,
            amount_usdt=fraction,
            close_reason=reason,
            strategy=strategy
        )
        
        self._append_jsonl(self.trades_path, asdict(record))
    
    # ===== Анализ данных =====
    
    def get_signals_stats(self, hours: int = 24) -> Dict:
        """Статистика сигналов за N часов."""
        cutoff = time.time() - hours * 3600
        
        stats = {
            "total": 0,
            "by_status": {},
            "by_watch_type": {},
            "avg_score": 0.0,
            "gates_passed": {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
        }
        
        scores = []
        
        for record in self._read_jsonl(self.signals_path):
            if record.get("ts", 0) < cutoff:
                continue
            
            stats["total"] += 1
            
            status = record.get("status", "")
            stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
            
            wtype = record.get("watch_type", "")
            if wtype:
                stats["by_watch_type"][wtype] = stats["by_watch_type"].get(wtype, 0) + 1
            
            scores.append(record.get("score", 0))
            
            gates = sum([
                record.get("gate0_passed", False),
                record.get("gate1_passed", False),
                record.get("gate2_passed", False),
                record.get("gate3_passed", False)
            ])
            stats["gates_passed"][gates] = stats["gates_passed"].get(gates, 0) + 1
        
        if scores:
            stats["avg_score"] = sum(scores) / len(scores)
        
        return stats
    
    def get_trades_stats(self, hours: int = 24) -> Dict:
        """Статистика сделок за N часов."""
        cutoff = time.time() - hours * 3600
        
        stats = {
            "total": 0,
            "opens": 0,
            "closes": 0,
            "wins": 0,
            "losses": 0,
            "total_pnl": 0.0,
            "by_reason": {},
            "by_status": {},
            "win_rate": 0.0
        }
        
        for record in self._read_jsonl(self.trades_path):
            if record.get("ts", 0) < cutoff:
                continue
            
            action = record.get("action", "")
            
            if action == "OPEN":
                stats["opens"] += 1
            elif action in ("CLOSE", "PARTIAL_CLOSE"):
                stats["closes"] += 1
                stats["total"] += 1
                
                pnl = record.get("pnl_usd", 0)
                stats["total_pnl"] += pnl
                
                if pnl > 0:
                    stats["wins"] += 1
                else:
                    stats["losses"] += 1
                
                reason = record.get("close_reason", "")
                stats["by_reason"][reason] = stats["by_reason"].get(reason, 0) + 1
                
                status = record.get("entry_status", "")
                if status not in stats["by_status"]:
                    stats["by_status"][status] = {"count": 0, "pnl": 0}
                stats["by_status"][status]["count"] += 1
                stats["by_status"][status]["pnl"] += pnl
        
        if stats["total"] > 0:
            stats["win_rate"] = stats["wins"] / stats["total"] * 100
        
        return stats
    
    # ===== Утилиты =====
    
    def _append_jsonl(self, path: str, record: Dict):
        """Добавить запись в JSONL файл."""
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"ML Logger error: {e}")
    
    def _read_jsonl(self, path: str) -> List[Dict]:
        """Прочитать JSONL файл."""
        records = []
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            records.append(json.loads(line))
        except Exception:
            pass
        return records
    
    def clear_old_records(self, days: int = 30):
        """Удалить записи старше N дней."""
        cutoff = time.time() - days * 86400
        
        for path in [self.signals_path, self.trades_path]:
            if not os.path.exists(path):
                continue
            
            records = self._read_jsonl(path)
            filtered = [r for r in records if r.get("ts", 0) >= cutoff]
            
            with open(path, "w", encoding="utf-8") as f:
                for r in filtered:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")


# Singleton
_logger: Optional[MLLogger] = None


def get_ml_logger(ml_dir: str = DEFAULT_ML_DIR) -> MLLogger:
    """Получить экземпляр логгера."""
    global _logger
    if _logger is None:
        _logger = MLLogger(ml_dir)
    return _logger


# Удобные функции
def log_signal(row: CoinRow, btc_price: float = 0.0, btc_change: float = 0.0):
    """Залогировать сигнал."""
    get_ml_logger().log_signal(row, btc_price, btc_change)


def log_trade_open(symbol: str, entry_price: float, leverage: float, amount: float, 
                   status: str, score: float, watch_type: str, gates: tuple):
    """Залогировать открытие."""
    get_ml_logger().log_trade_open(symbol, entry_price, leverage, amount, status, score, watch_type, gates)


def log_trade_close(symbol: str, entry: float, exit_price: float, pnl_pct: float, 
                    pnl_usd: float, leverage: float, amount: float, reason: str,
                    duration: float, balance: float):
    """Залогировать закрытие."""
    get_ml_logger().log_trade_close(symbol, entry, exit_price, pnl_pct, pnl_usd, 
                                     leverage, amount, reason, duration, balance)
