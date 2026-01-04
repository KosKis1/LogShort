# core/params_ml.py
# Параметры гейтов — готовы к ML-обучению для каждой монеты
# Version: 1.0

from dataclasses import dataclass, field, asdict
from typing import Optional
import json
import os
import time


@dataclass
class GateParams:
    """
    Все настраиваемые параметры системы гейтов.
    
    Эти параметры будут:
    1. Сначала использоваться как DEFAULT
    2. Потом обучаться ML для каждой монеты отдельно
    3. Храниться в params/{SYMBOL}.json
    """
    
    # === Gate 0: Контекст рынка ===
    btc_trend_max: float = 0.5           # BTC %1h должен быть <= этого (не растёт сильно)
    divergence_min: float = 5.0          # альт должен расти больше BTC минимум на X%
    gate0_enabled: bool = True           # можно отключить для тестов
    
    # === Gate 1: Setup (истощение у вершины) ===
    shadow_body_ratio: float = 1.5       # upper_shadow > body * ratio = истощение
    exhaustion_candles: int = 3          # сколько свечей проверять на истощение
    high_tolerance_pct: float = 0.3      # "примерно равный high" = разница < X%
    min_exhaustion_signals: int = 2      # минимум сигналов из 3 для Gate 1
    gate1_enabled: bool = True
    
    # === Gate 2: Trigger (breakdown + failed retest) ===
    range_candles_base: int = 8          # базовое окно для range (40 мин на 5m)
    range_candles_hot: int = 14          # окно если памп > 30% (70 мин)
    range_candles_mid: int = 10          # окно если памп 15-30% (50 мин)
    pump_threshold_hot: float = 30.0     # порог "горячего" пампа %
    pump_threshold_mid: float = 15.0     # порог среднего пампа %
    retest_candles: int = 2              # сколько свечей ждать failed retest
    breakdown_confirm_pct: float = 0.1   # закрытие должно быть ниже range_low на X%
    gate2_enabled: bool = True
    
    # === Gate 3: Confidence (подтверждение давления) ===
    volume_mult: float = 1.3             # объём пробоя >= median * mult
    volume_lookback: int = 12            # окно для расчёта median объёма
    momentum_threshold: float = 0.0      # %10m должен быть <= этого (не растёт)
    min_confidence_signals: int = 2      # минимум сигналов из 4 для Gate 3
    gate3_enabled: bool = True
    
    # === Пороги отбора кандидатов ===
    min_change_24h: float = 8.0          # минимальный рост 24h %
    min_range_position: float = 85.0     # позиция в диапазоне дня (0-100)
    max_dist_to_high: float = 2.0        # максимальное расстояние до хая %
    min_funding: float = 0.0             # минимальный фандинг (0 = любой положительный)
    min_turnover_m: float = 10.0         # минимальный оборот в миллионах
    
    # === Risk Management ===
    sl_above_range_pct: float = 0.5      # SL выше range_high на X%
    sl_above_local_high_pct: float = 0.3 # или выше локального хая на X%
    tp1_ratio: float = 0.5               # TP1 = entry - (entry - range_low) * ratio
    tp2_ratio: float = 1.0               # TP2 = range_low
    tp3_use_low24h: bool = True          # TP3 = low 24h
    min_rr: float = 1.5                  # минимальный Risk/Reward для входа
    
    # === Антипаттерны ===
    v_recovery_candles: int = 2          # V-recovery за N свечей = отмена сигнала
    signal_ttl_minutes: int = 15         # сигнал актуален N минут после генерации
    
    # === ML Metadata ===
    symbol: str = "DEFAULT"              # для какой монеты эти параметры
    version: int = 1                     # версия параметров
    trained_at: float = 0.0              # timestamp обучения (0 = не обучено)
    win_rate: float = 0.0                # винрейт на истории
    sample_size: int = 0                 # на скольких сделках обучено
    
    def to_dict(self) -> dict:
        """Сериализация в словарь"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, d: dict) -> "GateParams":
        """Десериализация из словаря"""
        # Фильтруем только известные поля
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in d.items() if k in known_fields}
        return cls(**filtered)
    
    def save(self, path: str):
        """Сохранить параметры в JSON"""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load(cls, path: str) -> "GateParams":
        """Загрузить параметры из JSON"""
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))


# === Глобальный кеш параметров ===
_params_cache: dict = {}


def get_params(symbol: str = "DEFAULT", params_dir: str = "params") -> GateParams:
    """
    Получить параметры для символа.
    Сначала ищет {symbol}.json, если нет — DEFAULT.json, если нет — дефолтные.
    """
    global _params_cache
    
    cache_key = f"{params_dir}/{symbol}"
    if cache_key in _params_cache:
        return _params_cache[cache_key]
    
    # Пробуем загрузить для конкретного символа
    symbol_path = os.path.join(params_dir, f"{symbol}.json")
    if os.path.exists(symbol_path):
        params = GateParams.load(symbol_path)
        _params_cache[cache_key] = params
        return params
    
    # Пробуем DEFAULT
    default_path = os.path.join(params_dir, "DEFAULT.json")
    if os.path.exists(default_path):
        params = GateParams.load(default_path)
        params.symbol = symbol  # подменяем символ
        _params_cache[cache_key] = params
        return params
    
    # Возвращаем хардкод дефолт
    params = GateParams(symbol=symbol)
    _params_cache[cache_key] = params
    return params


def clear_params_cache():
    """Очистить кеш параметров (после обучения)"""
    global _params_cache
    _params_cache = {}
