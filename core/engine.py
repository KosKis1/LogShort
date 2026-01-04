"""
core.engine
Step 3 (safe): centralize base ranking + Focus selection.
This module MUST NOT import Qt / GUI. Pure python only.

Used by the monolith UI to avoid duplicated "base sort" logic in multiple places.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence, Tuple


def _as_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def base_rank_tuple(row: Any) -> Tuple[float, float, float, float]:
    """
    Base ranking (DESC):
      1) Short % (short_prob)
      2) Candidate % (candidate_pct)
      3) Confidence % (short_conf)
      4) Volume 24h (vol24h_m)
    Returns a tuple that can be used for sorting DESC (caller usually uses reverse=True),
    or use the returned negative values for ASC.
    """
    short_p = _as_float(getattr(row, "short_prob", 0.0))
    cand_p  = _as_float(getattr(row, "candidate_pct", 0.0))
    conf_p  = _as_float(getattr(row, "short_conf", 0.0))
    vol24   = _as_float(getattr(row, "vol24h_m", 0.0))
    return (short_p, cand_p, conf_p, vol24)


def sort_symbols_base(rows_by_symbol: Dict[str, Any], symbols: Sequence[str]) -> List[str]:
    """Return symbols sorted by base ranking (DESC). Missing rows go to the end."""
    def key(sym: str) -> Tuple[int, float, float, float, float]:
        r = rows_by_symbol.get(sym)
        if r is None:
            return (1, 0.0, 0.0, 0.0, 0.0)
        a,b,c,d = base_rank_tuple(r)
        return (0, a, b, c, d)
    return sorted(list(symbols), key=key, reverse=True)


def select_focus_symbols(
    rows_by_symbol: Dict[str, Any],
    candidates: Sequence[str],
    focus_n: int,
    pinned: Sequence[str] = (),
) -> List[str]:
    """
    Select Focus list from candidates by base ranking.
    Excludes pinned.
    """
    pin = set(pinned or ())
    filtered = [s for s in candidates if s not in pin]
    ranked = sort_symbols_base(rows_by_symbol, filtered)
    return ranked[: max(0, int(focus_n))]


def apply_base_sort_inplace(
    rows_by_symbol: Dict[str, Any],
    symbols: List[str],
    pinned: Sequence[str] = (),
) -> List[str]:
    """Utility: returns a new list with pinned first (same order), rest by base ranking."""
    pin = list(pinned or ())
    rest = [s for s in symbols if s not in set(pin)]
    rest_sorted = sort_symbols_base(rows_by_symbol, rest)
    return pin + rest_sorted
