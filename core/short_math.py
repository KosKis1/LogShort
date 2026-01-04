"""
core/short_math.py

6B2: All math & scoring logic extracted from auto-short_v095_with_trainer_bridge.py
into a dedicated module to keep UI/Engine/Live free from embedded math.

This is a "lift-and-shift" extraction (same formulas as current baseline),
so behavior stays the same while we gain modularity + ML-readiness.

Functions exported:
clamp, safe_div, pct, fmt_price, local_high, close_hours_ago, trend_ppm, down, up, log1p_norm, structure_score_from_candles, trade_plan, compute_volume_score, compute_exhaustion, compute_short_prob, compute_conf_down_strength, compute_candidate_pct, grade_from, confirm_down_logic, confirm_volume_logic, local_extrema_levels, cluster_levels, compute_support_resistance
"""

from __future__ import annotations

import math
import statistics

from typing import Dict, List, Optional, Tuple

# ------------------------------------------------------------
# Baseline constants (MUST match auto-short_v095_with_trainer_bridge.py)
# ------------------------------------------------------------
# Entry = Price_now * (1 + 1%)
ENTRY_OFFSET_PCT = 1.0
# SL = High_Y * (1 + 0.2%)
SL_BUFFER_PCT = 0.20
# S/R clustering merge threshold (default, may be overridden from params)
CLUSTER_MERGE_PCT = 0.3

# Hard gates used inside candidate computation
EXH_HARD_MIN = 0.25
CONF_HARD_MIN = 50.0

# Try to import from params, fallback to local default
try:
    from core.params import CLUSTER_MERGE_PCT as _CLUSTER_PCT  # type: ignore
    CLUSTER_MERGE_PCT = _CLUSTER_PCT
except Exception:
    pass  # keep default 0.3

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0

def pct(a: float, b: float) -> float:
    return safe_div((a - b), b) * 100.0 if b else 0.0

def fmt_price(x: float) -> str:
    if not x or x <= 0 or math.isnan(x) or math.isinf(x):
        return "N/A"
    if x >= 1000:
        return f"{x:.2f}"
    if x >= 1:
        return f"{x:.4f}"
    return f"{x:.6f}"

def local_high(kl: List[Dict], lookback: int) -> float:
    if not kl:
        return 0.0
    tail = kl[-lookback:] if len(kl) >= lookback else kl
    return max(x["high"] for x in tail) if tail else 0.0

def close_hours_ago(kl_1h: List[Dict], hours: int) -> Optional[float]:
    if not kl_1h:
        return None
    idx = len(kl_1h) - 1 - hours
    if idx < 0:
        idx = 0
    return float(kl_1h[idx]["close"])

def trend_ppm(close_then: float, close_now: float, minutes: int) -> float:
    if minutes <= 0 or close_then <= 0 or close_now <= 0:
        return 0.0
    return pct(close_now, close_then) / float(minutes)

def down(x: float) -> float:
    return clamp((-x) / 0.02, 0.0, 1.0)

def up(x: float) -> float:
    return clamp((x) / 0.02, 0.0, 1.0)

def log1p_norm(x: float, denom: float) -> float:
    x = max(x, 0.0)
    return clamp(math.log1p(x) / math.log1p(denom), 0.0, 1.0)

def structure_score_from_candles(kl: List[Dict], n: int = 6) -> float:
    if not kl or len(kl) < 3:
        return 0.0
    last = kl[-n:] if len(kl) >= n else kl
    closes = [x["close"] for x in last]
    highs = [x["high"] for x in last]
    dec_close = sum(1 for i in range(1, len(closes)) if closes[i] < closes[i - 1])
    dec_high  = sum(1 for i in range(1, len(highs))  if highs[i]  < highs[i - 1])
    return clamp((dec_close + dec_high) / 10.0, 0.0, 1.0)

def trade_plan(price_now: float, high_y: float) -> Tuple[float, float, float, float, float, float, float]:
    entry = price_now * (1.0 + ENTRY_OFFSET_PCT / 100.0)
    if high_y > 0:
        sl = high_y * (1.0 + SL_BUFFER_PCT / 100.0)
    else:
        sl = entry * (1.0 + 0.015)

    risk = max(sl - entry, entry * 0.002)
    tp1 = max(entry - 0.5 * risk, 0.0)
    tp2 = max(entry - 1.0 * risk, 0.0)
    tp3 = max(entry - 1.5 * risk, 0.0)
    rr = safe_div((entry - tp2), (sl - entry)) if (sl - entry) > 0 else 0.0
    profit_pct = safe_div((entry - tp2), entry) * 100.0 if entry > 0 else 0.0
    return entry, sl, tp1, tp2, tp3, rr, profit_pct

def compute_volume_score(ratio_5m_1h: float, ratio_15m_3h: float) -> float:
    return clamp(
        0.6 * log1p_norm(ratio_5m_1h, 3.0) +
        0.4 * log1p_norm(ratio_15m_3h, 3.0),
        0.0, 1.0
    )

def compute_exhaustion(trend_1h: float, trend_3h: float, trend_24h: float) -> float:
    pump = up(trend_24h)
    rev = down(trend_1h) * down(trend_3h)
    return clamp(pump * rev, 0.0, 1.0)

def compute_short_prob(dist_high_pct: float, volume_score: float, btc_div_1h: float, exhaustion: float) -> float:
    proximity = clamp(1.0 - dist_high_pct / 12.0, 0.0, 1.0)
    btc_weak = clamp((-btc_div_1h) / 0.015, 0.0, 1.0)
    return 100.0 * clamp(
        0.35 * exhaustion +
        0.25 * proximity +
        0.20 * volume_score +
        0.20 * btc_weak,
        0.0, 1.0
    )

def compute_conf_down_strength(trend_1h: float, trend_3h: float, volume_score: float, structure_score: float) -> float:
    price_drop = clamp(0.6 * down(trend_1h) + 0.4 * down(trend_3h), 0.0, 1.0)
    return 100.0 * clamp(
        0.45 * price_drop +
        0.35 * structure_score +
        0.20 * volume_score,
        0.0, 1.0
    )

def compute_candidate_pct(short_prob: float, conf: float, rr: float, btc_div_1h: float, exhaustion: float) -> float:
    rr_score = 100.0 * clamp(rr / 2.5, 0.0, 1.0)
    btc_score = 100.0 * clamp((-btc_div_1h) / 0.015, 0.0, 1.0)

    base = clamp(
        0.45 * conf +
        0.35 * short_prob +
        0.15 * rr_score +
        0.05 * btc_score,
        0.0, 100.0
    )

    if exhaustion < EXH_HARD_MIN:
        base = min(base, 40.0)
    if conf < CONF_HARD_MIN:
        base = min(base, 55.0)

    return base

def grade_from(prob: float, conf: float) -> str:
    if prob >= 75 and conf >= 75:
        return "A"
    if prob >= 65 and conf >= 65:
        return "B"
    if prob >= 55 and conf >= 55:
        return "C"
    return "D"

def confirm_down_logic(trend_1h: float, trend_3h: float, structure_score: float) -> bool:
    return (trend_1h < 0.0) and (trend_3h <= 0.0 or structure_score >= 0.35)

def confirm_volume_logic(volume_score: float) -> bool:
    return volume_score >= 0.25


# ============================================================
# SUPPORT / RESISTANCE
# ============================================================

def local_extrema_levels(kl: List[Dict]) -> Tuple[List[float], List[float]]:
    lows, highs = [], []
    if not kl or len(kl) < 5:
        return lows, highs
    for i in range(1, len(kl) - 1):
        a, b, c = kl[i - 1], kl[i], kl[i + 1]
        if b["low"] < a["low"] and b["low"] < c["low"]:
            lows.append(float(b["low"]))
        if b["high"] > a["high"] and b["high"] > c["high"]:
            highs.append(float(b["high"]))
    return lows, highs

def cluster_levels(levels: List[float], merge_pct: float) -> List[float]:
    if not levels:
        return []
    levels = sorted(levels)
    clusters: List[List[float]] = [[levels[0]]]
    for x in levels[1:]:
        last_med = statistics.median(clusters[-1])
        rel = abs(x - last_med) / last_med * 100.0 if last_med else 999.0
        if rel <= merge_pct:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    return sorted(float(statistics.median(cl)) for cl in clusters)

def compute_support_resistance(kl: List[Dict], price_now: float) -> Tuple[List[float], List[float]]:
    lows, highs = local_extrema_levels(kl)

    if len(lows) < 3 and kl:
        lows += [min(x["low"] for x in kl)]
    if len(highs) < 3 and kl:
        highs += [max(x["high"] for x in kl)]

    sup_levels = cluster_levels(lows, CLUSTER_MERGE_PCT)
    res_levels = cluster_levels(highs, CLUSTER_MERGE_PCT)

    supports = [x for x in sup_levels if x < price_now]
    resistances = [x for x in res_levels if x > price_now]

    supports = sorted(supports, reverse=True)[:3]
    resistances = sorted(resistances)[:3]
    return supports, resistances


# ============================================================
# SOUND
# ============================================================

