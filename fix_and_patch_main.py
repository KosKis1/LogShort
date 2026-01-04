#!/usr/bin/env python3
"""
ВОССТАНОВЛЕНИЕ main.py ИЗ БЭКАПА И ПРАВИЛЬНЫЙ ПАТЧ V2
"""

import os
import glob
import shutil
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_FILE = os.path.join(BASE_DIR, "main.py")

print("=" * 70)
print("ВОССТАНОВЛЕНИЕ И ПАТЧ V2 ДЛЯ main.py")
print("=" * 70)
print()

# ============================================================================
# 1. ВОССТАНАВЛИВАЕМ ИЗ БЭКАПА
# ============================================================================
print("[1] Поиск бэкапа...")

# Ищем последний бэкап
backups = glob.glob(os.path.join(BASE_DIR, "main.py.backup_*"))
if backups:
    latest_backup = max(backups, key=os.path.getmtime)
    print(f"   Найден бэкап: {os.path.basename(latest_backup)}")
    shutil.copy(latest_backup, MAIN_FILE)
    print(f"   [OK] main.py восстановлен из бэкапа")
else:
    print("   [WARN] Бэкап не найден, работаем с текущим файлом")

# ============================================================================
# 2. ЧИТАЕМ ФАЙЛ
# ============================================================================
print("\n[2] Загрузка main.py...")

with open(MAIN_FILE, 'r', encoding='utf-8') as f:
    content = f.read()

print(f"   Размер: {len(content)} символов")

# Проверяем что файл не повреждён
if 'class MainWindow' not in content:
    print("   [ERROR] Файл повреждён! class MainWindow не найден")
    input("Нажмите Enter...")
    exit(1)

# ============================================================================
# 3. ДОБАВЛЯЕМ ИМПОРТЫ V2 В ПРАВИЛЬНОЕ МЕСТО
# ============================================================================
print("\n[3] Добавление импортов V2...")

v2_imports = '''
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

if 'V2_AVAILABLE' not in content:
    # Ищем место ПОСЛЕ всех импортов, ПЕРЕД первым классом/функцией
    lines = content.split('\n')
    insert_idx = 0
    
    for i, line in enumerate(lines):
        # Пропускаем импорты
        stripped = line.strip()
        if stripped.startswith('import ') or stripped.startswith('from '):
            insert_idx = i + 1
        # Пропускаем try/except блоки импортов
        elif stripped == 'try:':
            # Ищем конец try/except
            for j in range(i+1, min(i+20, len(lines))):
                if lines[j].strip().startswith('except'):
                    for k in range(j+1, min(j+10, len(lines))):
                        if lines[k].strip() and not lines[k].startswith(' ') and not lines[k].startswith('\t'):
                            insert_idx = k
                            break
                        elif lines[k].strip().startswith('print'):
                            insert_idx = k + 1
                    break
            continue
        # Останавливаемся на первом определении класса или функции верхнего уровня
        elif stripped.startswith('class ') or (stripped.startswith('def ') and not line.startswith(' ')):
            break
    
    # Вставляем импорты
    lines.insert(insert_idx, v2_imports)
    content = '\n'.join(lines)
    print(f"   [OK] Импорты V2 добавлены после строки {insert_idx}")
else:
    print("   [SKIP] Импорты V2 уже есть")

# ============================================================================
# 4. ДОБАВЛЯЕМ МЕТОД _update_v2_progress В КЛАСС MainWindow
# ============================================================================
print("\n[4] Добавление метода _update_v2_progress...")

v2_method = '''
    def _update_v2_progress(self):
        """Обновление прогресс-баров V2."""
        try:
            if not V2_AVAILABLE or not USE_NEW_UI:
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
            
            # Генерируем и устанавливаем текст
            top200_header = header_mgr.get_top200_header_text()
            candidates_header = header_mgr.get_candidates_header_text()
            
            if hasattr(self, 'lbl_full_timer') and top200_header:
                self.lbl_full_timer.setText(top200_header)
                self.lbl_full_timer.setWordWrap(True)
                self.lbl_full_timer.setMinimumHeight(40)
            
            if hasattr(self, 'lbl_cand_timer') and candidates_header:
                self.lbl_cand_timer.setText(candidates_header)
                self.lbl_cand_timer.setWordWrap(True)
                self.lbl_cand_timer.setMinimumHeight(40)
                
        except Exception as e:
            pass  # Тихо игнорируем ошибки V2

'''

if 'def _update_v2_progress(self):' not in content:
    # Вставляем перед closeEvent
    if 'def closeEvent(self' in content:
        content = content.replace(
            '    def closeEvent(self',
            v2_method + '    def closeEvent(self'
        )
        print("   [OK] Метод добавлен перед closeEvent")
    else:
        print("   [ERROR] closeEvent не найден")
else:
    print("   [SKIP] Метод уже есть")

# ============================================================================
# 5. ДОБАВЛЯЕМ ВЫЗОВ V2 В _tick_full_countdown
# ============================================================================
print("\n[5] Добавление вызова V2 в _tick_full_countdown...")

# Ищем метод и добавляем вызов
old_tick = '''    def _tick_full_countdown(self):
        """Тик таймера полного пересчёта."""'''

new_tick = '''    def _tick_full_countdown(self):
        """Тик таймера полного пересчёта."""
        # === V2 Update ===
        if V2_AVAILABLE and USE_NEW_UI:
            try:
                self._update_v2_progress()
            except:
                pass
        # === END V2 ==='''

if old_tick in content and 'V2_AVAILABLE and USE_NEW_UI' not in content.split('_tick_full_countdown')[1][:500]:
    content = content.replace(old_tick, new_tick)
    print("   [OK] Вызов V2 добавлен")
else:
    # Пробуем альтернативный вариант
    alt_old = '    def _tick_full_countdown(self):'
    if alt_old in content and 'V2_AVAILABLE and USE_NEW_UI' not in content.split('_tick_full_countdown')[1][:500]:
        # Находим позицию и вставляем после первой строки метода
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'def _tick_full_countdown(self):' in line:
                # Вставляем после docstring или сразу после def
                j = i + 1
                while j < len(lines) and (lines[j].strip().startswith('"""') or lines[j].strip() == ''):
                    j += 1
                    if '"""' in lines[j-1] and lines[j-1].strip() != '"""':
                        break
                
                v2_call = '''        # === V2 Update ===
        if V2_AVAILABLE and USE_NEW_UI:
            try:
                self._update_v2_progress()
            except:
                pass
        # === END V2 ==='''
                lines.insert(j, v2_call)
                content = '\n'.join(lines)
                print("   [OK] Вызов V2 добавлен (альтернативный метод)")
                break
    else:
        print("   [SKIP] Вызов уже есть или метод не найден")

# ============================================================================
# 6. СОХРАНЯЕМ
# ============================================================================
print("\n[6] Сохранение...")

# Создаём новый бэкап
new_backup = MAIN_FILE + f".pre_v2_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
if os.path.exists(MAIN_FILE):
    shutil.copy(MAIN_FILE, new_backup)

with open(MAIN_FILE, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"   [OK] main.py сохранён")
print(f"   [OK] Бэкап: {os.path.basename(new_backup)}")

# ============================================================================
# 7. ПРОВЕРКА СИНТАКСИСА
# ============================================================================
print("\n[7] Проверка синтаксиса...")

import py_compile
try:
    py_compile.compile(MAIN_FILE, doraise=True)
    print("   [OK] Синтаксис корректен!")
except py_compile.PyCompileError as e:
    print(f"   [ERROR] Ошибка синтаксиса: {e}")
    print("   Восстанавливаем из бэкапа...")
    shutil.copy(new_backup, MAIN_FILE)
    print("   [OK] Файл восстановлен")

print("\n" + "=" * 70)
print("ГОТОВО! Запустите сканер через _Start.bat")
print("=" * 70)
input("\nНажмите Enter...")
