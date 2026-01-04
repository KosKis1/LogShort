# core/params.py
# Backward-compatible params for Short Project 2 (Scanner + Live)
# IMPORTANT: This file is designed to satisfy legacy expectations such as:
#   P.TOP.N, P.FOCUS.N, P.UNIVERSE.N
#   P.FOCUS.size, P.UNIVERSE.size
#   flat aliases: TOP_N, FOCUS_N, UNIVERSE_N
#   timing aliases: *_SEC and *_S
#
# Default values match baseline behavior.

from __future__ import annotations
from dataclasses import dataclass

# -------- Blocks (legacy names kept) --------

@dataclass(frozen=True)
class _TopBlock:
    N: int
    refresh_sec: int
    # Some code may refer to .size (treat as N)
    size: int | None = None

    def __post_init__(self):
        # dataclass(frozen=True) doesn't allow assignment; so size handled via constructor
        pass

@dataclass(frozen=True)
class _FocusBlock:
    N: int
    refresh_sec: int
    size: int  # legacy expects FOCUS.size

@dataclass(frozen=True)
class _UniverseBlock:
    N: int
    refresh_sec: int
    size: int  # legacy expects UNIVERSE.size


@dataclass(frozen=True)
class Params:
    TOP: _TopBlock
    FOCUS: _FocusBlock
    UNIVERSE: _UniverseBlock

    # legacy flat aliases
    TOP_N: int
    FOCUS_N: int
    UNIVERSE_N: int

    # timing aliases (both *_SEC and *_S)
    UNIVERSE_REFRESH_SEC: int
    UNIVERSE_REFRESH_S: int
    TOP_REFRESH_SEC: int
    TOP_REFRESH_S: int
    FOCUS_REFRESH_SEC: int
    FOCUS_REFRESH_S: int

    # optional new knobs (safe defaults; do not change behavior)
    EXCLUDE_SYMBOLS: tuple[str, ...] = ()
    LIVE_MIN_CANDIDATE: float = 0.0
    LIVE_MIN_SHORT: float = 0.0
    LIVE_MIN_CONFIDENCE: float = 0.0
    SOFT_DIAG_MODE: bool = False


# -------- Baseline defaults --------
_TOP_N = 20
_FOCUS_N = 5
_UNIVERSE_N = 200

_UNIVERSE_REFRESH_SEC = 120  # 10 min
_TOP_REFRESH_SEC = 60        # 1 min
_FOCUS_REFRESH_SEC = 15      # 10–20 sec

P = Params(
    TOP=_TopBlock(N=_TOP_N, refresh_sec=_TOP_REFRESH_SEC, size=_TOP_N),
    FOCUS=_FocusBlock(N=_FOCUS_N, refresh_sec=_FOCUS_REFRESH_SEC, size=_FOCUS_N),
    UNIVERSE=_UniverseBlock(N=_UNIVERSE_N, refresh_sec=_UNIVERSE_REFRESH_SEC, size=_UNIVERSE_N),

    TOP_N=_TOP_N,
    FOCUS_N=_FOCUS_N,
    UNIVERSE_N=_UNIVERSE_N,

    UNIVERSE_REFRESH_SEC=_UNIVERSE_REFRESH_SEC,
    UNIVERSE_REFRESH_S=_UNIVERSE_REFRESH_SEC,
    TOP_REFRESH_SEC=_TOP_REFRESH_SEC,
    TOP_REFRESH_S=_TOP_REFRESH_SEC,
    FOCUS_REFRESH_SEC=_FOCUS_REFRESH_SEC,
    FOCUS_REFRESH_S=_FOCUS_REFRESH_SEC,
)

# module-level aliases (some code imports these directly)
TOP_N = P.TOP_N
FOCUS_N = P.FOCUS_N
UNIVERSE_N = P.UNIVERSE_N

UNIVERSE_REFRESH_SEC = P.UNIVERSE_REFRESH_SEC
UNIVERSE_REFRESH_S = P.UNIVERSE_REFRESH_S
TOP_REFRESH_SEC = P.TOP_REFRESH_SEC
TOP_REFRESH_S = P.TOP_REFRESH_S
FOCUS_REFRESH_SEC = P.FOCUS_REFRESH_SEC
FOCUS_REFRESH_S = P.FOCUS_REFRESH_S


# ---- Extra tuning params (safe defaults) ----
CLUSTER_MERGE_PCT = 0.005  # 0.5% merge threshold for clustering S/R levels
KLINE_WORKERS = 6  # default thread workers for klines fetching (if used)
