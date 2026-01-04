# core/gates.py
# Система гейтов для уверенного входа в шорт
# Version: 1.0
#
# Архитектура:
#   Gate 0: Контекст рынка (BTC не растёт)
#   Gate 1: Setup (истощение у вершины)
#   Gate 2: Trigger (breakdown + failed retest)
#   Gate 3: Confidence (подтверждение давления)
#
# Вход только если ВСЕ включённые гейты пройдены.

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import time

from .params_ml import GateParams, get_params


@dataclass
class GateResult:
    """Результат проверки одного гейта"""
    passed: bool
    score: float = 0.0          # 0-100, для ранжирования
    signals: List[str] = field(default_factory=list)  # какие условия сработали
    debug: Dict = field(default_factory=dict)         # отладочная инфо


@dataclass 
class GatesResult:
    """Результат проверки всех гейтов"""
    gate0: GateResult
    gate1: GateResult
    gate2: GateResult
    gate3: GateResult
    
    # Итоговый статус
    all_passed: bool = False
    status: str = ""            # "ВХОД" / "Готовность" / "Интерес" / "Наблюдение" / ""
    signal_text: str = ""       # человекочитаемое описание
    
    # Торговые уровни (если all_passed)
    entry_price: float = 0.0
    sl_price: float = 0.0
    tp1_price: float = 0.0
    tp2_price: float = 0.0
    tp3_price: float = 0.0
    rr_ratio: float = 0.0
    
    # Для ML логирования
    timestamp: int = 0
    symbol: str = ""
    params_version: int = 1


# ============================================================
# GATE 0: Контекст рынка
# ============================================================

def check_gate0(
    btc_trend_1h: float,
    alt_change_24h: float,
    btc_change_24h: float,
    params: GateParams
) -> GateResult:
    """
    Gate 0: Контекст рынка
    
    Проверяет:
    1. BTC не растёт сильно (trend <= threshold)
    2. ИЛИ альт растёт значительно больше BTC (divergence)
    
    Returns: GateResult
    """
    if not params.gate0_enabled:
        return GateResult(passed=True, score=100, signals=["disabled"])
    
    signals = []
    score = 0.0
    
    # Условие 1: BTC не растёт
    btc_ok = btc_trend_1h <= params.btc_trend_max
    if btc_ok:
        signals.append(f"BTC_trend={btc_trend_1h:.2f}%<=max")
        score += 50
    
    # Условие 2: Дивергенция (альт >> BTC)
    divergence = alt_change_24h - btc_change_24h
    div_ok = divergence >= params.divergence_min
    if div_ok:
        signals.append(f"divergence={divergence:.1f}%")
        score += 50
    
    passed = btc_ok or div_ok
    
    return GateResult(
        passed=passed,
        score=score,
        signals=signals,
        debug={
            "btc_trend_1h": btc_trend_1h,
            "btc_change_24h": btc_change_24h,
            "alt_change_24h": alt_change_24h,
            "divergence": divergence,
            "btc_ok": btc_ok,
            "div_ok": div_ok,
        }
    )


# ============================================================
# GATE 1: Setup (истощение у вершины)
# ============================================================

def check_gate1(
    candles_5m: List[Dict],
    params: GateParams
) -> GateResult:
    """
    Gate 1: Setup — Вершина сформирована
    
    Проверяет (нужно 2 из 3):
    1. Истощение свечами (длинные верхние тени)
    2. High не растёт (нет прогресса)
    3. Close падает при стабильном high
    
    candles_5m: список свечей [{ts, open, high, low, close, volume}, ...]
                отсортирован от старых к новым
    """
    if not params.gate1_enabled:
        return GateResult(passed=True, score=100, signals=["disabled"])
    
    if len(candles_5m) < params.exhaustion_candles:
        return GateResult(passed=False, score=0, signals=["not_enough_candles"])
    
    recent = candles_5m[-params.exhaustion_candles:]
    signals = []
    conditions_met = 0
    
    # --- Условие 1: Истощение (длинные верхние тени) ---
    exhaustion_count = 0
    for c in recent:
        body = abs(c["close"] - c["open"])
        upper_shadow = c["high"] - max(c["close"], c["open"])
        
        if body > 0 and upper_shadow > body * params.shadow_body_ratio:
            exhaustion_count += 1
    
    if exhaustion_count >= 2:
        signals.append(f"exhaustion_shadows={exhaustion_count}")
        conditions_met += 1
    
    # --- Условие 2: High не растёт ---
    highs = [c["high"] for c in recent]
    max_high = max(highs)
    min_high = min(highs)
    high_range_pct = ((max_high - min_high) / max_high * 100) if max_high > 0 else 0
    
    if high_range_pct < params.high_tolerance_pct:
        signals.append(f"high_flat={high_range_pct:.2f}%")
        conditions_met += 1
    
    # --- Условие 3: Close падает при стабильном high ---
    closes = [c["close"] for c in recent]
    close_falling = all(closes[i] >= closes[i+1] for i in range(len(closes)-1))
    # Или просто: последний close < первый close
    close_dropped = closes[-1] < closes[0]
    
    if close_falling or close_dropped:
        signals.append("close_declining")
        conditions_met += 1
    
    passed = conditions_met >= params.min_exhaustion_signals
    score = (conditions_met / 3) * 100
    
    return GateResult(
        passed=passed,
        score=score,
        signals=signals,
        debug={
            "exhaustion_count": exhaustion_count,
            "high_range_pct": high_range_pct,
            "close_falling": close_falling,
            "close_dropped": close_dropped,
            "conditions_met": conditions_met,
        }
    )


# ============================================================
# GATE 2: Trigger (breakdown + failed retest)
# ============================================================

def check_gate2(
    candles_5m: List[Dict],
    change_24h: float,
    params: GateParams
) -> Tuple[GateResult, float, float]:
    """
    Gate 2: Trigger — Breakdown + Failed Retest
    
    Логика:
    1. Определяем range (high/low) последних N свечей
    2. Проверяем breakdown: close < range_low
    3. Проверяем failed retest: цена не вернулась выше range_low
    
    Returns: (GateResult, range_low, range_high)
    """
    if not params.gate2_enabled:
        return GateResult(passed=True, score=100, signals=["disabled"]), 0, 0
    
    # Адаптивное окно в зависимости от силы пампа
    if change_24h > params.pump_threshold_hot:
        n = params.range_candles_hot
    elif change_24h > params.pump_threshold_mid:
        n = params.range_candles_mid
    else:
        n = params.range_candles_base
    
    if len(candles_5m) < n + 2:
        return GateResult(passed=False, score=0, signals=["not_enough_candles"]), 0, 0
    
    # Range из свечей ДО последних 2 (чтобы проверить пробой)
    range_candles = candles_5m[-(n+2):-2]
    range_high = max(c["high"] for c in range_candles)
    range_low = min(c["low"] for c in range_candles)
    
    # Последние 2 свечи для проверки breakdown + retest
    prev_candle = candles_5m[-2]
    last_candle = candles_5m[-1]
    
    signals = []
    score = 0.0
    
    # --- Условие 1: Breakdown (закрытие ниже range_low) ---
    breakdown_threshold = range_low * (1 - params.breakdown_confirm_pct / 100)
    breakdown = prev_candle["close"] < breakdown_threshold
    
    if breakdown:
        signals.append(f"breakdown_close={prev_candle['close']:.4f}<{range_low:.4f}")
        score += 50
    
    # --- Условие 2: Failed Retest (не вернулся выше) ---
    retest_failed = last_candle["close"] < range_low and last_candle["high"] < range_low * 1.005
    
    if retest_failed:
        signals.append("retest_failed")
        score += 50
    
    # Альтернатива: агрессивный вход (только breakdown с объёмом)
    # Это будет проверяться в Gate 3
    
    passed = breakdown and retest_failed
    
    return GateResult(
        passed=passed,
        score=score,
        signals=signals,
        debug={
            "n_candles": n,
            "range_high": range_high,
            "range_low": range_low,
            "prev_close": prev_candle["close"],
            "last_close": last_candle["close"],
            "last_high": last_candle["high"],
            "breakdown": breakdown,
            "retest_failed": retest_failed,
        }
    ), range_low, range_high


# ============================================================
# GATE 3: Confidence (подтверждение давления)
# ============================================================

def check_gate3(
    candles_5m: List[Dict],
    momentum_10m: float,
    funding_rate: float,
    dist_to_high: float,
    prev_dist_to_high: float,
    params: GateParams
) -> GateResult:
    """
    Gate 3: Confidence — Подтверждение давления
    
    Проверяет (нужно 2 из 4):
    1. Momentum сменил знак (был + → стал 0/-)
    2. Объём на пробое >= median * mult
    3. Funding положительный
    4. dist_to_high увеличился (цена уходит от хая)
    """
    if not params.gate3_enabled:
        return GateResult(passed=True, score=100, signals=["disabled"])
    
    signals = []
    conditions_met = 0
    
    # --- Условие 1: Momentum не растёт ---
    momentum_ok = momentum_10m <= params.momentum_threshold
    if momentum_ok:
        signals.append(f"momentum={momentum_10m:.2f}%<=0")
        conditions_met += 1
    
    # --- Условие 2: Объём на пробое выше медианы ---
    if len(candles_5m) >= params.volume_lookback:
        volumes = [c.get("volume", 0) or c.get("turnover", 0) for c in candles_5m[-params.volume_lookback:]]
        volumes_sorted = sorted(volumes)
        median_vol = volumes_sorted[len(volumes_sorted) // 2]
        last_vol = volumes[-1] if volumes else 0
        
        volume_ok = last_vol >= median_vol * params.volume_mult
        if volume_ok:
            signals.append(f"volume={last_vol:.0f}>={median_vol:.0f}*{params.volume_mult}")
            conditions_met += 1
    
    # --- Условие 3: Funding положительный ---
    funding_ok = funding_rate > params.min_funding
    if funding_ok:
        signals.append(f"funding={funding_rate:.4f}>0")
        conditions_met += 1
    
    # --- Условие 4: Уходим от хая ---
    dist_increasing = dist_to_high > prev_dist_to_high
    if dist_increasing:
        signals.append(f"dist_increasing={prev_dist_to_high:.2f}->{dist_to_high:.2f}")
        conditions_met += 1
    
    passed = conditions_met >= params.min_confidence_signals
    score = (conditions_met / 4) * 100
    
    return GateResult(
        passed=passed,
        score=score,
        signals=signals,
        debug={
            "momentum_10m": momentum_10m,
            "momentum_ok": momentum_ok,
            "funding_rate": funding_rate,
            "funding_ok": funding_ok,
            "dist_to_high": dist_to_high,
            "prev_dist_to_high": prev_dist_to_high,
            "dist_increasing": dist_increasing,
            "conditions_met": conditions_met,
        }
    )


# ============================================================
# АНТИПАТТЕРН: V-Recovery
# ============================================================

def check_v_recovery(
    candles_5m: List[Dict],
    range_low: float,
    params: GateParams
) -> bool:
    """
    Проверка V-Recovery (отмена сигнала)
    
    Если цена резко вернулась выше range_low за N свечей — это НЕ шорт.
    
    Returns: True если V-recovery обнаружен (отменить сигнал)
    """
    if len(candles_5m) < params.v_recovery_candles + 1:
        return False
    
    recent = candles_5m[-(params.v_recovery_candles + 1):]
    
    # Была ниже range_low, потом вернулась выше
    was_below = any(c["close"] < range_low for c in recent[:-1])
    now_above = recent[-1]["close"] > range_low
    
    return was_below and now_above


# ============================================================
# РАСЧЁТ ТОРГОВЫХ УРОВНЕЙ
# ============================================================

def calculate_trade_levels(
    entry_price: float,
    range_low: float,
    range_high: float,
    low_24h: float,
    params: GateParams
) -> Tuple[float, float, float, float, float]:
    """
    Расчёт SL и TP уровней
    
    Returns: (sl_price, tp1_price, tp2_price, tp3_price, rr_ratio)
    """
    # SL выше range_high
    sl_price = range_high * (1 + params.sl_above_range_pct / 100)
    
    # TP1: частичный профит
    tp1_price = entry_price - (entry_price - range_low) * params.tp1_ratio
    
    # TP2: range_low
    tp2_price = range_low
    
    # TP3: low 24h (если включено и ниже TP2)
    if params.tp3_use_low24h and low_24h < tp2_price:
        tp3_price = low_24h
    else:
        tp3_price = tp2_price * 0.99  # на 1% ниже TP2
    
    # Risk/Reward
    risk = sl_price - entry_price
    reward = entry_price - tp1_price
    rr_ratio = reward / risk if risk > 0 else 0
    
    return sl_price, tp1_price, tp2_price, tp3_price, rr_ratio


# ============================================================
# ГЛАВНАЯ ФУНКЦИЯ: Проверка всех гейтов
# ============================================================

def check_all_gates(
    symbol: str,
    candles_5m: List[Dict],
    current_price: float,
    change_24h: float,
    range_position: float,
    dist_to_high: float,
    funding_rate: float,
    low_24h: float,
    btc_trend_1h: float = 0.0,
    btc_change_24h: float = 0.0,
    momentum_10m: float = 0.0,
    prev_dist_to_high: float = 0.0,
    params: Optional[GateParams] = None
) -> GatesResult:
    """
    Проверка всех гейтов для символа.
    
    Returns: GatesResult с полной информацией
    """
    if params is None:
        params = get_params(symbol)
    
    result = GatesResult(
        gate0=GateResult(passed=False),
        gate1=GateResult(passed=False),
        gate2=GateResult(passed=False),
        gate3=GateResult(passed=False),
        timestamp=int(time.time()),
        symbol=symbol,
        params_version=params.version,
    )
    
    # === Gate 0: Контекст ===
    result.gate0 = check_gate0(
        btc_trend_1h=btc_trend_1h,
        alt_change_24h=change_24h,
        btc_change_24h=btc_change_24h,
        params=params
    )
    
    if not result.gate0.passed:
        result.status = ""
        result.signal_text = "Контекст не подходит (BTC растёт)"
        return result
    
    # === Gate 1: Setup ===
    result.gate1 = check_gate1(
        candles_5m=candles_5m,
        params=params
    )
    
    if not result.gate1.passed:
        # Проверяем базовые условия для статусов ниже
        if range_position > 70 or change_24h > 8:
            result.status = "Наблюдение"
            result.signal_text = f"Рост +{change_24h:.0f}%, ждём истощение"
        return result
    
    # === Gate 2: Trigger ===
    gate2_result, range_low, range_high = check_gate2(
        candles_5m=candles_5m,
        change_24h=change_24h,
        params=params
    )
    result.gate2 = gate2_result
    
    if not result.gate2.passed:
        if range_position > 80 and change_24h > 10:
            result.status = "Интерес"
            result.signal_text = f"Истощение есть, ждём breakdown"
        else:
            result.status = "Наблюдение"
            result.signal_text = f"Setup готов, нет breakdown"
        return result
    
    # === Проверка V-Recovery ===
    if check_v_recovery(candles_5m, range_low, params):
        result.status = "Наблюдение"
        result.signal_text = "V-recovery, отмена сигнала"
        return result
    
    # === Gate 3: Confidence ===
    result.gate3 = check_gate3(
        candles_5m=candles_5m,
        momentum_10m=momentum_10m,
        funding_rate=funding_rate,
        dist_to_high=dist_to_high,
        prev_dist_to_high=prev_dist_to_high,
        params=params
    )
    
    if not result.gate3.passed:
        result.status = "Готовность"
        result.signal_text = f"Breakdown есть, ждём подтверждение"
        return result
    
    # === ВСЕ ГЕЙТЫ ПРОЙДЕНЫ ===
    result.all_passed = True
    
    # Расчёт торговых уровней
    entry_price = current_price
    sl, tp1, tp2, tp3, rr = calculate_trade_levels(
        entry_price=entry_price,
        range_low=range_low,
        range_high=range_high,
        low_24h=low_24h,
        params=params
    )
    
    # Проверка минимального R/R
    if rr < params.min_rr:
        result.status = "Готовность"
        result.signal_text = f"R/R={rr:.2f} < {params.min_rr}, ждём лучший вход"
        return result
    
    result.entry_price = entry_price
    result.sl_price = sl
    result.tp1_price = tp1
    result.tp2_price = tp2
    result.tp3_price = tp3
    result.rr_ratio = rr
    
    result.status = "ВХОД"
    result.signal_text = f"Breakdown подтверждён, R/R={rr:.2f}"
    
    return result
