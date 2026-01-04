# ===== core/math_utils.py =====
# Базовые математические функции
# ==============================

import math
from typing import List, Dict, Optional, Tuple


def clamp(x: float, lo: float, hi: float) -> float:
    """Ограничение значения в диапазоне."""
    return max(lo, min(hi, x))


def safe_div(a: float, b: float, default: float = 0.0) -> float:
    """Безопасное деление."""
    return a / b if b != 0 else default


def pct(a: float, b: float) -> float:
    """Процентное изменение от a к b."""
    return safe_div(b - a, a, 0.0) * 100


def pct_change(old: float, new: float) -> float:
    """Процентное изменение."""
    if old == 0:
        return 0.0
    return (new - old) / old * 100


def down(x: float) -> float:
    """Отрицательная часть (для трендов)."""
    return min(0.0, x)


def up(x: float) -> float:
    """Положительная часть (для трендов)."""
    return max(0.0, x)


def log1p_norm(x: float, denom: float) -> float:
    """Нормализация через логарифм."""
    return math.log1p(x) / math.log1p(denom) if denom > 0 else 0.0


def sigmoid(x: float, k: float = 1.0) -> float:
    """Сигмоида для нормализации."""
    return 1 / (1 + math.exp(-k * x))


def normalize_score(value: float, min_val: float, max_val: float) -> float:
    """Нормализация значения в диапазон 0-100."""
    if max_val <= min_val:
        return 50.0
    return clamp((value - min_val) / (max_val - min_val) * 100, 0, 100)


# ===== Ценовые функции =====

def fmt_price(x: float) -> str:
    """Форматирование цены."""
    if x == 0:
        return "0"
    if x >= 1000:
        return f"{x:,.0f}"
    if x >= 1:
        return f"{x:.2f}"
    if x >= 0.01:
        return f"{x:.4f}"
    return f"{x:.6f}"


def range_position(price: float, low: float, high: float) -> float:
    """Позиция цены в диапазоне low-high (0-100%)."""
    if high <= low:
        return 50.0
    return clamp((price - low) / (high - low) * 100, 0, 100)


def dist_to_high_pct(price: float, high: float) -> float:
    """Расстояние до хая в процентах."""
    if price <= 0:
        return 0.0
    return (high - price) / price * 100


def dist_to_low_pct(price: float, low: float) -> float:
    """Расстояние до лоу в процентах."""
    if price <= 0:
        return 0.0
    return (price - low) / price * 100


# ===== Функции для свечей =====

def local_high(klines: List[Dict], lookback: int = 24) -> float:
    """Локальный максимум за lookback свечей."""
    if not klines:
        return 0.0
    subset = klines[-lookback:] if len(klines) >= lookback else klines
    return max(float(k.get("high", 0) or k.get("h", 0) or 0) for k in subset)


def local_low(klines: List[Dict], lookback: int = 24) -> float:
    """Локальный минимум за lookback свечей."""
    if not klines:
        return 0.0
    subset = klines[-lookback:] if len(klines) >= lookback else klines
    return min(float(k.get("low", 0) or k.get("l", 0) or 0) for k in subset)


def close_hours_ago(klines_1h: List[Dict], hours: int) -> Optional[float]:
    """Цена закрытия N часов назад."""
    if not klines_1h or len(klines_1h) < hours:
        return None
    idx = -(hours + 1)
    if abs(idx) > len(klines_1h):
        return None
    candle = klines_1h[idx]
    return float(candle.get("close", 0) or candle.get("c", 0) or 0)


def trend_ppm(close_then: float, close_now: float, minutes: int) -> float:
    """Тренд в % за минуту (ppm = percent per minute)."""
    if close_then <= 0 or minutes <= 0:
        return 0.0
    return pct_change(close_then, close_now) / minutes


# ===== Структурный анализ =====

def structure_score_from_candles(klines: List[Dict], n: int = 6) -> float:
    """
    Оценка структуры свечей (0-100).
    Высокий скор = больше красных свечей = подтверждение падения.
    """
    if not klines or len(klines) < n:
        return 50.0
    
    subset = klines[-n:]
    red_count = 0
    
    for k in subset:
        o = float(k.get("open", 0) or k.get("o", 0) or 0)
        c = float(k.get("close", 0) or k.get("c", 0) or 0)
        if c < o:
            red_count += 1
    
    return red_count / n * 100


def body_size_ratio(kline: Dict) -> float:
    """Отношение тела свечи к полному размеру (0-1)."""
    o = float(kline.get("open", 0) or kline.get("o", 0) or 0)
    c = float(kline.get("close", 0) or kline.get("c", 0) or 0)
    h = float(kline.get("high", 0) or kline.get("h", 0) or 0)
    l = float(kline.get("low", 0) or kline.get("l", 0) or 0)
    
    body = abs(c - o)
    full = h - l
    
    return safe_div(body, full, 0.5)


def is_doji(kline: Dict, threshold: float = 0.1) -> bool:
    """Проверка на доджи (маленькое тело)."""
    return body_size_ratio(kline) < threshold


def is_hammer(kline: Dict) -> bool:
    """Проверка на молот (длинная нижняя тень)."""
    o = float(kline.get("open", 0) or kline.get("o", 0) or 0)
    c = float(kline.get("close", 0) or kline.get("c", 0) or 0)
    h = float(kline.get("high", 0) or kline.get("h", 0) or 0)
    l = float(kline.get("low", 0) or kline.get("l", 0) or 0)
    
    body = abs(c - o)
    lower_shadow = min(o, c) - l
    upper_shadow = h - max(o, c)
    
    return lower_shadow > body * 2 and upper_shadow < body


# ===== Уровни поддержки/сопротивления =====

def local_extrema_levels(klines: List[Dict]) -> Tuple[List[float], List[float]]:
    """
    Находит локальные экстремумы.
    Returns: (highs, lows)
    """
    if len(klines) < 3:
        return [], []
    
    highs, lows = [], []
    
    for i in range(1, len(klines) - 1):
        h_prev = float(klines[i-1].get("high", 0) or 0)
        h_curr = float(klines[i].get("high", 0) or 0)
        h_next = float(klines[i+1].get("high", 0) or 0)
        
        l_prev = float(klines[i-1].get("low", 0) or 0)
        l_curr = float(klines[i].get("low", 0) or 0)
        l_next = float(klines[i+1].get("low", 0) or 0)
        
        if h_curr > h_prev and h_curr > h_next:
            highs.append(h_curr)
        if l_curr < l_prev and l_curr < l_next:
            lows.append(l_curr)
    
    return highs, lows


def cluster_levels(levels: List[float], merge_pct: float = 0.5) -> List[float]:
    """
    Кластеризация уровней (объединение близких).
    """
    if not levels:
        return []
    
    sorted_levels = sorted(levels)
    clusters = []
    cluster = [sorted_levels[0]]
    
    for level in sorted_levels[1:]:
        if cluster and (level - cluster[-1]) / cluster[-1] * 100 < merge_pct:
            cluster.append(level)
        else:
            clusters.append(sum(cluster) / len(cluster))
            cluster = [level]
    
    if cluster:
        clusters.append(sum(cluster) / len(cluster))
    
    return clusters


def compute_support_resistance(
    klines: List[Dict], 
    price_now: float
) -> Tuple[List[float], List[float]]:
    """
    Вычисляет уровни поддержки и сопротивления.
    Returns: (supports, resistances)
    """
    highs, lows = local_extrema_levels(klines)
    
    all_highs = cluster_levels(highs)
    all_lows = cluster_levels(lows)
    
    resistances = sorted([h for h in all_highs if h > price_now])
    supports = sorted([l for l in all_lows if l < price_now], reverse=True)
    
    return supports[:3], resistances[:3]
