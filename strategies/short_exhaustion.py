# ===== strategies/short_exhaustion.py =====
# Стратегия SHORT на истощении роста
# ===================================

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

from core.types import CoinRow
from core.math_utils import (
    clamp, safe_div, pct_change, range_position, dist_to_high_pct,
    trend_ppm, structure_score_from_candles, local_high,
    close_hours_ago, down, up, log1p_norm
)
from strategies.base_strategy import BaseStrategy, StrategyConfig


@dataclass
class ShortExhaustionConfig(StrategyConfig):
    """Конфигурация стратегии SHORT Exhaustion."""
    name: str = "ShortExhaustion"
    version: str = "2.0"
    
    # Risk Management
    sl_pct: float = 2.5
    tp1_pct: float = 1.5
    tp2_pct: float = 3.0
    
    # Пороги для гейтов
    gate0_pump_threshold: float = 8.0      # Минимум роста 24ч для "пампа"
    gate0_range_min: float = 70.0          # Минимум позиции в диапазоне
    
    gate1_exhaustion_min: float = 0.3      # Минимум истощения
    gate1_dist_high_max: float = 5.0       # Макс расстояние до хая
    
    gate2_trend_1h_max: float = 0.0        # Тренд 1ч должен быть отрицательным
    gate2_structure_min: float = 50.0      # Минимум красных свечей
    
    gate3_btc_div_max: float = 0.0         # Слабее BTC
    gate3_volume_score_min: float = 0.3    # Минимум ускорения объёма


class ShortExhaustionStrategy(BaseStrategy):
    """
    Стратегия SHORT на истощении роста.
    
    Логика:
    1. Монета сильно выросла (pump)
    2. Находится близко к хаю
    3. Показывает признаки истощения
    4. Начинает падать (подтверждение)
    5. Слабее BTC
    
    Гейты:
    - Gate 0: Базовый фильтр (памп + позиция в диапазоне)
    - Gate 1: Истощение (тренды + расстояние до хая)
    - Gate 2: Подтверждение падения (структура + тренд 1ч)
    - Gate 3: Финальный фильтр (BTC дивергенция + объём)
    """
    
    def __init__(self, config: Optional[ShortExhaustionConfig] = None):
        super().__init__(config or ShortExhaustionConfig())
        self.config: ShortExhaustionConfig = self.config
    
    # ===== Вычисление индикаторов =====
    
    def compute_indicators(self, row: CoinRow, klines: Dict[str, List]) -> CoinRow:
        """Вычислить все индикаторы."""
        
        kl_5m = klines.get("5", [])
        kl_15m = klines.get("15", [])
        kl_1h = klines.get("60", [])
        kl_4h = klines.get("240", [])
        
        # Позиция в диапазоне
        row.range_position = range_position(row.price_now, row.low_24h, row.high_24h)
        row.dist_high_pct = dist_to_high_pct(row.price_now, row.high_24h)
        
        # Тренды
        if kl_1h:
            close_1h_ago = close_hours_ago(kl_1h, 1)
            close_3h_ago = close_hours_ago(kl_1h, 3)
            close_24h_ago = close_hours_ago(kl_1h, 24)
            
            if close_1h_ago:
                row.trend_1h_ppm = trend_ppm(close_1h_ago, row.price_now, 60)
            if close_3h_ago:
                row.trend_3h_ppm = trend_ppm(close_3h_ago, row.price_now, 180)
            if close_24h_ago:
                row.trend_24h_ppm = trend_ppm(close_24h_ago, row.price_now, 1440)
        
        # Объёмные индикаторы
        row.vol_ratio_5m_1h = self._compute_volume_ratio(kl_5m, kl_1h, 12)
        row.vol_ratio_15m_3h = self._compute_volume_ratio(kl_15m, kl_1h, 12)
        row.volume_score = self._compute_volume_score(row.vol_ratio_5m_1h, row.vol_ratio_15m_3h)
        
        # Структура свечей
        row.structure_score = structure_score_from_candles(kl_1h, n=6)
        
        # Истощение
        row.exhaustion = self._compute_exhaustion(
            row.trend_1h_ppm, row.trend_3h_ppm, row.trend_24h_ppm
        )
        
        # Вероятности
        row.short_prob = self._compute_short_prob(row)
        row.short_conf = self._compute_conf_down(row)
        row.candidate_pct = self._compute_candidate_pct(row)
        
        # Гейты
        row.gate0_passed = self._check_gate0(row)
        row.gate1_passed = self._check_gate1(row)
        row.gate2_passed = self._check_gate2(row)
        row.gate3_passed = self._check_gate3(row)
        
        # Торговый план
        entry, sl, tp1, tp2, rr = self.compute_trade_plan(row)
        row.entry_price = entry
        row.sl_price = sl
        row.tp1 = tp1
        row.tp2 = tp2
        row.rr = rr
        
        # Грейд
        row.grade = self._grade_from(row.short_prob, row.short_conf)
        
        return row
    
    def _compute_volume_ratio(self, kl_short: List, kl_long: List, multiplier: int) -> float:
        """Отношение объёма коротких свечей к длинным."""
        if not kl_short or not kl_long:
            return 1.0
        
        vol_short = sum(float(k.get("turnover", 0) or k.get("volume", 0) or 0) for k in kl_short[-1:])
        vol_long = sum(float(k.get("turnover", 0) or k.get("volume", 0) or 0) for k in kl_long[-1:])
        
        return safe_div(vol_short * multiplier, vol_long, 1.0)
    
    def _compute_volume_score(self, ratio_5m_1h: float, ratio_15m_3h: float) -> float:
        """Итоговый скор объёма (0-1)."""
        avg = (ratio_5m_1h + ratio_15m_3h) / 2
        return clamp(avg - 0.5, 0, 1)  # >1 = ускорение
    
    def _compute_exhaustion(self, trend_1h: float, trend_3h: float, trend_24h: float) -> float:
        """
        Истощение тренда (0-1).
        Высокое = тренд замедляется, разворот вероятен.
        """
        if trend_24h <= 0:
            return 0.0
        
        # Если 24ч рост, но 1ч/3ч замедляются - истощение
        slowdown_1h = max(0, trend_24h - trend_1h) / max(0.001, trend_24h)
        slowdown_3h = max(0, trend_24h - trend_3h) / max(0.001, trend_24h)
        
        return clamp((slowdown_1h + slowdown_3h) / 2, 0, 1)
    
    def _compute_short_prob(self, row: CoinRow) -> float:
        """Вероятность SHORT (0-100)."""
        score = 0.0
        
        # Расстояние до хая (ближе = лучше)
        if row.dist_high_pct < 2:
            score += 25
        elif row.dist_high_pct < 5:
            score += 15
        
        # Объём
        score += row.volume_score * 20
        
        # BTC дивергенция (слабее = лучше)
        if row.btc_div_1h < 0:
            score += min(25, abs(row.btc_div_1h) * 100)
        
        # Истощение
        score += row.exhaustion * 30
        
        return clamp(score, 0, 100)
    
    def _compute_conf_down(self, row: CoinRow) -> float:
        """Подтверждение падения (0-100)."""
        score = 0.0
        
        # Тренд 1ч отрицательный
        if row.trend_1h_ppm < 0:
            score += min(30, abs(row.trend_1h_ppm) * 1000)
        
        # Тренд 3ч отрицательный
        if row.trend_3h_ppm < 0:
            score += min(30, abs(row.trend_3h_ppm) * 1000)
        
        # Структура свечей
        score += (row.structure_score / 100) * 25
        
        # Объём
        score += row.volume_score * 15
        
        return clamp(score, 0, 100)
    
    def _compute_candidate_pct(self, row: CoinRow) -> float:
        """Рейтинг кандидата (0-100)."""
        base = (row.short_prob + row.short_conf) / 2
        
        # Бонус за R/R
        if row.rr >= 2:
            base += 10
        elif row.rr >= 1.5:
            base += 5
        
        # Бонус за BTC дивергенцию
        if row.btc_div_1h < -0.01:
            base += 5
        
        # Штраф за низкое истощение
        if row.exhaustion < 0.25:
            base = min(base, 40)
        
        # Штраф за низкое подтверждение
        if row.short_conf < 50:
            base = min(base, 55)
        
        return clamp(base, 0, 100)
    
    def _grade_from(self, prob: float, conf: float) -> str:
        """Грейд A/B/C/D."""
        avg = (prob + conf) / 2
        if avg >= 75:
            return "A"
        if avg >= 60:
            return "B"
        if avg >= 45:
            return "C"
        return "D"
    
    # ===== Гейты =====
    
    def _check_gate0(self, row: CoinRow) -> bool:
        """Gate 0: Базовый фильтр."""
        # Должен быть памп или высокая позиция
        is_pump = row.change_24h_pct >= self.config.gate0_pump_threshold
        is_high = row.range_position >= self.config.gate0_range_min
        return is_pump or is_high
    
    def _check_gate1(self, row: CoinRow) -> bool:
        """Gate 1: Истощение."""
        has_exhaustion = row.exhaustion >= self.config.gate1_exhaustion_min
        near_high = row.dist_high_pct <= self.config.gate1_dist_high_max
        return has_exhaustion and near_high
    
    def _check_gate2(self, row: CoinRow) -> bool:
        """Gate 2: Подтверждение падения."""
        trend_down = row.trend_1h_ppm <= self.config.gate2_trend_1h_max
        structure_weak = row.structure_score >= self.config.gate2_structure_min
        return trend_down and structure_weak
    
    def _check_gate3(self, row: CoinRow) -> bool:
        """Gate 3: Финальный фильтр."""
        weaker_btc = row.btc_div_1h <= self.config.gate3_btc_div_max
        volume_ok = row.volume_score >= self.config.gate3_volume_score_min
        return weaker_btc and volume_ok
    
    # ===== Статус и скор =====
    
    def compute_status(self, row: CoinRow) -> Tuple[str, str]:
        """Определить статус монеты."""
        
        gates_passed = sum([
            row.gate0_passed, row.gate1_passed, 
            row.gate2_passed, row.gate3_passed
        ])
        
        if gates_passed == 4:
            return "ВХОД", "Все гейты пройдены! Сильный сигнал SHORT"
        
        if gates_passed == 3:
            if not row.gate3_passed:
                return "Готовность", "Ждём подтверждения BTC/объёма"
            if not row.gate2_passed:
                return "Готовность", "Ждём подтверждения падения"
            return "Готовность", "Почти готов к входу"
        
        if gates_passed == 2:
            if row.gate0_passed and row.gate1_passed:
                return "Интерес", "Истощение есть, ждём breakdown"
            return "Интерес", "Потенциальный кандидат"
        
        if gates_passed == 1:
            if row.gate0_passed:
                return "Наблюдение", "Памп/высокая позиция"
            return "Наблюдение", "Мониторинг"
        
        return "Наблюдение", "Не соответствует критериям"
    
    def compute_score(self, row: CoinRow) -> float:
        """Итоговый скор для ранжирования."""
        base = row.candidate_pct
        
        # Бонус за гейты
        gates_passed = sum([
            row.gate0_passed, row.gate1_passed,
            row.gate2_passed, row.gate3_passed
        ])
        base += gates_passed * 5
        
        # Бонус за статус
        status_bonus = {
            "ВХОД": 20,
            "Готовность": 10,
            "Интерес": 5,
            "Наблюдение": 0
        }
        base += status_bonus.get(row.status, 0)
        
        return clamp(base, 0, 100)
    
    def should_enter(self, row: CoinRow) -> bool:
        """Условие входа."""
        # Минимум 2 гейта
        gates_passed = sum([
            row.gate0_passed, row.gate1_passed,
            row.gate2_passed, row.gate3_passed
        ])
        if gates_passed < 2:
            return False
        
        # Статус должен быть подходящий
        if row.status not in self.config.entry_statuses:
            return False
        
        # Минимальный скор
        if row.score < self.config.min_score:
            return False
        
        return True
    
    def compute_trade_plan(self, row: CoinRow) -> Tuple[float, float, float, float, float]:
        """Вычислить торговый план."""
        entry = row.price_now
        
        if entry <= 0:
            return 0, 0, 0, 0, 0
        
        sl = entry * (1 + self.config.sl_pct / 100)
        tp1 = entry * (1 - self.config.tp1_pct / 100)
        tp2 = entry * (1 - self.config.tp2_pct / 100)
        
        risk = sl - entry
        reward = entry - tp1
        rr = safe_div(reward, risk, 0)
        
        return entry, sl, tp1, tp2, rr
    
    # ===== Определение типа наблюдения =====
    
    def compute_watch_type(self, row: CoinRow) -> str:
        """Определить тип наблюдения."""
        
        # Памп с коррекцией
        if row.change_24h_pct >= 15 and row.trend_1h_ppm < 0:
            return "Памп/Кор"
        
        # Рост с коррекцией
        if row.change_24h_pct >= 5 and row.trend_1h_ppm < 0:
            return "Рост/Кор"
        
        # Плато с падением
        if abs(row.change_24h_pct) < 5 and row.trend_1h_ppm < -0.01:
            return "Пл/Пад"
        
        return ""


# Singleton
_strategy: Optional[ShortExhaustionStrategy] = None


def get_strategy() -> ShortExhaustionStrategy:
    """Получить экземпляр стратегии."""
    global _strategy
    if _strategy is None:
        _strategy = ShortExhaustionStrategy()
    return _strategy
