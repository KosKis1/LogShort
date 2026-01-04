# ============================================================
# PATCH STEP 2 - Интеграция новых таблиц и UI
# ============================================================
# Версия: v2.0
# Дата: 02.01.2025
# ============================================================

"""
ШАГ 2: ИНТЕГРАЦИЯ НОВЫХ ТАБЛИЦ
==============================

Этот скрипт модифицирует auto-short_v095_with_trainer_bridge.py:
1. Добавляет импорты новых модулей
2. Обновляет заголовки таблиц (новые колонки)
3. Добавляет прогресс-бары в заголовки
4. Обновляет fill_main_row и render_focus_table

ИСПОЛЬЗОВАНИЕ:
    python _patch_step2.py

После запуска:
- Создаётся backup: auto-short_v095_with_trainer_bridge.py.pre_step2
- Модифицируется главный файл
"""

import os
import sys
import re
import shutil
from datetime import datetime

# Путь к главному файлу
MAIN_FILE = "auto-short_v095_with_trainer_bridge.py"
BACKUP_SUFFIX = ".pre_step2"


def create_backup(filepath: str) -> str:
    """Создаёт бэкап файла."""
    backup_path = filepath + BACKUP_SUFFIX
    shutil.copy2(filepath, backup_path)
    print(f"✅ Бэкап создан: {backup_path}")
    return backup_path


def read_file(filepath: str) -> str:
    """Читает файл."""
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def write_file(filepath: str, content: str):
    """Записывает файл."""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ Файл обновлён: {filepath}")


def patch_imports(content: str) -> str:
    """Добавляет импорты новых модулей после существующих импортов."""
    
    # Ищем место после импортов core.params
    import_marker = "from core.params import P"
    
    new_imports = '''
# === V2 IMPORTS (Step 2) ===
try:
    from core.config_v2 import (
        USE_NEW_UI, USE_NEW_FREQUENCIES, USE_NEW_SCORING, USE_NEW_ALGORITHMS,
        SCAN_LEVEL1_INTERVAL_SEC, SCAN_LEVEL2_INTERVAL_SEC, SCAN_LEVEL3_INTERVAL_SEC,
        STATUS_THRESHOLD_WATCH, STATUS_THRESHOLD_INTEREST, STATUS_THRESHOLD_READY,
    )
    from core.engine_v2 import (
        get_scan_state, update_scan_timers, should_run_level1, should_run_level2, should_run_level3,
        mark_level_complete, mark_level_started, calculate_score_v2, ScanMetrics,
    )
    from strategies.short_after_pump_v2 import ShortAfterPumpV2, get_strategy as get_strategy_v2
    from ui.table_headers_v2 import (
        get_header_manager, TABLE1_HEADERS, TABLE2_HEADERS,
        format_impulse, format_volume_spike, format_relative_weakness,
        format_trend, format_exhaustion, format_z_score, format_quality_stars,
        format_criteria_type, format_maturity, format_volume_dynamic,
        get_status_color, get_criteria_color,
    )
    V2_AVAILABLE = True
    print("[V2] Новые модули v2 загружены успешно")
except ImportError as e:
    V2_AVAILABLE = False
    USE_NEW_UI = False
    print(f"[V2] Модули v2 не найдены, используем старую версию: {e}")
# === END V2 IMPORTS ===
'''
    
    if "V2_AVAILABLE" in content:
        print("⚠️ Импорты V2 уже добавлены, пропускаем")
        return content
    
    if import_marker in content:
        content = content.replace(
            import_marker,
            import_marker + new_imports
        )
        print("✅ Импорты V2 добавлены")
    else:
        print("❌ Не найден маркер для импортов")
    
    return content


def patch_table1_headers(content: str) -> str:
    """Обновляет заголовки первой таблицы (TOP200)."""
    
    old_headers = '''        # Колонки TOP200 (без Статус/Сигнал - они во второй таблице)
        headers = [
            "Ранг", "Монета", "Позиция %", "До хая %", "24ч %",
            "Цена", "Оборот", "Фандинг", "Макс 24ч", "Мин 24ч"
        ]
        self.tbl_main.setHorizontalHeaderLabels(headers)'''
    
    new_headers = '''        # Колонки TOP200 (V2: новые колонки с импульсом, слабостью, зрелостью)
        if V2_AVAILABLE and USE_NEW_UI:
            headers = TABLE1_HEADERS  # Из table_headers_v2.py
            self.tbl_main.setColumnCount(len(headers))
        else:
            headers = [
                "Ранг", "Монета", "Позиция %", "До хая %", "24ч %",
                "Цена", "Оборот", "Фандинг", "Макс 24ч", "Мин 24ч"
            ]
        self.tbl_main.setHorizontalHeaderLabels(headers)'''
    
    if "TABLE1_HEADERS" in content and "V2_AVAILABLE and USE_NEW_UI" in content:
        print("⚠️ Заголовки таблицы 1 уже обновлены, пропускаем")
        return content
    
    if old_headers in content:
        content = content.replace(old_headers, new_headers)
        print("✅ Заголовки таблицы 1 обновлены")
    else:
        print("❌ Не найден блок заголовков таблицы 1")
    
    return content


def patch_table2_headers(content: str) -> str:
    """Обновляет заголовки второй таблицы (Кандидаты)."""
    
    old_headers = '''        # Расширенные метрики: Статус и Сигнал здесь, слева важные
        focus_headers = ["Монета", "Статус", "Тип сигнала", "Сигнал", "Скор", "Позиция %", "До хая %", "24ч %",
            "Фандинг", "Цена", "Вход", "SL", "TP1", "R/R",
            "Оборот", "В списке", "Осталось"
        ]
        self.tbl_focus.setColumnCount(len(focus_headers))'''
    
    new_headers = '''        # V2: Расширенные метрики с Exhaustion, RW, Z-Score, Качеством
        if V2_AVAILABLE and USE_NEW_UI:
            focus_headers = TABLE2_HEADERS  # Из table_headers_v2.py
        else:
            focus_headers = ["Монета", "Статус", "Тип сигнала", "Сигнал", "Скор", "Позиция %", "До хая %", "24ч %",
                "Фандинг", "Цена", "Вход", "SL", "TP1", "R/R",
                "Оборот", "В списке", "Осталось"
            ]
        self.tbl_focus.setColumnCount(len(focus_headers))'''
    
    if "TABLE2_HEADERS" in content and "V2_AVAILABLE and USE_NEW_UI" in content:
        print("⚠️ Заголовки таблицы 2 уже обновлены, пропускаем")
        return content
    
    if old_headers in content:
        content = content.replace(old_headers, new_headers)
        print("✅ Заголовки таблицы 2 обновлены")
    else:
        print("❌ Не найден блок заголовков таблицы 2")
    
    return content


def patch_top200_counter_label(content: str) -> str:
    """Обновляет метку счётчика TOP200 для поддержки прогресс-баров."""
    
    old_label = '''        # === Метка счётчика TOP200 ===
        self.lbl_top200_counter = QLabel("Пересчитано: 0 из 200 | След. пересчёт через --:--")
        self.lbl_top200_counter.setStyleSheet("color: #00d4ff; font-size: 13px; padding: 4px; font-weight: bold;")'''
    
    new_label = '''        # === Метка счётчика TOP200 (V2: с прогресс-барами) ===
        self.lbl_top200_counter = QLabel("Пересчитано: 0 из 200 | След. пересчёт через --:--")
        self.lbl_top200_counter.setStyleSheet("color: #00d4ff; font-size: 13px; padding: 4px; font-weight: bold;")
        self.lbl_top200_counter.setWordWrap(True)
        self.lbl_top200_counter.setMinimumHeight(50 if (V2_AVAILABLE and USE_NEW_UI) else 20)'''
    
    if "setMinimumHeight(50" in content:
        print("⚠️ Метка TOP200 уже обновлена, пропускаем")
        return content
    
    if old_label in content:
        content = content.replace(old_label, new_label)
        print("✅ Метка TOP200 обновлена")
    else:
        print("❌ Не найден блок метки TOP200")
    
    return content


def patch_candidates_counter_label(content: str) -> str:
    """Обновляет метку счётчика кандидатов."""
    
    old_label = '''        # === Метка счётчика кандидатов ===
        self.lbl_candidates_counter = QLabel("Обновление: --:--:--")
        self.lbl_candidates_counter.setStyleSheet("color: #ffd700; font-size: 13px; padding: 4px; font-weight: bold;")
        self._candidates_flash_timer = None'''
    
    new_label = '''        # === Метка счётчика кандидатов (V2: с прогресс-барами) ===
        self.lbl_candidates_counter = QLabel("Обновление: --:--:--")
        self.lbl_candidates_counter.setStyleSheet("color: #ffd700; font-size: 13px; padding: 4px; font-weight: bold;")
        self.lbl_candidates_counter.setWordWrap(True)
        self.lbl_candidates_counter.setMinimumHeight(60 if (V2_AVAILABLE and USE_NEW_UI) else 20)
        self._candidates_flash_timer = None'''
    
    if "setMinimumHeight(60" in content:
        print("⚠️ Метка кандидатов уже обновлена, пропускаем")
        return content
    
    if old_label in content:
        content = content.replace(old_label, new_label)
        print("✅ Метка кандидатов обновлена")
    else:
        print("❌ Не найден блок метки кандидатов")
    
    return content


def patch_tick_status_lines(content: str) -> str:
    """Добавляет обновление прогресс-баров V2 в _tick_status_lines."""
    
    # Ищем начало функции _tick_status_lines
    old_func_start = '''    def _tick_status_lines(self):
        # Universe line
        try:'''
    
    new_func_start = '''    def _tick_status_lines(self):
        # V2: Обновляем прогресс-бары если доступны
        if V2_AVAILABLE and USE_NEW_UI:
            try:
                self._update_v2_progress_bars()
            except Exception:
                pass
        
        # Universe line
        try:'''
    
    if "_update_v2_progress_bars" in content:
        print("⚠️ _tick_status_lines уже обновлён, пропускаем")
        return content
    
    if old_func_start in content:
        content = content.replace(old_func_start, new_func_start)
        print("✅ _tick_status_lines обновлён")
    else:
        print("❌ Не найден _tick_status_lines")
    
    return content


def add_v2_progress_bars_method(content: str) -> str:
    """Добавляет метод _update_v2_progress_bars в MainWindow."""
    
    new_method = '''
    def _update_v2_progress_bars(self):
        """V2: Обновляет прогресс-бары в заголовках таблиц."""
        if not V2_AVAILABLE or not USE_NEW_UI:
            return
        
        try:
            # Обновляем таймеры в engine_v2
            update_scan_timers()
            scan_state = get_scan_state()
            
            # Получаем менеджер заголовков
            header_mgr = get_header_manager()
            
            # Обновляем таймеры
            header_mgr.update_level_timers(
                level1_remaining=scan_state.level1_remaining_sec,
                level2_remaining=scan_state.level2_remaining_sec,
                level3_remaining=scan_state.level3_remaining_sec,
                candidates_remaining=scan_state.level3_remaining_sec,  # Синхронизируем
            )
            
            # Обновляем статусы пересчёта
            header_mgr.set_level_in_progress(1, scan_state.level1_in_progress)
            header_mgr.set_level_in_progress(2, scan_state.level2_in_progress)
            header_mgr.set_level_in_progress(3, scan_state.level3_in_progress)
            
            # Обновляем счётчики
            selected = len(self._candidates_storage)
            classic = sum(1 for d in self._candidates_storage.values() if d.get("criteria_type") == "КЛАСС")
            pump_5m = sum(1 for d in self._candidates_storage.values() if d.get("criteria_type") == "ПАМП-5м")
            pump_1m = sum(1 for d in self._candidates_storage.values() if d.get("criteria_type") == "ЭКСТР-1м")
            combo = sum(1 for d in self._candidates_storage.values() if d.get("criteria_type") == "КОМБО")
            header_mgr.update_counts(selected, classic, pump_5m, pump_1m, combo)
            
            # Обновляем счётчики статусов
            watch = sum(1 for d in self._candidates_storage.values() if d.get("status") == "Наблюдение")
            interest = sum(1 for d in self._candidates_storage.values() if d.get("status") == "Интерес")
            ready = sum(1 for d in self._candidates_storage.values() if d.get("status") == "Готовность")
            entry = sum(1 for d in self._candidates_storage.values() if d.get("status") == "ВХОД")
            header_mgr.update_status_counts(watch, interest, ready, entry)
            
            # Обновляем текст меток
            self.lbl_top200_counter.setText(header_mgr.get_table1_header_text())
            self.lbl_candidates_counter.setText(header_mgr.get_table2_header_text())
            
        except Exception as e:
            # Fallback на старый формат
            pass

'''
    
    if "_update_v2_progress_bars" in content:
        print("⚠️ Метод _update_v2_progress_bars уже добавлен, пропускаем")
        return content
    
    # Ищем место для вставки (после _tick_status_lines)
    marker = "    def _flash_top_updated(self):"
    
    if marker in content:
        content = content.replace(marker, new_method + marker)
        print("✅ Метод _update_v2_progress_bars добавлен")
    else:
        print("❌ Не найден маркер для вставки _update_v2_progress_bars")
    
    return content


def main():
    """Главная функция патча."""
    print("=" * 60)
    print("🔧 ШАГ 2: ИНТЕГРАЦИЯ НОВЫХ ТАБЛИЦ И UI")
    print("=" * 60)
    print()
    
    # Проверяем что мы в правильной папке
    if not os.path.exists(MAIN_FILE):
        print(f"❌ Файл {MAIN_FILE} не найден!")
        print(f"   Запустите скрипт из папки C:\\Pythone\\Log_Short\\")
        return 1
    
    # Проверяем что V2 модули установлены
    v2_files = [
        "core/config_v2.py",
        "core/engine_v2.py",
        "strategies/short_after_pump_v2.py",
        "ui/table_headers_v2.py",
    ]
    
    missing = [f for f in v2_files if not os.path.exists(f)]
    if missing:
        print("❌ Не найдены файлы V2 (Шаг 1 не выполнен?):")
        for f in missing:
            print(f"   - {f}")
        return 1
    
    print("✅ Все V2 модули найдены")
    print()
    
    # Создаём бэкап
    backup_path = create_backup(MAIN_FILE)
    
    # Читаем файл
    content = read_file(MAIN_FILE)
    original_content = content
    
    print()
    print("🔄 Применяем патчи...")
    print()
    
    # Применяем патчи
    content = patch_imports(content)
    content = patch_table1_headers(content)
    content = patch_table2_headers(content)
    content = patch_top200_counter_label(content)
    content = patch_candidates_counter_label(content)
    content = patch_tick_status_lines(content)
    content = add_v2_progress_bars_method(content)
    
    # Проверяем были ли изменения
    if content == original_content:
        print()
        print("⚠️ Никаких изменений не внесено (возможно, патчи уже применены)")
        return 0
    
    # Записываем изменения
    print()
    write_file(MAIN_FILE, content)
    
    print()
    print("=" * 60)
    print("✅ ШАГ 2 ЗАВЕРШЁН!")
    print()
    print(f"📁 Бэкап: {backup_path}")
    print(f"📝 Обновлён: {MAIN_FILE}")
    print()
    print("Теперь запустите сканер для проверки:")
    print("    python auto-short_v095_with_trainer_bridge.py")
    print()
    print("Если возникнут ошибки, восстановите бэкап:")
    print(f"    copy {backup_path} {MAIN_FILE}")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
