# ============================================================
# ENGINE V2 - Новая логика отбора и трёхуровневая система сканирования
# ============================================================
# Версия: v2.0
# Дата: 02.01.2025
# ============================================================

"""
ТРЁХУРОВНЕВАЯ СИСТЕМА СКАНИРОВАНИЯ
==================================

Уровень 1 (Полный пересчёт): каждые 5 минут
- Полная загрузка TOP200
- Оборот, Макс/Мин 24ч, Funding Rate
- Тренд 1ч (полный пересчёт)

Уровень 2 (Обновление цен): каждые 30 секунд
- Цены всех 200 монет (батч-запрос)
- Изменение 24ч %
- Позиция %, До хая %

Уровень 3 (Детектор пампов): каждые 10 секунд
- Импульс 5м, Импульс 1м
- Volume spike
- Слабость (BTC divergence)
- Критерий попадания
"""

import time
import math
import traceback
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

# Импорт конфигурации
try:
    from core.config_v2 import *
except ImportError:
    # Fallback значения
    USE_NEW_ALGORITHMS = True
    CLASSIC_RANGE_POSITION_MIN = 70
    CLASSIC_CHANGE_24H_MIN = 3.0
    PUMP_5M_CHANGE_MIN = 3.0
    PUMP_5M_VOLUME_SPIKE_MIN = 2.0
    PUMP_1M_CHANGE_MIN = 2.0
    PUMP_1M_VOLUME_SPIKE_MIN = 3.0
    MIN_TURNOVER_24H_M = 5
    RW_BLOCK_THRESHOLD = 0.0


@dataclass
class ScanMetrics:
    """Метрики для новой системы скоринга."""
    # Базовые (из тикеров)
    price_now: float = 0.0
    high_24h: float = 0.0
    low_24h: float = 0.0
    change_24h_pct: float = 0.0
    range_position: float = 0.0
    dist_to_high_pct: float = 0.0
    funding_rate: float = 0.0
    turnover_24h_m: float = 0.0
    
    # Новые метрики (из свечей)
    change_5m: float = 0.0           # Импульс за 5 минут
    change_1m: float = 0.0           # Импульс за 1 минуту
    volume_spike: float = 0.0        # Текущий объём / средний
    volume_declining: bool = False   # Объём падает при росте цены
    
    # Относительная слабость
    btc_div_1h: float = 0.0          # Дивергенция к BTC за 1ч
    btc_div_3h: float = 0.0          # Дивергенция к BTC за 3ч
    
    # Тренды
    trend_1h: float = 0.0            # Направление тренда 1ч
    trend_3h: float = 0.0            # Направление тренда 3ч
    
    # Расчётные
    exhaustion: float = 0.0          # Истощение покупателей (0-1)
    z_score: float = 0.0             # Статистическая перекупленность
    volatility: float = 0.0          # Волатильность
    
    # Скоринг
    score: float = 0.0               # Итоговый скор (0-100)
    quality_stars: int = 0           # Качество (1-5 звёзд)
    
    # Критерий попадания
    criteria_type: str = ""          # КЛАСС / ПАМП-5м / ЭКСТР-1м / КОМБО
    criteria_passed: bool = False    # Прошёл отбор


@dataclass
class ScanState:
    """Состояние сканера для отслеживания уровней."""
    # Временные метки последних обновлений
    level1_last_update: float = 0.0
    level2_last_update: float = 0.0
    level3_last_update: float = 0.0
    
    # Счётчики для UI
    level1_remaining_sec: int = 0
    level2_remaining_sec: int = 0
    level3_remaining_sec: int = 0
    
    # Статус сканирования
    level1_in_progress: bool = False
    level2_in_progress: bool = False
    level3_in_progress: bool = False
    
    # Кэш данных
    btc_data: Dict = field(default_factory=dict)
    tickers_cache: List = field(default_factory=list)
    klines_cache: Dict = field(default_factory=dict)




def _v2_trace(context: str, exc: BaseException) -> None:
    """Print a detailed traceback to terminal (and let outer logger handle file writes).
    Engine-level helper: never raises.
    """
    try:
        print(f"[ENGINE_V2][ERROR] {context}: {exc}")
        print(traceback.format_exc())
    except Exception:
        pass

# Глобальное состояние сканера
_scan_state = ScanState()


def _ensure_scan_state_initialized() -> None:
    """Инициализирует таймстемпы уровней при первом использовании.

    В текущей версии level*_last_update по умолчанию = 0.0, из-за чего
    таймеры в UI могут всегда показывать 0с (как будто уже "просрочено").
    """
    now = time.time()
    st = _scan_state
    if st.level1_last_update <= 0:
        st.level1_last_update = now
    if st.level2_last_update <= 0:
        st.level2_last_update = now
    if st.level3_last_update <= 0:
        st.level3_last_update = now


def get_scan_state() -> ScanState:
    """Возвращает текущее состояние сканера."""
    return _scan_state


def update_scan_timers():
    """Обновляет таймеры для UI."""
    _ensure_scan_state_initialized()
    now = time.time()
    state = _scan_state
    
    # Уровень 1: каждые 5 минут (300 сек)
    elapsed1 = now - state.level1_last_update
    state.level1_remaining_sec = max(0, int(SCAN_LEVEL1_INTERVAL_SEC - elapsed1))
    
    # Уровень 2: каждые 30 секунд
    elapsed2 = now - state.level2_last_update
    state.level2_remaining_sec = max(0, int(SCAN_LEVEL2_INTERVAL_SEC - elapsed2))
    
    # Уровень 3: каждые 10 секунд
    elapsed3 = now - state.level3_last_update
    state.level3_remaining_sec = max(0, int(SCAN_LEVEL3_INTERVAL_SEC - elapsed3))


def should_run_level1() -> bool:
    """Проверяет нужно ли запускать полный пересчёт."""
    now = time.time()
    elapsed = now - _scan_state.level1_last_update
    return elapsed >= SCAN_LEVEL1_INTERVAL_SEC


def should_run_level2() -> bool:
    """Проверяет нужно ли обновлять цены."""
    now = time.time()
    elapsed = now - _scan_state.level2_last_update
    return elapsed >= SCAN_LEVEL2_INTERVAL_SEC


def should_run_level3() -> bool:
    """Проверяет нужно ли запускать детектор пампов."""
    now = time.time()
    elapsed = now - _scan_state.level3_last_update
    return elapsed >= SCAN_LEVEL3_INTERVAL_SEC


# ============================================================
# РАСЧЁТ НОВЫХ МЕТРИК
# ============================================================

def calculate_change_5m(klines_1m: List[Dict]) -> float:
    """Рассчитывает изменение за 5 минут из 1м свечей."""
    if not klines_1m or len(klines_1m) < 5:
        return 0.0
    try:
        price_now = klines_1m[-1]["close"]
        price_5m_ago = klines_1m[-5]["close"]
        if price_5m_ago > 0:
            return ((price_now - price_5m_ago) / price_5m_ago) * 100
    except (KeyError, IndexError, ZeroDivisionError):
        pass
    return 0.0


def calculate_change_1m(klines_1m: List[Dict]) -> float:
    """Рассчитывает изменение за 1 минуту."""
    if not klines_1m or len(klines_1m) < 2:
        return 0.0
    try:
        price_now = klines_1m[-1]["close"]
        price_1m_ago = klines_1m[-2]["close"]
        if price_1m_ago > 0:
            return ((price_now - price_1m_ago) / price_1m_ago) * 100
    except (KeyError, IndexError, ZeroDivisionError):
        pass
    return 0.0


def calculate_volume_spike(klines: List[Dict], lookback: int = 20) -> float:
    """Рассчитывает отношение текущего объёма к среднему."""
    if not klines or len(klines) < 2:
        return 1.0
    try:
        current_volume = klines[-1]["volume"]
        
        # Средний объём за lookback свечей (исключая текущую)
        history = klines[-lookback-1:-1] if len(klines) > lookback else klines[:-1]
        if not history:
            return 1.0
            
        avg_volume = sum(k["volume"] for k in history) / len(history)
        
        if avg_volume > 0:
            return current_volume / avg_volume
    except (KeyError, IndexError, ZeroDivisionError):
        pass
    return 1.0


def calculate_volume_declining(klines: List[Dict], n_candles: int = 3) -> bool:
    """Проверяет падает ли объём при росте цены."""
    if not klines or len(klines) < n_candles + 1:
        return False
    try:
        # Проверяем последние n свечей
        last_n = klines[-n_candles:]
        
        # Цена растёт?
        price_rising = last_n[-1]["close"] > last_n[0]["close"]
        
        # Объём падает?
        volume_falling = all(
            last_n[i]["volume"] > last_n[i+1]["volume"]
            for i in range(len(last_n) - 1)
        )
        
        return price_rising and volume_falling
    except (KeyError, IndexError):
        pass
    return False


def calculate_btc_divergence(
    coin_change: float,
    btc_change: float
) -> float:
    """Рассчитывает дивергенцию к BTC."""
    return coin_change - btc_change


def calculate_exhaustion(
    volume_spike: float,
    price_momentum: float,
    high_not_updated: bool
) -> float:
    """
    Рассчитывает истощение покупателей (0-1).
    
    Высокий exhaustion = объём высокий, но цена не растёт = покупатели выдыхаются.
    """
    # Нормализуем volume_spike (2.0 = 0.5, 4.0 = 1.0)
    vol_factor = min(1.0, max(0.0, (volume_spike - 1.0) / 3.0))
    
    # Нормализуем momentum (инвертируем: высокий momentum = низкий exhaustion)
    mom_factor = max(0.0, 1.0 - abs(price_momentum) / 5.0)
    
    # Бонус если хай не обновляется
    high_bonus = 0.2 if high_not_updated else 0.0
    
    exhaustion = (vol_factor * 0.5 + mom_factor * 0.3 + high_bonus)
    return min(1.0, max(0.0, exhaustion))


def calculate_z_score(
    current_price: float,
    prices: List[float],
    period: int = 20
) -> float:
    """Рассчитывает Z-Score (статистическая перекупленность)."""
    if not prices or len(prices) < period:
        return 0.0
    try:
        sample = prices[-period:]
        mean = sum(sample) / len(sample)
        
        # Стандартное отклонение
        variance = sum((x - mean) ** 2 for x in sample) / len(sample)
        std = math.sqrt(variance) if variance > 0 else 0.0
        
        if std > 0:
            return (current_price - mean) / std
    except (ZeroDivisionError, ValueError):
        pass
    return 0.0


def calculate_trend(klines: List[Dict], period: int = 60) -> float:
    """
    Рассчитывает направление тренда (-1 до +1).
    
    Использует линейную регрессию цен закрытия.
    """
    if not klines or len(klines) < 3:
        return 0.0
    try:
        sample = klines[-period:] if len(klines) >= period else klines
        closes = [k["close"] for k in sample]
        n = len(closes)
        
        # Простая линейная регрессия
        x_mean = (n - 1) / 2
        y_mean = sum(closes) / n
        
        numerator = sum((i - x_mean) * (closes[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        
        if denominator > 0:
            slope = numerator / denominator
            # Нормализуем: положительный slope = восходящий тренд
            normalized = slope / (y_mean / 100) if y_mean > 0 else 0
            return max(-1.0, min(1.0, normalized * 10))
    except (ZeroDivisionError, ValueError):
        pass
    return 0.0


# ============================================================
# ОПРЕДЕЛЕНИЕ КРИТЕРИЯ ПОПАДАНИЯ
# ============================================================

def determine_criteria_type(metrics: ScanMetrics) -> Tuple[str, bool]:
    """
    Определяет критерий попадания во вторую таблицу.
    
    Возвращает (тип, прошёл_ли).
    """
    passed_criteria = []
    
    # Путь A: Классический
    if (metrics.range_position >= CLASSIC_RANGE_POSITION_MIN and 
        metrics.change_24h_pct >= CLASSIC_CHANGE_24H_MIN and
        metrics.turnover_24h_m >= MIN_TURNOVER_24H_M):
        passed_criteria.append("КЛАСС")
    
    # Путь B: Быстрый памп (5 минут)
    if (metrics.change_5m >= PUMP_5M_CHANGE_MIN and
        metrics.volume_spike >= PUMP_5M_VOLUME_SPIKE_MIN and
        metrics.turnover_24h_m >= MIN_TURNOVER_24H_M):
        passed_criteria.append("ПАМП-5м")
    
    # Путь C: Экстремальный памп (1 минута)
    if (metrics.change_1m >= PUMP_1M_CHANGE_MIN and
        metrics.volume_spike >= PUMP_1M_VOLUME_SPIKE_MIN and
        metrics.turnover_24h_m >= MIN_TURNOVER_24H_M):
        passed_criteria.append("ЭКСТР-1м")
    
    if not passed_criteria:
        return "", False
    
    if len(passed_criteria) > 1:
        return "КОМБО", True
    
    return passed_criteria[0], True


# ============================================================
# НОВАЯ СИСТЕМА СКОРИНГА
# ============================================================

def calculate_score_v2(metrics: ScanMetrics) -> float:
    """
    Новая система скоринга (0-100).
    
    Факторы:
    - Exhaustion (истощение): 20 баллов
    - Близость к хаю: 15 баллов
    - Тренд вниз: 10 баллов
    - Relative Weakness (ОБЯЗАТЕЛЬНЫЙ): 30 баллов
    - Funding Rate: 15-25 баллов
    - Volume spike: 10 баллов
    """
    score = 0.0
    
    # 1. Exhaustion (0-20 баллов)
    exhaustion_score = min(20.0, metrics.exhaustion * 20 / 0.7)
    score += exhaustion_score
    
    # 2. Близость к хаю (0-15 баллов)
    # dist_to_high = 0% -> 15 баллов, dist = 10% -> 0 баллов
    near_high_score = max(0.0, 15.0 - metrics.dist_to_high_pct * 1.5)
    score += near_high_score
    
    # 3. Тренд вниз (0-10 баллов)
    # trend < 0 -> до 10 баллов
    if metrics.trend_1h < 0:
        trend_score = min(10.0, abs(metrics.trend_1h) * 10)
        score += trend_score
    
    # 4. Relative Weakness (ОБЯЗАТЕЛЬНЫЙ ФИЛЬТР, 0-30 баллов)
    if metrics.btc_div_1h <= RW_BLOCK_THRESHOLD:
        # Прошёл фильтр
        if metrics.btc_div_1h <= RW_EXCELLENT_THRESHOLD:
            rw_score = 30.0
        elif metrics.btc_div_1h <= RW_GOOD_THRESHOLD:
            rw_score = 25.0
        else:
            rw_score = 15.0
        score += rw_score
    else:
        # НЕ прошёл фильтр - максимум 29 баллов (статус Наблюдение)
        return min(29.0, score)
    
    # 5. Funding Rate (0-25 баллов)
    if metrics.funding_rate > 0.0015:  # > 0.15%
        score += FUNDING_BONUS_EXTREME
    elif metrics.funding_rate > 0.0008:  # > 0.08%
        score += FUNDING_BONUS_HIGH
    elif metrics.funding_rate > 0:
        score += 5.0
    
    # 6. Volume spike (0-10 баллов)
    if metrics.volume_spike >= VOLUME_SPIKE_EXTREME:
        score += VOLUME_SPIKE_BONUS
    elif metrics.volume_spike >= VOLUME_SPIKE_GOOD:
        score += 7.0
    elif metrics.volume_spike >= VOLUME_SPIKE_MIN:
        score += 4.0
    
    # Бонус за Z-Score
    if metrics.z_score >= ZSCORE_EXTREME:
        score += ZSCORE_BONUS
    elif metrics.z_score >= ZSCORE_OVERBOUGHT:
        score += 3.0
    
    return min(100.0, max(0.0, score))


def calculate_quality_stars(metrics: ScanMetrics) -> int:
    """
    Рассчитывает качество сигнала (1-5 звёзд).
    
    Факторы:
    1. Exhaustion > 0.6
    2. RW 1h < -2%
    3. RW 3h < RW 1h (усиливается)
    4. Volume declining
    5. Z-Score > 2.0
    6. Funding > 0.1%
    """
    factors_passed = 0
    
    if metrics.exhaustion >= EXHAUSTION_GOOD:
        factors_passed += 1
    
    if metrics.btc_div_1h <= RW_EXCELLENT_THRESHOLD:
        factors_passed += 1
    
    if metrics.btc_div_3h < metrics.btc_div_1h:  # Слабость усиливается
        factors_passed += 1
    
    if metrics.volume_declining:
        factors_passed += 1
    
    if metrics.z_score >= ZSCORE_OVERBOUGHT:
        factors_passed += 1
    
    if metrics.funding_rate > 0.001:  # > 0.1%
        factors_passed += 1
    
    # Определяем звёзды
    if factors_passed >= QUALITY_5_STARS_MIN_FACTORS:
        return 5
    elif factors_passed >= QUALITY_4_STARS_MIN_FACTORS:
        return 4
    elif factors_passed >= QUALITY_3_STARS_MIN_FACTORS:
        return 3
    elif factors_passed >= QUALITY_2_STARS_MIN_FACTORS:
        return 2
    elif factors_passed >= QUALITY_1_STAR_MIN_FACTORS:
        return 1
    return 0


def determine_status_v2(score: float) -> str:
    """Определяет статус по скору."""
    if score >= STATUS_THRESHOLD_READY:
        return "Готовность"
    elif score >= STATUS_THRESHOLD_INTEREST:
        return "Интерес"
    elif score >= STATUS_THRESHOLD_WATCH:
        return "Наблюдение"
    return ""


# ============================================================
# ОСНОВНЫЕ ФУНКЦИИ СКАНИРОВАНИЯ
# ============================================================

def process_ticker_data(ticker: Dict, btc_ticker: Optional[Dict] = None) -> ScanMetrics:
    """Обрабатывает данные тикера и создаёт базовые метрики."""
    metrics = ScanMetrics()
    
    try:
        metrics.price_now = float(ticker.get("lastPrice", 0) or 0)
        metrics.high_24h = float(ticker.get("highPrice24h", 0) or 0)
        metrics.low_24h = float(ticker.get("lowPrice24h", 0) or 0)
        
        # Изменение за 24ч
        change_pct = ticker.get("price24hPcnt")
        if change_pct:
            metrics.change_24h_pct = float(change_pct) * 100
        
        # Оборот
        turnover = float(ticker.get("turnover24h", 0) or 0)
        metrics.turnover_24h_m = turnover / 1_000_000
        
        # Funding rate
        metrics.funding_rate = float(ticker.get("fundingRate", 0) or 0)
        
        # Позиция в диапазоне
        if metrics.high_24h > metrics.low_24h:
            range_val = metrics.high_24h - metrics.low_24h
            metrics.range_position = ((metrics.price_now - metrics.low_24h) / range_val) * 100
            metrics.dist_to_high_pct = ((metrics.high_24h - metrics.price_now) / metrics.high_24h) * 100
        
        # BTC дивергенция за 24ч (базовая)
        if btc_ticker:
            btc_change = float(btc_ticker.get("price24hPcnt", 0) or 0) * 100
            metrics.btc_div_1h = metrics.change_24h_pct - btc_change  # Упрощение для Level 2
            
    except (ValueError, TypeError, KeyError):
        pass
    
    return metrics


def enrich_with_klines(
    metrics: ScanMetrics,
    klines_1m: List[Dict],
    klines_5m: List[Dict],
    btc_klines_1m: Optional[List[Dict]] = None
) -> ScanMetrics:
    """Обогащает метрики данными из свечей (Level 3)."""
    
    # Импульсы
    metrics.change_5m = calculate_change_5m(klines_1m)
    metrics.change_1m = calculate_change_1m(klines_1m)
    
    # Volume spike
    metrics.volume_spike = calculate_volume_spike(klines_1m)
    
    # Volume declining
    metrics.volume_declining = calculate_volume_declining(klines_1m)
    
    # Тренды
    metrics.trend_1h = calculate_trend(klines_1m, period=60)
    if klines_5m:
        metrics.trend_3h = calculate_trend(klines_5m, period=36)
    
    # Z-Score
    if klines_1m:
        closes = [k["close"] for k in klines_1m]
        metrics.z_score = calculate_z_score(metrics.price_now, closes)
    
    # Exhaustion
    price_momentum = metrics.change_5m
    high_not_updated = False
    if klines_1m and len(klines_1m) >= 3:
        recent_highs = [k["high"] for k in klines_1m[-3:]]
        high_not_updated = recent_highs[-1] <= max(recent_highs[:-1])
    
    metrics.exhaustion = calculate_exhaustion(
        metrics.volume_spike,
        price_momentum,
        high_not_updated
    )
    
    # BTC дивергенция (точная)
    if btc_klines_1m and len(btc_klines_1m) >= 60:
        btc_change_1h = calculate_change_5m(btc_klines_1m[-60:])  # Упрощение
        coin_change_1h = calculate_change_5m(klines_1m[-60:]) if len(klines_1m) >= 60 else metrics.change_5m
        metrics.btc_div_1h = calculate_btc_divergence(coin_change_1h, btc_change_1h)
    
    # Критерий попадания
    criteria_type, criteria_passed = determine_criteria_type(metrics)
    metrics.criteria_type = criteria_type
    metrics.criteria_passed = criteria_passed
    
    # Скор и качество
    metrics.score = calculate_score_v2(metrics)
    metrics.quality_stars = calculate_quality_stars(metrics)
    
    return metrics


def mark_level_complete(level: int):
    """Отмечает завершение уровня сканирования."""
    now = time.time()
    state = _scan_state
    
    if level == 1:
        state.level1_last_update = now
        state.level1_in_progress = False
    elif level == 2:
        state.level2_last_update = now
        state.level2_in_progress = False
    elif level == 3:
        state.level3_last_update = now
        state.level3_in_progress = False


def mark_level_started(level: int):
    """Отмечает начало уровня сканирования."""
    state = _scan_state
    
    if level == 1:
        state.level1_in_progress = True
    elif level == 2:
        state.level2_in_progress = True
    elif level == 3:
        state.level3_in_progress = True
