from __future__ import annotations
import math
from typing import Any, Optional

def fnum(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default

def safe_div(a: float, b: float, default: float = 0.0) -> float:
    return default if b == 0 else (a / b)

def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x

def log1p_norm(x: float, scale: float = 1.0) -> float:
    # Normalized log growth on [0,1] for positive x
    if x <= 0:
        return 0.0
    return clamp(math.log1p(x) / math.log1p(scale), 0.0, 1.0)

def sigmoid(z: float) -> float:
    try:
        return 1.0 / (1.0 + math.exp(-z))
    except OverflowError:
        return 1.0 if z > 0 else 0.0
