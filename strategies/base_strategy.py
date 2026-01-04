# ===== strategies/base_strategy.py =====
# Базовый класс для всех торговых стратегий
# =========================================

from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

from core.types import CoinRow, TradeSignal


@dataclass
class StrategyConfig:
    """Конфигурация стратегии."""
    name: str = "BaseStrategy"
    version: str = "1.0"
    
    # Risk Management
    sl_pct: float = 2.5              # Stop Loss %
    tp1_pct: float = 1.5             # Take Profit 1 %
    tp2_pct: float = 3.0             # Take Profit 2 %
    tp1_close_fraction: float = 0.5  # Закрыть 50% на TP1
    
    # Leverage
    min_leverage: float = 5.0
    max_leverage: float = 20.0
    leverage_safety: float = 0.8
    
    # Timeouts
    timeout_sec: int = 4 * 3600      # 4 часа
    timeout_flat_pct: float = 1.0    # Закрыть если PnL < 1%
    
    # Entry filters
    min_score: float = 50.0
    min_volume_24h_m: int = 3        # Минимум $3M оборота
    
    # Allowed statuses for entry
    entry_statuses: Tuple[str, ...] = ("Интерес", "Готовность", "ВХОД")


class BaseStrategy(ABC):
    """
    Абстрактный базовый класс для торговых стратегий.
    
    Каждая стратегия должна реализовать:
    - compute_indicators() - расчёт индикаторов
    - compute_status() - определение статуса
    - compute_score() - расчёт скора
    - should_enter() - условие входа
    - compute_trade_plan() - расчёт SL/TP
    """
    
    def __init__(self, config: Optional[StrategyConfig] = None):
        self.config = config or StrategyConfig()
    
    @property
    def name(self) -> str:
        return self.config.name
    
    @property
    def version(self) -> str:
        return self.config.version
    
    # ===== Абстрактные методы (ОБЯЗАТЕЛЬНО реализовать) =====
    
    @abstractmethod
    def compute_indicators(self, row: CoinRow, klines: Dict[str, List]) -> CoinRow:
        """
        Вычислить все индикаторы для монеты.
        
        Args:
            row: Данные монеты
            klines: Словарь свечей по интервалам {"5": [...], "60": [...], ...}
        
        Returns:
            Обновлённый CoinRow с вычисленными индикаторами
        """
        pass
    
    @abstractmethod
    def compute_status(self, row: CoinRow) -> Tuple[str, str]:
        """
        Определить статус монеты.
        
        Returns:
            (status, signal_text)
            status: "Наблюдение", "Интерес", "Готовность", "ВХОД"
            signal_text: Текстовое описание сигнала
        """
        pass
    
    @abstractmethod
    def compute_score(self, row: CoinRow) -> float:
        """
        Вычислить итоговый скор (0-100).
        Используется для ранжирования кандидатов.
        """
        pass
    
    @abstractmethod
    def should_enter(self, row: CoinRow) -> bool:
        """
        Проверить условия входа в позицию.
        
        Returns:
            True если можно входить
        """
        pass
    
    @abstractmethod
    def compute_trade_plan(self, row: CoinRow) -> Tuple[float, float, float, float, float]:
        """
        Вычислить торговый план.
        
        Returns:
            (entry_price, sl_price, tp1_price, tp2_price, rr_ratio)
        """
        pass
    
    # ===== Опциональные методы (можно переопределить) =====
    
    def compute_leverage(self, row: CoinRow) -> float:
        """
        Вычислить адаптивное плечо.
        По умолчанию на основе волатильности.
        """
        entry = row.entry_price or row.price_now
        high = row.high_24h
        
        if entry <= 0 or high <= entry:
            return self.config.min_leverage
        
        adverse_move_pct = (high - entry) / entry
        if adverse_move_pct <= 0:
            return self.config.min_leverage
        
        lev_max = self.config.leverage_safety / adverse_move_pct
        return max(self.config.min_leverage, min(self.config.max_leverage, lev_max))
    
    def filter_candidates(self, rows: List[CoinRow]) -> List[CoinRow]:
        """
        Отфильтровать кандидатов для входа.
        """
        candidates = []
        for row in rows:
            if row.status not in self.config.entry_statuses:
                continue
            if row.score < self.config.min_score:
                continue
            if row.vol24_m < self.config.min_volume_24h_m:
                continue
            if not self.should_enter(row):
                continue
            candidates.append(row)
        
        # Сортируем по скору
        candidates.sort(key=lambda r: r.score, reverse=True)
        return candidates
    
    def create_signal(self, row: CoinRow, amount_usdt: float = 100.0) -> TradeSignal:
        """
        Создать торговый сигнал из CoinRow.
        """
        entry, sl, tp1, tp2, rr = self.compute_trade_plan(row)
        leverage = self.compute_leverage(row)
        
        return TradeSignal(
            symbol=row.symbol,
            status=row.status,
            watch_type=row.watch_type,
            score=row.score,
            entry_price=entry,
            sl_price=sl,
            tp1_price=tp1,
            tp2_price=tp2,
            leverage=leverage,
            amount_usdt=amount_usdt,
            gate0_passed=row.gate0_passed,
            gate1_passed=row.gate1_passed,
            gate2_passed=row.gate2_passed,
            gate3_passed=row.gate3_passed,
            signal_text=row.signal,
        )
    
    # ===== Методы для ML =====
    
    def get_feature_names(self) -> List[str]:
        """
        Список названий фичей для ML.
        Переопределить в конкретной стратегии.
        """
        return [
            "range_position", "dist_high_pct", "change_24h_pct",
            "trend_1h_ppm", "trend_3h_ppm", "trend_24h_ppm",
            "volume_score", "structure_score", "exhaustion",
            "btc_div_1h", "funding_rate",
            "short_prob", "short_conf", "candidate_pct",
            "rr", "score"
        ]
    
    def extract_features(self, row: CoinRow) -> Dict[str, float]:
        """
        Извлечь фичи для ML из CoinRow.
        """
        return {
            "range_position": row.range_position,
            "dist_high_pct": row.dist_high_pct,
            "change_24h_pct": row.change_24h_pct,
            "trend_1h_ppm": row.trend_1h_ppm,
            "trend_3h_ppm": row.trend_3h_ppm,
            "trend_24h_ppm": row.trend_24h_ppm,
            "volume_score": row.volume_score,
            "structure_score": row.structure_score,
            "exhaustion": row.exhaustion,
            "btc_div_1h": row.btc_div_1h,
            "funding_rate": row.funding_rate,
            "short_prob": row.short_prob,
            "short_conf": row.short_conf,
            "candidate_pct": row.candidate_pct,
            "rr": row.rr,
            "score": row.score,
        }
    
    def to_dict(self) -> Dict:
        """Сериализация конфигурации стратегии."""
        return {
            "name": self.config.name,
            "version": self.config.version,
            "sl_pct": self.config.sl_pct,
            "tp1_pct": self.config.tp1_pct,
            "tp2_pct": self.config.tp2_pct,
            "min_leverage": self.config.min_leverage,
            "max_leverage": self.config.max_leverage,
            "min_score": self.config.min_score,
            "entry_statuses": self.config.entry_statuses,
        }
