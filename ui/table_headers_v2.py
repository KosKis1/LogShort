# ============================================================
# TABLE HEADERS V2 - Новые заголовки с прогресс-барами
# ============================================================
# Версия: v2.0
# Дата: 02.01.2025
# ============================================================

"""
ВИЗУАЛИЗАЦИЯ ПЕРЕСЧЁТОВ
=======================

Первая таблица (TOP200):
- Детектор: каждые 10 сек
- Цены: каждые 30 сек
- Полный: каждые 5 мин

Вторая таблица (Кандидаты):
- Анализ: каждые 10 сек
- Триггеры: по событиям
"""

import time
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass

# Импорт конфигурации
try:
    from core.config_v2 import (
        SCAN_LEVEL1_INTERVAL_SEC,
        SCAN_LEVEL2_INTERVAL_SEC,
        SCAN_LEVEL3_INTERVAL_SEC,
        CANDIDATES_REFRESH_SEC,
        STATUS_COLOR_ENTRY,
        STATUS_COLOR_READY,
        STATUS_COLOR_INTEREST,
        STATUS_COLOR_WATCH,
        CRITERIA_COLOR_CLASSIC,
        CRITERIA_COLOR_PUMP_5M,
        CRITERIA_COLOR_PUMP_1M,
        CRITERIA_COLOR_COMBO,
    )
except ImportError:
    SCAN_LEVEL1_INTERVAL_SEC = 300
    SCAN_LEVEL2_INTERVAL_SEC = 30
    SCAN_LEVEL3_INTERVAL_SEC = 10
    CANDIDATES_REFRESH_SEC = 10
    STATUS_COLOR_ENTRY = "#007800"
    STATUS_COLOR_READY = "#8C6400"
    STATUS_COLOR_INTEREST = "#646432"
    STATUS_COLOR_WATCH = "#3C3C3C"
    CRITERIA_COLOR_CLASSIC = "#1E90FF"
    CRITERIA_COLOR_PUMP_5M = "#FFA500"
    CRITERIA_COLOR_PUMP_1M = "#FF4500"
    CRITERIA_COLOR_COMBO = "#FFD700"


@dataclass
class ProgressBarState:
    """Состояние прогресс-бара."""
    name: str
    total_sec: int
    remaining_sec: int = 0
    in_progress: bool = False
    last_update: float = 0.0
    
    @property
    def progress_pct(self) -> float:
        """Процент выполнения (0-100)."""
        if self.total_sec <= 0:
            return 100.0
        elapsed = self.total_sec - self.remaining_sec
        return min(100.0, max(0.0, (elapsed / self.total_sec) * 100))
    
    @property
    def progress_bar(self) -> str:
        """ASCII прогресс-бар."""
        filled = int(self.progress_pct / 10)
        return "█" * filled + "░" * (10 - filled)
    
    def format_remaining(self) -> str:
        """Форматирует оставшееся время."""
        if self.remaining_sec >= 60:
            return f"{self.remaining_sec // 60}м {self.remaining_sec % 60}с"
        return f"{self.remaining_sec}с"


class HeaderStateManager:
    """Менеджер состояния заголовков таблиц."""
    
    def __init__(self):
        # Прогресс-бары для первой таблицы
        self.level1_bar = ProgressBarState(
            name="Полный пересчёт",
            total_sec=SCAN_LEVEL1_INTERVAL_SEC
        )
        self.level2_bar = ProgressBarState(
            name="Обновление цен",
            total_sec=SCAN_LEVEL2_INTERVAL_SEC
        )
        self.level3_bar = ProgressBarState(
            name="Детектор пампов",
            total_sec=SCAN_LEVEL3_INTERVAL_SEC
        )
        
        # Прогресс-бар для второй таблицы
        self.candidates_bar = ProgressBarState(
            name="Анализ кандидатов",
            total_sec=CANDIDATES_REFRESH_SEC
        )
        
        # Счётчики
        self.total_coins = 200
        self.selected_coins = 0
        self.classic_count = 0
        self.pump_5m_count = 0
        self.pump_1m_count = 0
        self.combo_count = 0
        
        # Счётчики статусов (вторая таблица)
        self.status_counts = {
            "Наблюдение": 0,
            "Интерес": 0,
            "Готовность": 0,
            "ВХОД": 0
        }
        
        # Последние события
        self.recent_events: List[Tuple[str, str, str]] = []  # (time, symbol, event)
        
        # Триггеры
        self.trigger_active = False
        self.trigger_message = ""
        
    def update_level_timers(
        self,
        level1_remaining: int,
        level2_remaining: int,
        level3_remaining: int,
        candidates_remaining: int
    ):
        """Обновляет таймеры всех уровней."""
        self.level1_bar.remaining_sec = level1_remaining
        self.level2_bar.remaining_sec = level2_remaining
        self.level3_bar.remaining_sec = level3_remaining
        self.candidates_bar.remaining_sec = candidates_remaining
    
    def set_level_in_progress(self, level: int, in_progress: bool):
        """Устанавливает флаг пересчёта для уровня."""
        if level == 1:
            self.level1_bar.in_progress = in_progress
        elif level == 2:
            self.level2_bar.in_progress = in_progress
        elif level == 3:
            self.level3_bar.in_progress = in_progress
        elif level == 4:  # candidates
            self.candidates_bar.in_progress = in_progress
    
    def update_counts(
        self,
        selected: int,
        classic: int,
        pump_5m: int,
        pump_1m: int,
        combo: int
    ):
        """Обновляет счётчики отобранных монет."""
        self.selected_coins = selected
        self.classic_count = classic
        self.pump_5m_count = pump_5m
        self.pump_1m_count = pump_1m
        self.combo_count = combo
    
    def update_status_counts(
        self,
        watch: int,
        interest: int,
        ready: int,
        entry: int
    ):
        """Обновляет счётчики статусов."""
        self.status_counts["Наблюдение"] = watch
        self.status_counts["Интерес"] = interest
        self.status_counts["Готовность"] = ready
        self.status_counts["ВХОД"] = entry
    
    def add_event(self, symbol: str, event: str):
        """Добавляет событие в ленту."""
        time_str = time.strftime("%H:%M:%S")
        self.recent_events.insert(0, (time_str, symbol, event))
        # Храним только последние 3 события
        self.recent_events = self.recent_events[:3]
    
    def set_trigger(self, active: bool, message: str = ""):
        """Устанавливает состояние триггера."""
        self.trigger_active = active
        self.trigger_message = message
    
    # ============================================================
    # ГЕНЕРАЦИЯ HTML/TEXT ДЛЯ ЗАГОЛОВКОВ
    # ============================================================
    
    def get_table1_header_text(self) -> str:
        """Возвращает текст заголовка первой таблицы."""
        lines = []
        
        # Строка 1: Название
        lines.append("🔵 TOP 200 монет по обороту")
        
        # Строка 2: Прогресс-бары
        det_status = "🟡 ПЕРЕСЧЁТ..." if self.level3_bar.in_progress else self.level3_bar.progress_bar
        price_status = "🟡 ОБНОВЛЕНИЕ..." if self.level2_bar.in_progress else self.level2_bar.progress_bar
        full_status = "🔄 ПЕРЕСЧЁТ..." if self.level1_bar.in_progress else self.level1_bar.progress_bar
        
        lines.append(
            f"🔄 Детектор: {det_status} {self.level3_bar.format_remaining()} | "
            f"💰 Цены: {price_status} {self.level2_bar.format_remaining()} | "
            f"📊 Полный: {full_status} {self.level1_bar.format_remaining()}"
        )
        
        # Строка 3: Счётчики
        lines.append(
            f"Отобрано: {self.selected_coins} из {self.total_coins} | "
            f"📊 Класс: {self.classic_count} | "
            f"⚡ Быстрые: {self.pump_5m_count} | "
            f"🚀 Экстрем: {self.pump_1m_count}"
        )
        
        return "\n".join(lines)
    
    def get_table2_header_text(self) -> str:
        """Возвращает текст заголовка второй таблицы."""
        lines = []
        
        # Строка 1: Название
        lines.append("🎯 Кандидаты для SHORT позиций")
        
        # Строка 2: Прогресс-бар и триггеры
        analysis_status = "🟡 АНАЛИЗ..." if self.candidates_bar.in_progress else self.candidates_bar.progress_bar
        trigger_status = "🔴 " + self.trigger_message if self.trigger_active else "🟢 Активны"
        
        lines.append(
            f"🔄 Анализ: {analysis_status} {self.candidates_bar.format_remaining()} | "
            f"⚡ Триггеры: {trigger_status}"
        )
        
        # Строка 3: Счётчики статусов
        total = sum(self.status_counts.values())
        lines.append(
            f"Всего: {total} монет | "
            f"Наблюд: {self.status_counts['Наблюдение']} | "
            f"Интерес: {self.status_counts['Интерес']} | "
            f"Готовн: {self.status_counts['Готовность']} | "
            f"🔴 ВХОД: {self.status_counts['ВХОД']}"
        )
        
        # Строка 4: Последние события (если есть)
        if self.recent_events:
            events_str = " | ".join(
                f"{t} - {sym} → {evt}" for t, sym, evt in self.recent_events[:2]
            )
            lines.append(f"Последние: {events_str}")
        
        return "\n".join(lines)
    
    def get_compact_table1_header(self) -> str:
        """Компактный заголовок для первой таблицы (однострочный)."""
        return (
            f"🔵 TOP 200 | "
            f"🔄 10с: {self.level3_bar.progress_bar} {self.level3_bar.remaining_sec}с | "
            f"💰 30с: {self.level2_bar.progress_bar} {self.level2_bar.remaining_sec}с | "
            f"📊 5м: {self.level1_bar.progress_bar} {self.level1_bar.format_remaining()} | "
            f"Отобрано: {self.selected_coins}"
        )
    
    def get_compact_table2_header(self) -> str:
        """Компактный заголовок для второй таблицы (однострочный)."""
        total = sum(self.status_counts.values())
        return (
            f"🎯 Кандидаты | "
            f"🔄 {self.candidates_bar.progress_bar} {self.candidates_bar.remaining_sec}с | "
            f"⚡{'🟢' if not self.trigger_active else '🔴'} | "
            f"{total} монет | "
            f"ВХОД: {self.status_counts['ВХОД']}"
        )


# ============================================================
# ОПРЕДЕЛЕНИЯ КОЛОНОК ТАБЛИЦ
# ============================================================

# Первая таблица (TOP200) - 11 колонок (оптимизированная)
TABLE1_HEADERS = [
    "Ранг",           # 0
    "Монета",         # 1
    "Тип",            # 2 - НОВОЕ: тип монеты (L1, DeFi, Meme, etc.)
    "Позиция %",      # 3
    "До хая %",       # 4
    "24ч %",          # 5
    "Импульс",        # 6 - НОВОЕ: иконка импульса 5м
    "V-Спайк",        # 7 - НОВОЕ: volume spike
    "Слабость",       # 8 - НОВОЕ: BTC divergence
    "Тренд",          # 9 - НОВОЕ: тренд 1ч
    "Зрелость",       # 10 - НОВОЕ: готовность сигнала
    "Критерий",       # 11 - НОВОЕ: почему попала во вторую таблицу
]

# Вторая таблица (Кандидаты) - 17 колонок (полная версия)
TABLE2_HEADERS = [
    "Монета",         # 0
    "Тип",            # 1 - НОВОЕ: тип монеты
    "Критерий",       # 2 - НОВОЕ: КЛАСС / ПАМП-5м / ЭКСТР-1м / КОМБО
    "Статус",         # 3
    "Скор",           # 4
    "До хая %",       # 5
    "Exhaustion",     # 6 - НОВОЕ: истощение
    "Слабость",       # 7 - НОВОЕ: RW 1ч с трендом
    "V-Дин",          # 8 - НОВОЕ: динамика объёма
    "Тренд",          # 9 - НОВОЕ: объединённый 1ч→3ч
    "Z-Score",        # 10 - НОВОЕ
    "Качество",       # 11 - НОВОЕ: звёзды
    "Вход",           # 12
    "SL",             # 13
    "TP1",            # 14
    "R/R",            # 15
    "Осталось",       # 16
]


# ============================================================
# ФОРМАТИРОВАНИЕ ЗНАЧЕНИЙ
# ============================================================

def format_impulse(change_5m: float) -> str:
    """Форматирует импульс 5м в иконку."""
    if change_5m >= 5.0:
        return "🚀"
    elif change_5m >= 3.0:
        return "⬆️⬆️"
    elif change_5m >= 1.0:
        return "⬆️"
    elif change_5m >= -1.0:
        return "➡️"
    else:
        return "⬇️"


def format_volume_spike(spike: float) -> str:
    """Форматирует volume spike."""
    if spike >= 3.0:
        return f"🔥🔥🔥 {spike:.1f}x"
    elif spike >= 2.0:
        return f"🔥🔥 {spike:.1f}x"
    elif spike >= 1.5:
        return f"🔥 {spike:.1f}x"
    elif spike >= 1.0:
        return f"⚡ {spike:.1f}x"
    else:
        return f"💤 {spike:.1f}x"


def format_relative_weakness(rw: float) -> str:
    """Форматирует относительную слабость."""
    if rw <= -3.0:
        return f"🟢🟢🟢 {rw:.1f}%"
    elif rw <= -2.0:
        return f"🟢🟢 {rw:.1f}%"
    elif rw <= -1.0:
        return f"🟢 {rw:.1f}%"
    elif rw <= 0.5:
        return f"⚪ {rw:.1f}%"
    else:
        return f"🔴 {rw:.1f}%"


def format_trend(trend_1h: float, trend_3h: Optional[float] = None) -> str:
    """Форматирует тренд."""
    def trend_icon(t: float) -> str:
        if t <= -0.5:
            return "⬇️⬇️"
        elif t <= -0.1:
            return "⬇️"
        elif t <= 0.1:
            return "➡️"
        elif t <= 0.5:
            return "⬆️"
        else:
            return "⬆️⬆️"
    
    if trend_3h is not None:
        return f"{trend_icon(trend_1h)}→{trend_icon(trend_3h)}"
    return trend_icon(trend_1h)


def format_exhaustion(exh: float) -> str:
    """Форматирует истощение."""
    if exh >= 0.8:
        return f"✓✓✓ {exh:.2f}"
    elif exh >= 0.6:
        return f"✓✓ {exh:.2f}"
    elif exh >= 0.4:
        return f"✓ {exh:.2f}"
    elif exh >= 0.2:
        return f"⚠️ {exh:.2f}"
    else:
        return f"❌ {exh:.2f}"


def format_z_score(z: float) -> str:
    """Форматирует Z-Score."""
    if z >= 2.5:
        return f"🟢🟢🟢 {z:.1f}"
    elif z >= 2.0:
        return f"🟢🟢 {z:.1f}"
    elif z >= 1.5:
        return f"🟢 {z:.1f}"
    elif z >= -1.5:
        return f"⚪ {z:.1f}"
    else:
        return f"🔴 {z:.1f}"


def format_quality_stars(stars: int) -> str:
    """Форматирует качество в звёзды."""
    return "⭐" * stars if stars > 0 else "—"


def format_criteria_type(criteria: str) -> str:
    """Форматирует тип критерия с иконкой."""
    icons = {
        "КЛАСС": "📊 КЛАСС",
        "ПАМП-5м": "⚡ ПАМП-5м",
        "ЭКСТР-1м": "🚀 ЭКСТР-1м",
        "КОМБО": "🎯 КОМБО",
    }
    return icons.get(criteria, criteria)


def format_maturity(score: float, rw_passed: bool) -> str:
    """Форматирует зрелость сигнала."""
    if not rw_passed:
        return f"{min(29, score):.0f}% 🔴"
    elif score >= 75:
        return f"{score:.0f}% 🟢"
    elif score >= 50:
        return f"{score:.0f}% 🟡"
    else:
        return f"{score:.0f}% 🔴"


def format_volume_dynamic(declining: bool, spike: float) -> str:
    """Форматирует динамику объёма."""
    if declining:
        return "📉📉 🟢" if spike > 1.5 else "📉"
    elif spike >= 2.0:
        return "📈📈"
    elif spike >= 1.5:
        return "📈"
    else:
        return "➡️"


# ============================================================
# ЦВЕТА ДЛЯ СТАТУСОВ И КРИТЕРИЕВ
# ============================================================

def get_status_color(status: str) -> str:
    """Возвращает цвет для статуса."""
    colors = {
        "ВХОД": STATUS_COLOR_ENTRY,
        "Готовность": STATUS_COLOR_READY,
        "Интерес": STATUS_COLOR_INTEREST,
        "Наблюдение": STATUS_COLOR_WATCH,
    }
    return colors.get(status, "#3C3C3C")


def get_criteria_color(criteria: str) -> str:
    """Возвращает цвет для критерия."""
    colors = {
        "КЛАСС": CRITERIA_COLOR_CLASSIC,
        "ПАМП-5м": CRITERIA_COLOR_PUMP_5M,
        "ЭКСТР-1м": CRITERIA_COLOR_PUMP_1M,
        "КОМБО": CRITERIA_COLOR_COMBO,
    }
    return colors.get(criteria, "#3C3C3C")


# Глобальный менеджер состояния
_header_manager = None


def get_header_manager() -> HeaderStateManager:
    """Возвращает глобальный менеджер состояния заголовков."""
    global _header_manager
    if _header_manager is None:
        _header_manager = HeaderStateManager()
    return _header_manager
