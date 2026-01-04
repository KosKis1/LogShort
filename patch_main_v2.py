#!/usr/bin/env python3
"""
ПАТЧ V2 ДЛЯ main.py
Добавляет прогресс-бары и интеграцию с V2 модулями

Запуск: python patch_main_v2.py
"""

import os
import shutil
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_FILE = os.path.join(BASE_DIR, "main.py")
BACKUP_FILE = MAIN_FILE + f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

print("=" * 70)
print("ПАТЧ V2 ДЛЯ main.py")
print("=" * 70)
print()

# Проверяем существование файла
if not os.path.exists(MAIN_FILE):
    print(f"[ERROR] Файл не найден: {MAIN_FILE}")
    input("Нажмите Enter...")
    exit(1)

# Читаем файл
with open(MAIN_FILE, 'r', encoding='utf-8') as f:
    content = f.read()
    lines = content.split('\n')

print(f"[TRACE] Загружено {len(lines)} строк")

# Создаём бэкап
shutil.copy(MAIN_FILE, BACKUP_FILE)
print(f"[OK] Бэкап создан: {os.path.basename(BACKUP_FILE)}")

changes = []

# ============================================================================
# 1. ДОБАВЛЯЕМ ИМПОРТЫ V2 (после существующих импортов)
# ============================================================================
print("\n[1] Добавление импортов V2...")

v2_import_block = '''
# === V2 IMPORTS ===
try:
    from core.config_v2 import USE_NEW_UI
    from core.engine_v2 import update_scan_timers, get_scan_state
    from ui.table_headers_v2 import get_header_manager
    V2_AVAILABLE = True
    print("[V2] Модули V2 загружены успешно")
except ImportError as e:
    V2_AVAILABLE = False
    USE_NEW_UI = False
    print(f"[V2] Модули V2 недоступны: {e}")
# === END V2 IMPORTS ===
'''

# Ищем место для вставки (после последнего import/from в начале файла)
insert_line = 0
for i, line in enumerate(lines[:60]):
    if line.startswith('import ') or line.startswith('from '):
        insert_line = i + 1
    # Пропускаем блок try/except для chart_window
    if 'try:' in line and i > 30:
        break

# Проверяем, не добавлен ли уже V2
if 'V2_AVAILABLE' not in content:
    lines.insert(insert_line + 5, v2_import_block)  # После импортов
    changes.append(f"Строка ~{insert_line + 5}: Добавлены импорты V2")
    print(f"   [OK] Импорты добавлены после строки {insert_line}")
else:
    print("   [SKIP] Импорты V2 уже есть")

# ============================================================================
# 2. МОДИФИЦИРУЕМ _tick_full_countdown ДЛЯ V2 ПРОГРЕСС-БАРОВ
# ============================================================================
print("\n[2] Модификация _tick_full_countdown...")

# Ищем метод _tick_full_countdown
new_lines = []
i = 0
modified_tick_full = False

while i < len(lines):
    line = lines[i]
    
    # Находим начало метода _tick_full_countdown
    if 'def _tick_full_countdown(self):' in line and not modified_tick_full:
        new_lines.append(line)
        i += 1
        
        # Добавляем вызов V2 в начало метода
        # Ищем первую строку после def (обычно комментарий или код)
        while i < len(lines) and (lines[i].strip() == '' or lines[i].strip().startswith('"""') or lines[i].strip().startswith('#')):
            new_lines.append(lines[i])
            i += 1
        
        # Вставляем вызов V2
        v2_call = '''        # === V2 Progress Update ===
        if V2_AVAILABLE and USE_NEW_UI:
            try:
                self._update_v2_progress()
            except Exception as e:
                pass  # Тихо игнорируем ошибки V2
        # === END V2 ===
'''
        if 'V2_AVAILABLE' not in lines[i-1] and 'V2_AVAILABLE' not in lines[i]:
            new_lines.append(v2_call)
            modified_tick_full = True
            changes.append("Метод _tick_full_countdown: добавлен вызов V2")
            print("   [OK] Вызов V2 добавлен в _tick_full_countdown")
        
        continue
    
    new_lines.append(line)
    i += 1

lines = new_lines

# ============================================================================
# 3. ДОБАВЛЯЕМ МЕТОД _update_v2_progress
# ============================================================================
print("\n[3] Добавление метода _update_v2_progress...")

v2_method = '''
    def _update_v2_progress(self):
        """Обновление прогресс-баров V2."""
        try:
            from core.engine_v2 import update_scan_timers, get_scan_state
            from ui.table_headers_v2 import get_header_manager
            from core.config_v2 import USE_NEW_UI
            
            if not USE_NEW_UI:
                return
            
            # Обновляем таймеры движка
            update_scan_timers()
            scan_state = get_scan_state()
            
            # Получаем header manager
            header_mgr = get_header_manager()
            
            # Обновляем таймеры уровней
            header_mgr.update_timers(
                level1_left=scan_state.get('level1_countdown', 0),
                level2_left=scan_state.get('level2_countdown', 0),
                level3_left=scan_state.get('level3_countdown', 0)
            )
            
            # Подсчёт по данным из таблиц
            # TOP200 данные
            top200_data = getattr(self, 'all_results', {})
            if top200_data:
                rows = list(top200_data.values())
                class_count = sum(1 for r in rows if getattr(r, 'watch_type', None))
                pump5m_count = sum(1 for r in rows if 'Памп' in str(getattr(r, 'watch_type', '') or ''))
                extr1m_count = sum(1 for r in rows if getattr(r, 'range_position', 0) > 90)
                combo_count = sum(1 for r in rows if getattr(r, 'watch_type', None) and getattr(r, 'range_position', 0) > 85)
                
                header_mgr.update_criteria_counts(
                    class_count=class_count,
                    pump5m_count=pump5m_count,
                    extr1m_count=extr1m_count,
                    combo_count=combo_count
                )
            
            # Кандидаты данные
            candidates_data = getattr(self, 'candidates', [])
            if candidates_data:
                watch_count = sum(1 for c in candidates_data if getattr(c, 'status', '') == 'Наблюдение')
                interest_count = sum(1 for c in candidates_data if getattr(c, 'status', '') == 'Интерес')
                ready_count = sum(1 for c in candidates_data if getattr(c, 'status', '') == 'Готовность')
                entry_count = sum(1 for c in candidates_data if getattr(c, 'status', '') == 'ВХОД')
                
                header_mgr.update_status_counts(
                    watch=watch_count,
                    interest=interest_count,
                    ready=ready_count,
                    entry=entry_count
                )
            
            # Генерируем текст заголовков
            top200_header = header_mgr.get_top200_header_text()
            candidates_header = header_mgr.get_candidates_header_text()
            
            # Обновляем метки (используем существующие lbl_full_timer и lbl_cand_timer)
            if hasattr(self, 'lbl_full_timer') and top200_header:
                # Заменяем простой текст на V2 прогресс-бар
                self.lbl_full_timer.setText(top200_header)
                self.lbl_full_timer.setWordWrap(True)
                self.lbl_full_timer.setMinimumHeight(40)
            
            if hasattr(self, 'lbl_cand_timer') and candidates_header:
                self.lbl_cand_timer.setText(candidates_header)
                self.lbl_cand_timer.setWordWrap(True)
                self.lbl_cand_timer.setMinimumHeight(40)
                
        except Exception as e:
            # При ошибке просто пропускаем V2 обновление
            print(f"[V2 ERROR] {e}")
            pass
'''

# Проверяем, не добавлен ли уже метод
content_check = '\n'.join(lines)
if 'def _update_v2_progress(self):' not in content_check:
    # Ищем место для вставки (перед closeEvent или в конце класса)
    insert_idx = None
    for i, line in enumerate(lines):
        if 'def closeEvent(self' in line:
            insert_idx = i
            break
    
    if insert_idx:
        lines.insert(insert_idx, v2_method)
        changes.append(f"Строка {insert_idx}: Добавлен метод _update_v2_progress")
        print(f"   [OK] Метод добавлен перед closeEvent (строка {insert_idx})")
    else:
        print("   [ERROR] Не найдено место для вставки метода")
else:
    print("   [SKIP] Метод _update_v2_progress уже есть")

# ============================================================================
# СОХРАНЯЕМ РЕЗУЛЬТАТ
# ============================================================================
print("\n" + "=" * 70)
print("РЕЗУЛЬТАТ:")
print("=" * 70)

if changes:
    final_content = '\n'.join(lines)
    with open(MAIN_FILE, 'w', encoding='utf-8') as f:
        f.write(final_content)
    
    for change in changes:
        print(f"   [+] {change}")
    
    print(f"\n[OK] Файл main.py обновлён!")
    print(f"[OK] Бэкап: {os.path.basename(BACKUP_FILE)}")
else:
    print("   Изменений не требуется - V2 уже интегрирован")

print("\n" + "=" * 70)
print("СЛЕДУЮЩИЙ ШАГ:")
print("=" * 70)
print("   Перезапустите сканер через _Start.bat")
print()
input("Нажмите Enter для закрытия...")
