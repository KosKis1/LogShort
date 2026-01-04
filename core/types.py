# ===== core/types.py =====
# Базовые типы данных для всей системы
# ================================

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from enum import Enum


class Status(Enum):
    """Статусы монеты в системе наблюдения."""
    OBSERVATION = "Наблюдение"      # Мониторим
    INTEREST = "Интерес"            # Потенциальный кандидат
    READINESS = "Готовность"        # Готов к входу
    ENTRY = "ВХОД"                  # Сигнал на вход
    
    @classmethod
    def from_string(cls, s: str) -> "Status":
        for status in cls:
            if status.value == s:
                return status
        return cls.OBSERVATION


class WatchType(Enum):
    """Типы наблюдения (паттерны)."""
    GROWTH_CORRECTION = "Рост/Кор"      # Рост с коррекцией
    PUMP_CORRECTION = "Памп/Кор"        # Памп с коррекцией
    FLAT_FALL = "Пл/Пад"                # Плато с падением
    NONE = ""
    
    @classmethod
    def from_string(cls, s: str) -> "WatchType":
        for wt in cls:
            if wt.value == s:
                return wt
        return cls.NONE


@dataclass
class CoinRow:
    """
    Данные по одной монете.
    Центральная структура данных системы.
    """
    symbol: str = ""
    
    # Базовые рыночные данные
    price_now: float = 0.0
    high_24h: float = 0.0
    low_24h: float = 0.0
    change_24h_pct: float = 0.0
    vol24_m: int = 0                    # Оборот в миллионах
    funding_rate: float = 0.0
    
    # Позиция в диапазоне
    range_position: float = 0.0         # 0-100%, где в диапазоне low-high
    dist_high_pct: float = 0.0          # Расстояние до хая в %
    
    # Тренды (% в минуту)
    trend_1h_ppm: float = 0.0
    trend_3h_ppm: float = 0.0
    trend_24h_ppm: float = 0.0
    
    # Объёмные индикаторы
    vol_ratio_5m_1h: float = 0.0        # Ускорение объёма 5м/1ч
    vol_ratio_15m_3h: float = 0.0       # Ускорение объёма 15м/3ч
    volume_score: float = 0.0           # Итоговый скор объёма
    
    # Структурные индикаторы
    structure_score: float = 0.0        # Оценка структуры свечей
    exhaustion: float = 0.0             # Истощение тренда
    
    # BTC корреляция
    btc_div_1h: float = 0.0             # Дивергенция от BTC
    btc_price: float = 0.0
    btc_change_24h: float = 0.0
    
    # Вычисленные метрики (стратегия)
    short_prob: float = 0.0             # Вероятность SHORT
    short_conf: float = 0.0             # Подтверждение падения
    candidate_pct: float = 0.0          # Рейтинг кандидата
    
    # Торговый план
    entry_price: float = 0.0
    sl_price: float = 0.0
    tp1: float = 0.0
    tp2: float = 0.0
    tp3: float = 0.0
    rr: float = 0.0                     # Risk/Reward
    
    # Статус и сигналы
    status: str = ""                    # Наблюдение/Интерес/Готовность/ВХОД
    watch_type: str = ""                # Тип наблюдения
    signal: str = ""                    # Текстовый сигнал
    score: float = 0.0                  # Итоговый скор для Trainer
    
    # Гейты
    gate0_passed: bool = False
    gate1_passed: bool = False
    gate2_passed: bool = False
    gate3_passed: bool = False
    gates_signal: str = ""
    
    # Служебные
    top_rank: int = 0
    grade: str = ""                     # A/B/C/D
    valid: bool = True
    last_update: float = 0.0
    added_at: float = 0.0               # Время добавления в кандидаты
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь для JSON."""
        return {
            "symbol": self.symbol,
            "price_now": self.price_now,
            "high_24h": self.high_24h,
            "low_24h": self.low_24h,
            "change_24h_pct": self.change_24h_pct,
            "vol24_m": self.vol24_m,
            "funding_rate": self.funding_rate,
            "range_position": self.range_position,
            "dist_high_pct": self.dist_high_pct,
            "trend_1h_ppm": self.trend_1h_ppm,
            "trend_3h_ppm": self.trend_3h_ppm,
            "trend_24h_ppm": self.trend_24h_ppm,
            "volume_score": self.volume_score,
            "structure_score": self.structure_score,
            "exhaustion": self.exhaustion,
            "btc_div_1h": self.btc_div_1h,
            "short_prob": self.short_prob,
            "short_conf": self.short_conf,
            "candidate_pct": self.candidate_pct,
            "entry_price": self.entry_price,
            "sl_price": self.sl_price,
            "tp1": self.tp1,
            "tp2": self.tp2,
            "rr": self.rr,
            "status": self.status,
            "watch_type": self.watch_type,
            "signal": self.signal,
            "score": self.score,
            "gate0_passed": self.gate0_passed,
            "gate1_passed": self.gate1_passed,
            "gate2_passed": self.gate2_passed,
            "gate3_passed": self.gate3_passed,
            "grade": self.grade,
        }


@dataclass
class TradeSignal:
    """Торговый сигнал для Trainer."""
    symbol: str
    status: str
    watch_type: str
    score: float
    
    entry_price: float
    sl_price: float
    tp1_price: float
    tp2_price: float
    
    leverage: float
    amount_usdt: float
    
    # Метаданные
    gate0_passed: bool = False
    gate1_passed: bool = False
    gate2_passed: bool = False
    gate3_passed: bool = False
    signal_text: str = ""
    
    timestamp: float = 0.0


@dataclass
class TradeResult:
    """Результат сделки для ML."""
    symbol: str
    entry_price: float
    exit_price: float
    pnl_pct: float
    pnl_usd: float
    
    reason: str                         # SL_HIT, TP1_HIT, TP2_HIT, TIMEOUT
    duration_sec: float
    
    # Параметры входа (для ML)
    entry_status: str = ""
    entry_score: float = 0.0
    entry_watch_type: str = ""
    leverage: float = 0.0
    
    timestamp: float = 0.0
