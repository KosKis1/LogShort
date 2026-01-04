# -*- coding: utf-8 -*-
"""
core.preselect

Pre-selection for SHORT candidates using ONLY /v5/market/tickers data (no klines).

Goal:
- From Universe TOP200 (by turnover), pick TOP20 "ripe to drop" candidates.
- Robust to "break high then drop": uses price position in 24h range (pos) not strict near-high.

Score idea (B + expanded top window):
- strong 24h rise (momentum/overheat)
- price is in upper part of 24h range (pos)
- positive funding (if available) -> crowd long bias (overheat)
- liquidity filter is applied outside (Universe already TOP200 by turnover)

All fields are best-effort; missing fields -> treated as neutral.
"""
from __future__ import annotations

from typing import Dict, Any, List, Tuple
import math

# ------------------------------------------------------------
# Watchlist (Наблюдение) types (RU short-codes):
#   Р→К : Рост → Коррекция (перегрев у хаёв)
#   П→К : Памп → Коррекция (резкий перегрев/истощение)
#   П→П : Плавное Падение (нисходящий тренд/продолжение)
#
# ВАЖНО:
# - Этот модуль работает ТОЛЬКО по данным /v5/market/tickers.
# - Никаких klines тут нет (скорость!).
# - Все пороги “мягкие” (это наблюдение, не вход).
# ------------------------------------------------------------

WATCH_RK = "Р→К"  # Рост → Коррекция
WATCH_PK = "П→К"  # Памп → Коррекция
WATCH_PP = "П→П"  # Плавное Падение

def _to_f(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default

def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    if b == 0.0:
        return default
    return a / b

def pre_short_score(t: Dict[str, Any]) -> float:
    """
    Compute pre-score from ticker row.
    Returns higher => more likely short candidate.
    """
    last = _to_f(t.get("lastPrice") or t.get("last"))
    high = _to_f(t.get("highPrice24h") or t.get("high24h"))
    low  = _to_f(t.get("lowPrice24h") or t.get("low24h"))
    # price change 24h percent: sometimes 'price24hPcnt' is like "0.1234" (12.34%)
    chg = _to_f(t.get("price24hPcnt"))
    # funding can be absent in tickers; treat missing as 0
    fund = _to_f(t.get("fundingRate"))
    # position in 24h range [0..1], robust to break-high updates
    rng = max(0.0, high - low)
    pos = _safe_div(last - low, rng, default=0.5) if rng > 0 else 0.5

    # normalize change: focus on positive rise; ignore negative here (those are already dropping)
    rise = max(0.0, chg)  # 0.20 -> 20%
    # compress with log to avoid domination by extreme values
    rise_n = math.log1p(rise * 10.0)  # 0.. ~
    # funding: positive funding increases short attractiveness; compress as well
    fund_n = math.log1p(max(0.0, fund) * 10000.0)  # funding is tiny; scale
    # pos emphasis: only upper band matters
    pos_n = max(0.0, pos - 0.7) / 0.3  # 0 when <0.7, 1 at 1.0
    pos_n = min(1.0, pos_n)

    # combined score
    score = (2.2 * rise_n) + (1.4 * pos_n) + (0.9 * fund_n)

    # small penalty if liquidity fields show tiny volume (best-effort)
    turn = _to_f(t.get("turnover24h"))
    if turn and turn < 1_000_000:  # < $1m
        score *= 0.5

    return float(score)


def watch_type_and_score(t: Dict[str, Any]) -> Tuple[str, float]:
    """Return (watch_type, watch_score) using ONLY ticker fields.

    watch_score is a comparative score (higher => higher priority in Watchlist).
    This is NOT an entry signal.
    """
    last = _to_f(t.get("lastPrice") or t.get("last"))
    high = _to_f(t.get("highPrice24h") or t.get("high24h"))
    low = _to_f(t.get("lowPrice24h") or t.get("low24h"))
    chg = _to_f(t.get("price24hPcnt")) * 100.0  # percent
    fund = _to_f(t.get("fundingRate"))
    turn = _to_f(t.get("turnover24h"))

    rng = max(0.0, high - low)
    pos01 = _safe_div(last - low, rng, default=0.5) if rng > 0 else 0.5
    pos = max(0.0, min(1.0, pos01))
    dist_to_high = _safe_div(high - last, high, default=0.0) if high > 0 else 0.0

    # Normalizations
    rise = max(0.0, chg) / 100.0
    fall = max(0.0, -chg) / 100.0
    rise_n = math.log1p(rise * 10.0)
    fall_n = math.log1p(fall * 10.0)
    fund_pos_n = math.log1p(max(0.0, fund) * 10000.0)
    fund_neg_n = math.log1p(max(0.0, -fund) * 10000.0)
    near_high_n = max(0.0, (0.03 - dist_to_high) / 0.03)  # 1 when <=3%
    near_high_n = min(1.0, near_high_n)
    top_pos_n = max(0.0, (pos - 0.75) / 0.25)  # 0..1 (upper quarter)
    top_pos_n = min(1.0, top_pos_n)
    low_pos_n = max(0.0, (0.35 - pos) / 0.35)  # 0..1 (lower ~35%)
    low_pos_n = min(1.0, low_pos_n)

    # Liquidity soft penalty
    liq_mul = 1.0
    if turn and turn < 1_000_000:  # < $1m turnover
        liq_mul = 0.5

    # ---- Type scores (soft / observation) ----
    # Р→К (overheat near highs)
    rk = (2.0 * rise_n) + (1.3 * top_pos_n) + (1.0 * fund_pos_n) + (1.0 * near_high_n)
    # П→К (pump/exhaustion): stronger rise + very near highs
    pk = (2.6 * rise_n) + (1.6 * top_pos_n) + (1.1 * fund_pos_n) + (1.4 * near_high_n)
    # Slight boost when very strong 24h move (proxy of "pamp")
    if chg >= 15.0:
        pk *= 1.15

    # П→П (smooth down / trend continuation): falling + lower zone + negative funding
    pp = (2.2 * fall_n) + (1.2 * low_pos_n) + (0.8 * fund_neg_n)
    # Extra boost if close to 24h low (proxy)
    if pos <= 0.2:
        pp *= 1.10

    rk *= liq_mul
    pk *= liq_mul
    pp *= liq_mul

    # Pick best type
    best_type = WATCH_RK
    best_score = rk
    if pk > best_score:
        best_type, best_score = WATCH_PK, pk
    if pp > best_score:
        best_type, best_score = WATCH_PP, pp

    return best_type, float(best_score)


def select_watch_candidates(
    tickers: List[Dict[str, Any]],
    top_n: int = 20,
    prefer_types: Tuple[str, ...] = (WATCH_PK, WATCH_RK, WATCH_PP),
) -> List[Dict[str, Any]]:
    """Build Watchlist candidates from tickers.

    Returns list of dicts:
        {"symbol": str, "watch_type": str, "watch_score": float}

    prefer_types controls tie-breaking priority.
    """
    pref = {t: i for i, t in enumerate(prefer_types)}
    rows: List[Dict[str, Any]] = []
    for t in tickers:
        sym = (t.get("symbol") or "").strip()
        if not sym:
            continue
        wtype, wscore = watch_type_and_score(t)
        rows.append({"symbol": sym, "watch_type": wtype, "watch_score": float(wscore)})

    rows.sort(
        key=lambda x: (
            float(x.get("watch_score", 0.0)),
            -pref.get(str(x.get("watch_type")), 999),
        ),
        reverse=True,
    )
    return rows[: max(1, int(top_n))]

def select_top_short_candidates(tickers: List[Dict[str, Any]], top_n: int = 20) -> List[Dict[str, Any]]:
    """Return list of dicts: {"symbol": str, "score": float} sorted desc.

    IMPORTANT:
    - Caller (GUI) expects dict-like rows and uses .get("symbol").
    - This wrapper keeps backward-compat with existing call-sites.
    """
    rows: List[Dict[str, Any]] = []
    for t in tickers:
        sym = (t.get("symbol") or "").strip()
        if not sym:
            continue
        rows.append({"symbol": sym, "score": float(pre_short_score(t))})
    rows.sort(key=lambda x: float(x.get("score", 0.0)), reverse=True)
    return rows[:max(1, int(top_n))]
