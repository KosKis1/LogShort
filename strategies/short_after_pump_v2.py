# ============================================================
# SHORT AFTER PUMP V2 - Новые алгоритмы для шорт-позиций
# ============================================================
# Версия: v2.0
# Дата: 02.01.2025
# ============================================================

"""
ТОП-3 АЛГОРИТМА ДЛЯ ШОРТ-ПОЗИЦИЙ
================================

🥇 Momentum Exhaustion / Pump Pullback (ядро системы)
- Volume spike → цена перестаёт расти
- ATR расширен
- High не обновляется / структура ломается
- Лучший баланс winrate + RR, ловит распределение

🥈 Relative Weakness Filter (обязательный фильтр)
- Монета слабее BTC
- Хуже своего сектора
- Объём не поддерживает рост
- Резко снижает ложные входы

🥉 Funding Rate Extremes (уникально для крипты)
- Funding Rate > 0.1% (экстремально положительный)
- Open Interest на ATH
- Высокая вероятность каскадного закрытия лонгов
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
import time
import math

# Импорт конфигурации
try:
    from core.config_v2 import *
except ImportError:
    # Fallback значения
    EXHAUSTION_MIN = 0.3
    EXHAUSTION_GOOD = 0.5
    EXHAUSTION_EXCELLENT = 0.7
    RW_BLOCK_THRESHOLD = 0.0
    RW_GOOD_THRESHOLD = -1.0
    RW_EXCELLENT_THRESHOLD = -2.0
    VOLUME_SPIKE_MIN = 1.5
    VOLUME_SPIKE_GOOD = 2.0
    STATUS_THRESHOLD_WATCH = 30
    STATUS_THRESHOLD_INTEREST = 55
    STATUS_THRESHOLD_READY = 75
    TTL_CLASSIC_MIN = 30
    TTL_PUMP_5M_MIN = 10
    TTL_PUMP_1M_MIN = 5


@dataclass
class SignalResult:
    """Результат анализа сигнала."""
    # Основные
    symbol: str
    status: str = ""              # Наблюдение / Интерес / Готовность / ВХОД
    signal_text: str = ""         # Текстовое описание сигнала
    score: float = 0.0            # Скор (0-100)
    quality_stars: int = 0        # Качество (1-5 звёзд)
    
    # Критерий попадания
    criteria_type: str = ""       # КЛАСС / ПАМП-5м / ЭКСТР-1м / КОМБО
    
    # Алгоритмы
    momentum_exhaustion: float = 0.0   # Результат алгоритма 1
    relative_weakness: float = 0.0     # Результат алгоритма 2
    funding_score: float = 0.0         # Результат алгоритма 3
    
    # Детали
    exhaustion: float = 0.0
    btc_div_1h: float = 0.0
    btc_div_3h: float = 0.0
    volume_spike: float = 0.0
    volume_declining: bool = False
    z_score: float = 0.0
    funding_rate: float = 0.0
    
    # Торговые уровни
    entry_price: float = 0.0
    sl_price: float = 0.0
    tp1_price: float = 0.0
    tp2_price: float = 0.0
    rr_ratio: float = 0.0
    
    # TTL
    ttl_minutes: float = 30.0
    added_at: float = 0.0
    
    # Флаги
    rw_passed: bool = False       # Прошёл фильтр Relative Weakness
    all_conditions_met: bool = False


class ShortAfterPumpV2:
    """
    Новая стратегия для шорт-позиций после пампа.
    
    Использует трёхуровневую систему алгоритмов:
    1. Momentum Exhaustion (ядро)
    2. Relative Weakness (обязательный фильтр)
    3. Funding Rate Extremes (бонус)
    """
    
    def __init__(self):
        self.name = "ShortAfterPumpV2"
        self._cache = {}  # symbol -> SignalResult
        
    def analyze(
        self,
        symbol: str,
        price_now: float,
        high_24h: float,
        low_24h: float,
        change_24h_pct: float,
        range_position: float,
        dist_to_high_pct: float,
        funding_rate: float,
        klines_1m: List[Dict],
        klines_5m: List[Dict],
        btc_change_1h: float = 0.0,
        btc_change_3h: float = 0.0,
        criteria_type: str = "",
    ) -> SignalResult:
        """
        Анализирует монету и возвращает результат.
        """
        result = SignalResult(symbol=symbol)
        result.criteria_type = criteria_type
        result.added_at = time.time()
        result.funding_rate = funding_rate
        
        # === АЛГОРИТМ 1: Momentum Exhaustion ===
        exhaustion_score, exhaustion_details = self._check_momentum_exhaustion(
            klines_1m, klines_5m, price_now, high_24h
        )
        result.momentum_exhaustion = exhaustion_score
        result.exhaustion = exhaustion_details.get("exhaustion", 0.0)
        result.volume_spike = exhaustion_details.get("volume_spike", 0.0)
        result.volume_declining = exhaustion_details.get("volume_declining", False)
        
        # === АЛГОРИТМ 2: Relative Weakness (ОБЯЗАТЕЛЬНЫЙ) ===
        rw_score, rw_passed = self._check_relative_weakness(
            change_24h_pct, btc_change_1h, btc_change_3h, klines_1m
        )
        result.relative_weakness = rw_score
        result.rw_passed = rw_passed
        result.btc_div_1h = change_24h_pct - btc_change_1h  # Упрощение
        result.btc_div_3h = change_24h_pct - btc_change_3h  # Упрощение
        
        # === АЛГОРИТМ 3: Funding Rate Extremes ===
        funding_score = self._check_funding_rate(funding_rate)
        result.funding_score = funding_score
        
        # === Z-Score ===
        result.z_score = self._calculate_z_score(klines_1m, price_now)
        
        # === РАСЧЁТ ИТОГОВОГО СКОРА ===
        result.score = self._calculate_total_score(
            exhaustion_score=exhaustion_score,
            rw_score=rw_score,
            rw_passed=rw_passed,
            funding_score=funding_score,
            near_high_pct=dist_to_high_pct,
            z_score=result.z_score
        )
        
        # === ОПРЕДЕЛЕНИЕ СТАТУСА ===
        result.status = self._determine_status(result.score, rw_passed)
        
        # === КАЧЕСТВО СИГНАЛА ===
        result.quality_stars = self._calculate_quality(result)
        
        # === ТОРГОВЫЕ УРОВНИ ===
        if result.status in ("Готовность", "ВХОД"):
            entry, sl, tp1, tp2, rr = self._calculate_levels(
                price_now, high_24h, low_24h
            )
            result.entry_price = entry
            result.sl_price = sl
            result.tp1_price = tp1
            result.tp2_price = tp2
            result.rr_ratio = rr
        
        # === TTL ===
        result.ttl_minutes = self._get_ttl(criteria_type, result.status)
        
        # === СИГНАЛ ТЕКСТ ===
        result.signal_text = self._generate_signal_text(result)
        
        # === ПРОВЕРКА ВСЕХ УСЛОВИЙ ВХОДА ===
        result.all_conditions_met = self._check_entry_conditions(result)
        
        # Кэшируем результат
        self._cache[symbol] = result
        
        return result
    
    def _check_momentum_exhaustion(
        self,
        klines_1m: List[Dict],
        klines_5m: List[Dict],
        price_now: float,
        high_24h: float
    ) -> Tuple[float, Dict]:
        """
        Алгоритм 1: Momentum Exhaustion / Pump Pullback
        
        Условия:
        - Volume spike (объём > 2x средний за 20 периодов)
        - Цена растёт < 0.5% при max объёме
        - High не обновляется 3+ свечи
        """
        details = {
            "exhaustion": 0.0,
            "volume_spike": 1.0,
            "volume_declining": False,
            "high_not_updated": False,
            "price_stall": False
        }
        
        if not klines_1m or len(klines_1m) < 20:
            return 0.0, details
        
        # 1. Volume spike
        try:
            current_vol = klines_1m[-1]["volume"]
            avg_vol = sum(k["volume"] for k in klines_1m[-21:-1]) / 20
            volume_spike = current_vol / avg_vol if avg_vol > 0 else 1.0
            details["volume_spike"] = volume_spike
        except (KeyError, ZeroDivisionError):
            volume_spike = 1.0
        
        # 2. Volume declining (объём падает при росте цены)
        try:
            last_3 = klines_1m[-3:]
            price_rising = last_3[-1]["close"] > last_3[0]["close"]
            vol_falling = last_3[-1]["volume"] < last_3[-2]["volume"] < last_3[-3]["volume"]
            details["volume_declining"] = price_rising and vol_falling
        except (KeyError, IndexError):
            pass
        
        # 3. High не обновляется
        try:
            last_5 = klines_1m[-5:]
            highs = [k["high"] for k in last_5]
            max_high = max(highs[:-1])
            details["high_not_updated"] = highs[-1] <= max_high
        except (KeyError, IndexError):
            pass
        
        # 4. Price stall (цена застопорилась)
        try:
            change_5m = (klines_1m[-1]["close"] - klines_1m[-5]["close"]) / klines_1m[-5]["close"] * 100
            details["price_stall"] = abs(change_5m) < 0.5 and volume_spike > 1.5
        except (KeyError, ZeroDivisionError):
            pass
        
        # Расчёт exhaustion
        exhaustion = 0.0
        
        # Высокий объём без роста цены
        if volume_spike >= 2.0 and details["price_stall"]:
            exhaustion += 0.4
        elif volume_spike >= 1.5:
            exhaustion += 0.2
        
        # High не обновляется
        if details["high_not_updated"]:
            exhaustion += 0.2
        
        # Volume declining при росте
        if details["volume_declining"]:
            exhaustion += 0.3
        
        # Близко к high_24h
        if price_now > 0 and high_24h > 0:
            dist = (high_24h - price_now) / high_24h * 100
            if dist < 2.0:
                exhaustion += 0.1
        
        details["exhaustion"] = min(1.0, exhaustion)
        
        # Скор алгоритма (0-40)
        score = min(40.0, exhaustion * 40 / 0.7)
        
        return score, details
    
    def _check_relative_weakness(
        self,
        change_24h: float,
        btc_change_1h: float,
        btc_change_3h: float,
        klines_1m: List[Dict]
    ) -> Tuple[float, bool]:
        """
        Алгоритм 2: Relative Weakness Filter
        
        Условия:
        - Монета слабее BTC минимум на 1-2%
        - Слабость усиливается (RW 3h < RW 1h)
        - Volume Ratio падает
        
        ОБЯЗАТЕЛЬНЫЙ ФИЛЬТР: если монета сильнее BTC -> блокируем!
        """
        # Расчёт дивергенции за 1 час
        # Упрощение: используем change_24h как прокси
        btc_div_1h = change_24h - btc_change_1h
        btc_div_3h = change_24h - btc_change_3h
        
        # БЛОК: если сильнее BTC
        if btc_div_1h > RW_BLOCK_THRESHOLD:
            return 0.0, False  # НЕ прошёл фильтр
        
        # Скор за слабость
        score = 0.0
        
        if btc_div_1h <= RW_EXCELLENT_THRESHOLD:  # < -2%
            score = 30.0
        elif btc_div_1h <= RW_GOOD_THRESHOLD:  # < -1%
            score = 25.0
        else:
            score = 15.0
        
        # Бонус: слабость усиливается
        if btc_div_3h < btc_div_1h:
            score += 5.0
        
        return min(35.0, score), True
    
    def _check_funding_rate(self, funding_rate: float) -> float:
        """
        Алгоритм 3: Funding Rate Extremes
        
        Условия:
        - FR > 0.08% = повышенный (15 баллов)
        - FR > 0.15% = экстремальный (25 баллов)
        """
        if funding_rate > 0.0015:  # > 0.15%
            return 25.0
        elif funding_rate > 0.0008:  # > 0.08%
            return 15.0
        elif funding_rate > 0:
            return 5.0
        return 0.0
    
    def _calculate_z_score(self, klines: List[Dict], current_price: float) -> float:
        """Рассчитывает Z-Score."""
        if not klines or len(klines) < 20:
            return 0.0
        try:
            closes = [k["close"] for k in klines[-20:]]
            mean = sum(closes) / len(closes)
            variance = sum((x - mean) ** 2 for x in closes) / len(closes)
            std = math.sqrt(variance) if variance > 0 else 0.0
            if std > 0:
                return (current_price - mean) / std
        except (KeyError, ZeroDivisionError, ValueError):
            pass
        return 0.0
    
    def _calculate_total_score(
        self,
        exhaustion_score: float,
        rw_score: float,
        rw_passed: bool,
        funding_score: float,
        near_high_pct: float,
        z_score: float
    ) -> float:
        """Рассчитывает итоговый скор (0-100)."""
        
        # Если не прошёл RW - максимум 29 баллов
        if not rw_passed:
            return min(29.0, exhaustion_score * 0.5)
        
        score = 0.0
        
        # Exhaustion (max 40)
        score += exhaustion_score
        
        # Relative Weakness (max 35)
        score += rw_score
        
        # Funding Rate (max 25)
        score += funding_score
        
        # Близость к хаю (бонус max 10)
        if near_high_pct < 2.0:
            score += 10.0
        elif near_high_pct < 5.0:
            score += 5.0
        
        # Z-Score бонус (max 5)
        if z_score >= 2.5:
            score += 5.0
        elif z_score >= 2.0:
            score += 3.0
        
        return min(100.0, max(0.0, score))
    
    def _determine_status(self, score: float, rw_passed: bool) -> str:
        """Определяет статус по скору."""
        if not rw_passed:
            return "Наблюдение"
        
        if score >= STATUS_THRESHOLD_READY:
            return "Готовность"
        elif score >= STATUS_THRESHOLD_INTEREST:
            return "Интерес"
        elif score >= STATUS_THRESHOLD_WATCH:
            return "Наблюдение"
        return ""
    
    def _calculate_quality(self, result: SignalResult) -> int:
        """Рассчитывает качество сигнала (1-5 звёзд)."""
        factors = 0
        
        if result.exhaustion >= EXHAUSTION_GOOD:
            factors += 1
        
        if result.btc_div_1h <= RW_EXCELLENT_THRESHOLD:
            factors += 1
        
        if result.btc_div_3h < result.btc_div_1h:
            factors += 1
        
        if result.volume_declining:
            factors += 1
        
        if result.z_score >= 2.0:
            factors += 1
        
        if result.funding_rate > 0.001:
            factors += 1
        
        if factors >= 6:
            return 5
        elif factors >= 5:
            return 4
        elif factors >= 4:
            return 3
        elif factors >= 3:
            return 2
        elif factors >= 2:
            return 1
        return 0
    
    def _calculate_levels(
        self,
        price_now: float,
        high_24h: float,
        low_24h: float
    ) -> Tuple[float, float, float, float, float]:
        """Рассчитывает торговые уровни."""
        if price_now <= 0:
            return 0.0, 0.0, 0.0, 0.0, 0.0
        
        # Entry: текущая цена + 0.5%
        entry = price_now * 1.005
        
        # SL: high_24h + 1%
        sl = high_24h * 1.01 if high_24h > 0 else price_now * 1.03
        
        # Risk
        risk = sl - entry
        if risk <= 0:
            return entry, sl, 0.0, 0.0, 0.0
        
        # TP1: 1.5R, TP2: 2.5R
        tp1 = entry - risk * 1.5
        tp2 = entry - risk * 2.5
        
        # R/R ratio для TP1
        rr = 1.5
        
        return entry, sl, tp1, tp2, rr
    
    def _get_ttl(self, criteria_type: str, status: str) -> float:
        """Возвращает TTL в минутах."""
        if status == "ВХОД":
            return float('inf')
        
        if criteria_type == "ЭКСТР-1м":
            return TTL_PUMP_1M_MIN
        elif criteria_type == "ПАМП-5м":
            return TTL_PUMP_5M_MIN
        else:
            return TTL_CLASSIC_MIN
    
    def _generate_signal_text(self, result: SignalResult) -> str:
        """Генерирует текстовое описание сигнала."""
        parts = []
        
        if result.exhaustion >= EXHAUSTION_GOOD:
            parts.append(f"Истощ {result.exhaustion:.2f}")
        
        if result.btc_div_1h <= RW_EXCELLENT_THRESHOLD:
            parts.append(f"Слабость {result.btc_div_1h:.1f}%")
        
        if result.volume_spike >= VOLUME_SPIKE_GOOD:
            parts.append(f"V-спайк {result.volume_spike:.1f}x")
        
        if result.funding_rate > 0.001:
            parts.append(f"FR {result.funding_rate*100:.2f}%")
        
        if result.z_score >= 2.0:
            parts.append(f"Z={result.z_score:.1f}")
        
        return ", ".join(parts) if parts else "Мониторинг"
    
    def _check_entry_conditions(self, result: SignalResult) -> bool:
        """Проверяет все условия для статуса ВХОД."""
        conditions = [
            result.rw_passed,                    # Прошёл RW фильтр
            result.exhaustion >= EXHAUSTION_MIN, # Истощение достаточное
            result.score >= STATUS_THRESHOLD_READY,  # Скор >= 75
            result.entry_price > 0,              # Есть уровни
            result.sl_price > result.entry_price,  # SL выше Entry (для шорта)
            result.rr_ratio >= 1.5,              # R/R >= 1.5
        ]
        return all(conditions)
    
    def get_cached_result(self, symbol: str) -> Optional[SignalResult]:
        """Возвращает кэшированный результат."""
        return self._cache.get(symbol)
    
    def clear_cache(self):
        """Очищает кэш."""
        self._cache.clear()


# Глобальный экземпляр стратегии
_strategy_instance = None


def get_strategy() -> ShortAfterPumpV2:
    """Возвращает глобальный экземпляр стратегии."""
    global _strategy_instance
    if _strategy_instance is None:
        _strategy_instance = ShortAfterPumpV2()
    return _strategy_instance
