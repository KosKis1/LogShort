"""core.trace

Единый модуль трассировки для проекта.

Цели:
  - Структурированные маркеры в едином формате: TRACE|Mxxx|...
  - Управление включением/выключением через env или параметры init().
  - Heartbeat + Watchdog для диагностики таймеров.

Управление через переменные окружения:
  - DEBUG_TRACE=1        включить трассировку
  - TRACE_LEVEL=1..5     уровень подробности (>=3 — подробные маркеры по тикам)
  - TRACE_FILE=<path>    путь к файлу лога (по умолчанию <logs_dir>/trace.log)

Пример строки:
  TRACE|M313|L2|tick=184|remain=17.9|now=2026-01-03 14:12:01.123|dt=3ms|thread=MainThread
"""

from __future__ import annotations

import os
import threading
import time
import traceback
from dataclasses import dataclass
from typing import Any, Dict, Optional


_lock = threading.Lock()


@dataclass
class TraceConfig:
    enabled: bool = False
    level: int = 0
    file_path: str = ""
    also_stdout: bool = True


_cfg = TraceConfig()


def _now_str() -> str:
    # ms precision
    t = time.time()
    lt = time.localtime(t)
    ms = int((t - int(t)) * 1000)
    return time.strftime("%Y-%m-%d %H:%M:%S", lt) + f".{ms:03d}"


def init(
    *,
    enabled: Optional[bool] = None,
    level: Optional[int] = None,
    logs_dir: Optional[str] = None,
    file_path: Optional[str] = None,
    also_stdout: Optional[bool] = None,
) -> None:
    """Инициализация трассировки.

    Рекомендуется вызывать один раз при старте (в entrypoint).
    """
    env_enabled = os.environ.get("DEBUG_TRACE", "0").strip().lower() in ("1", "true", "yes", "y")
    env_level = os.environ.get("TRACE_LEVEL", "3").strip()
    env_file = os.environ.get("TRACE_FILE", "").strip()

    if enabled is None:
        enabled = env_enabled
    if level is None:
        try:
            level = int(env_level)
        except Exception:
            level = 3
    if also_stdout is None:
        also_stdout = True

    if file_path is None:
        file_path = env_file or ""
    if not file_path:
        base = logs_dir or os.path.join(os.getcwd(), "logs")
        try:
            os.makedirs(base, exist_ok=True)
        except Exception:
            base = os.getcwd()
        file_path = os.path.join(base, "trace.log")

    _cfg.enabled = bool(enabled)
    _cfg.level = int(level or 0)
    _cfg.file_path = file_path
    _cfg.also_stdout = bool(also_stdout)

    if _cfg.enabled:
        trace("M000", "TRACE_INIT", enabled=_cfg.enabled, level=_cfg.level, file=_cfg.file_path)


def enabled() -> bool:
    return bool(_cfg.enabled)


def level() -> int:
    return int(_cfg.level)


def _write_line(line: str) -> None:
    if not _cfg.enabled:
        return
    with _lock:
        try:
            with open(_cfg.file_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            # последняя линия обороны: печать в stdout
            try:
                print(line)
            except Exception:
                pass


def trace(marker: str, tag_or_level: str, /, **kv: Any) -> None:
    """Пишет одну строку трассировки.

    marker: например "M313"
    tag_or_level: например "L2" или "UI" или "FLAGS"
    kv: любые поля (tick, remain, dt, ...)
    """
    if not _cfg.enabled:
        return
    parts = ["TRACE", str(marker), str(tag_or_level)]
    # Везде печатаем now и thread по умолчанию, если не передали
    kv = dict(kv)
    kv.setdefault("now", _now_str())
    kv.setdefault("thread", threading.current_thread().name)
    for k, v in kv.items():
        parts.append(f"{k}={v}")
    line = "|".join(parts)
    _write_line(line)
    if _cfg.also_stdout:
        try:
            print(line)
        except Exception:
            pass


def trace_exc(marker: str, tag_or_level: str, exc: BaseException, /, **kv: Any) -> None:
    """Пишет маркер + traceback."""
    if not _cfg.enabled:
        return
    kv = dict(kv)
    kv["exc"] = repr(exc)
    trace(marker, tag_or_level, **kv)
    tb = traceback.format_exc()
    for line in tb.splitlines():
        _write_line("TRACE|TB|" + line)
        if _cfg.also_stdout:
            try:
                print("TRACE|TB|" + line)
            except Exception:
                pass


class Span:
    """Контекст-таймер для dt=...ms."""

    def __init__(self, marker_enter: str, marker_exit: str, lvl: str, **kv: Any):
        self.marker_enter = marker_enter
        self.marker_exit = marker_exit
        self.lvl = lvl
        self.kv = kv
        self.t0 = 0.0

    def __enter__(self):
        self.t0 = time.time()
        if _cfg.enabled and _cfg.level >= 3:
            trace(self.marker_enter, self.lvl, **self.kv)
        return self

    def __exit__(self, exc_type, exc, tb):
        dt_ms = int((time.time() - self.t0) * 1000)
        if exc is not None:
            trace_exc(self.marker_exit, self.lvl, exc, dt=f"{dt_ms}ms", **self.kv)
            return False
        if _cfg.enabled and _cfg.level >= 3:
            trace(self.marker_exit, self.lvl, dt=f"{dt_ms}ms", **self.kv)
        return False


@dataclass
class HeartbeatState:
    last_hb_ts: float = 0.0
    tick_id: int = 0


_hb = HeartbeatState()


def heartbeat(
    *,
    last_run_l1: Optional[float] = None,
    last_run_l2: Optional[float] = None,
    last_run_l3: Optional[float] = None,
    r1: Optional[float] = None,
    r2: Optional[float] = None,
    r3: Optional[float] = None,
    ui_last_update: Optional[float] = None,
    api60: Optional[int] = None,
) -> None:
    if not _cfg.enabled:
        return
    if _cfg.level < 2:
        return
    now = time.time()
    # 1 раз в секунду максимум
    if now - _hb.last_hb_ts < 1.0:
        return
    _hb.last_hb_ts = now
    _hb.tick_id += 1
    trace(
        "HB",
        "SYS",
        tick=_hb.tick_id,
        L1_last=f"{last_run_l1:.0f}" if last_run_l1 else "-",
        L2_last=f"{last_run_l2:.0f}" if last_run_l2 else "-",
        L3_last=f"{last_run_l3:.0f}" if last_run_l3 else "-",
        r1=r1 if r1 is not None else "-",
        r2=r2 if r2 is not None else "-",
        r3=r3 if r3 is not None else "-",
        ui=f"{ui_last_update:.0f}" if ui_last_update else "-",
        api60=api60 if api60 is not None else "-",
    )


def watchdog(
    *,
    last_run_l2: Optional[float] = None,
    last_run_l3: Optional[float] = None,
    expected_l2: float = 30.0,
    expected_l3: float = 10.0,
) -> None:
    if not _cfg.enabled:
        return
    if _cfg.level < 2:
        return
    now = time.time()
    if last_run_l2 and (now - last_run_l2) > (expected_l2 + 15.0):
        trace("ALERT", "L2", reason="L2_STALLED", delta=f"{now-last_run_l2:.1f}s", expected=f"<={expected_l2}s")
    if last_run_l3 and (now - last_run_l3) > (expected_l3 + 10.0):
        trace("ALERT", "L3", reason="L3_STALLED", delta=f"{now-last_run_l3:.1f}s", expected=f"<={expected_l3}s")
