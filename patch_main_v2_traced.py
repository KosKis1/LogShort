#!/usr/bin/env python3
"""
ПАТЧ V2 ДЛЯ main.py С ТРАССИРОВКОЙ
Каждый шаг логируется для отладки
"""

import os
import shutil
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_FILE = os.path.join(BASE_DIR, "main.py")
LOG_FILE = os.path.join(BASE_DIR, "patch_v2_trace.log")

# Трассировочный лог
trace_log = []

def trace(msg):
    """Трассировка - выводит и сохраняет"""
    print(msg)
    trace_log.append(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} | {msg}")

def save_trace():
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(trace_log))
    print(f"\n[TRACE LOG] Сохранён: {LOG_FILE}")

# ============================================================================
trace("=" * 70)
trace("ПАТЧ V2 ДЛЯ main.py С ТРАССИРОВКОЙ")
trace("=" * 70)

# 1. Проверяем файл
trace(f"\n[STEP 1] Проверка файла: {MAIN_FILE}")
if not os.path.exists(MAIN_FILE):
    trace(f"   [FATAL] Файл не найден!")
    save_trace()
    input("Enter...")
    exit(1)

trace(f"   [OK] Файл существует")

# 2. Читаем файл
trace(f"\n[STEP 2] Чтение файла...")
with open(MAIN_FILE, 'r', encoding='utf-8') as f:
    original_content = f.read()
    
trace(f"   [OK] Прочитано {len(original_content)} символов, {len(original_content.splitlines())} строк")

# Проверяем целостность
if 'class MainWindow' not in original_content:
    trace(f"   [FATAL] Файл повреждён - нет class MainWindow!")
    save_trace()
    input("Enter...")
    exit(1)
    
trace(f"   [OK] class MainWindow найден")

# 3. Создаём бэкап
trace(f"\n[STEP 3] Создание бэкапа...")
backup_name = f"main.py.bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
backup_path = os.path.join(BASE_DIR, backup_name)
shutil.copy(MAIN_FILE, backup_path)
trace(f"   [OK] Бэкап: {backup_name}")

# 4. Подготовка контента
content = original_content
lines = content.split('\n')
trace(f"\n[STEP 4] Подготовка к модификации...")

# ============================================================================
# БЛОК ИМПОРТОВ V2
# ============================================================================
V2_IMPORTS = '''
# === V2 IMPORTS (added by patch) ===
try:
    from core.config_v2 import USE_NEW_UI
    from core.engine_v2 import update_scan_timers, get_scan_state
    from ui.table_headers_v2 import get_header_manager
    V2_AVAILABLE = True
    print("[TRACE-V2] V2 модули загружены успешно")
except ImportError as e:
    V2_AVAILABLE = False
    USE_NEW_UI = False
    print(f"[TRACE-V2] V2 модули недоступны: {e}")
# === END V2 IMPORTS ===
'''

# ============================================================================
# МЕТОД _update_v2_progress
# ============================================================================
V2_METHOD = '''
    def _update_v2_progress(self):
        """[V2] Обновление прогресс-баров."""
        print("[TRACE-V2] _update_v2_progress вызван")
        try:
            if not V2_AVAILABLE:
                print("[TRACE-V2] V2_AVAILABLE = False, выход")
                return
            if not USE_NEW_UI:
                print("[TRACE-V2] USE_NEW_UI = False, выход")
                return
            
            print("[TRACE-V2] Обновляю таймеры...")
            update_scan_timers()
            scan_state = get_scan_state()
            
            header_mgr = get_header_manager()
            
            # Обновляем таймеры
            header_mgr.update_timers(
                level1_left=scan_state.get('level1_countdown', 0),
                level2_left=scan_state.get('level2_countdown', 0),
                level3_left=scan_state.get('level3_countdown', 0)
            )
            
            # Данные TOP200
            top200_data = getattr(self, 'all_results', {})
            if top200_data:
                rows = list(top200_data.values())
                class_count = sum(1 for r in rows if getattr(r, 'watch_type', None))
                pump5m_count = sum(1 for r in rows if 'Памп' in str(getattr(r, 'watch_type', '') or ''))
                extr1m_count = sum(1 for r in rows if getattr(r, 'range_position', 0) > 90)
                combo_count = sum(1 for r in rows if getattr(r, 'watch_type', None) and getattr(r, 'range_position', 0) > 85)
                header_mgr.update_criteria_counts(class_count, pump5m_count, extr1m_count, combo_count)
            
            # Данные кандидатов
            candidates_data = getattr(self, 'candidates', [])
            if candidates_data:
                watch = sum(1 for c in candidates_data if getattr(c, 'status', '') == 'Наблюдение')
                interest = sum(1 for c in candidates_data if getattr(c, 'status', '') == 'Интерес')
                ready = sum(1 for c in candidates_data if getattr(c, 'status', '') == 'Готовность')
                entry = sum(1 for c in candidates_data if getattr(c, 'status', '') == 'ВХОД')
                header_mgr.update_status_counts(watch, interest, ready, entry)
            
            # Обновляем UI
            top200_text = header_mgr.get_top200_header_text()
            cand_text = header_mgr.get_candidates_header_text()
            
            print(f"[TRACE-V2] top200_text: {top200_text[:50] if top200_text else 'None'}...")
            print(f"[TRACE-V2] cand_text: {cand_text[:50] if cand_text else 'None'}...")
            
            if hasattr(self, 'lbl_full_timer') and top200_text:
                self.lbl_full_timer.setText(top200_text)
                self.lbl_full_timer.setWordWrap(True)
                self.lbl_full_timer.setMinimumHeight(45)
                print("[TRACE-V2] lbl_full_timer обновлён")
            
            if hasattr(self, 'lbl_cand_timer') and cand_text:
                self.lbl_cand_timer.setText(cand_text)
                self.lbl_cand_timer.setWordWrap(True)
                self.lbl_cand_timer.setMinimumHeight(45)
                print("[TRACE-V2] lbl_cand_timer обновлён")
                
        except Exception as e:
            print(f"[TRACE-V2] Ошибка: {e}")

'''

# ============================================================================
# 5. ДОБАВЛЯЕМ ИМПОРТЫ
# ============================================================================
trace(f"\n[STEP 5] Добавление импортов V2...")

if 'V2_AVAILABLE' in content:
    trace(f"   [SKIP] V2_AVAILABLE уже есть в файле")
else:
    # Ищем последний import в начале файла
    last_import_line = 0
    in_try_block = False
    
    for i, line in enumerate(lines[:80]):
        stripped = line.strip()
        trace(f"   [SCAN] Line {i}: {stripped[:50]}")
        
        if stripped.startswith('import ') or stripped.startswith('from '):
            last_import_line = i
            trace(f"   [FOUND] Import на строке {i}")
        
        # Пропускаем try блоки
        if stripped == 'try:':
            in_try_block = True
        if in_try_block and stripped.startswith('except'):
            in_try_block = False
            # Ищем конец except блока
            for j in range(i+1, min(i+10, len(lines))):
                if lines[j].strip() and not lines[j].startswith(' '):
                    last_import_line = j - 1
                    break
    
    trace(f"   [RESULT] Последний import на строке {last_import_line}")
    
    # Вставляем после последнего импорта
    insert_pos = last_import_line + 1
    trace(f"   [INSERT] Вставка на позицию {insert_pos}")
    
    lines.insert(insert_pos, V2_IMPORTS)
    trace(f"   [OK] Импорты V2 добавлены")

# ============================================================================
# 6. ДОБАВЛЯЕМ МЕТОД
# ============================================================================
content = '\n'.join(lines)
trace(f"\n[STEP 6] Добавление метода _update_v2_progress...")

if 'def _update_v2_progress(self):' in content:
    trace(f"   [SKIP] Метод уже существует")
else:
    # Ищем def closeEvent
    if 'def closeEvent(self' in content:
        trace(f"   [FOUND] closeEvent найден")
        content = content.replace(
            '    def closeEvent(self',
            V2_METHOD + '\n    def closeEvent(self'
        )
        trace(f"   [OK] Метод добавлен перед closeEvent")
    else:
        trace(f"   [ERROR] closeEvent не найден!")

# ============================================================================
# 7. ДОБАВЛЯЕМ ВЫЗОВ В _tick_full_countdown
# ============================================================================
trace(f"\n[STEP 7] Добавление вызова V2 в _tick_full_countdown...")

V2_CALL = '''        # === V2 CALL ===
        print("[TRACE-V2] _tick_full_countdown выполняется")
        if V2_AVAILABLE and USE_NEW_UI:
            try:
                self._update_v2_progress()
            except Exception as e:
                print(f"[TRACE-V2] Ошибка вызова: {e}")
        # === END V2 CALL ===
'''

if 'V2_AVAILABLE and USE_NEW_UI' in content and '_tick_full_countdown' in content:
    # Проверяем, есть ли вызов именно в _tick_full_countdown
    tick_pos = content.find('def _tick_full_countdown')
    next_def = content.find('\n    def ', tick_pos + 10)
    tick_body = content[tick_pos:next_def] if next_def > 0 else content[tick_pos:]
    
    if 'V2_AVAILABLE and USE_NEW_UI' in tick_body:
        trace(f"   [SKIP] Вызов V2 уже есть в _tick_full_countdown")
    else:
        trace(f"   [NEED] Вызов V2 нужно добавить")
else:
    trace(f"   [NEED] Добавляю вызов V2...")

# Находим метод и добавляем вызов
lines = content.split('\n')
new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    new_lines.append(line)
    
    if 'def _tick_full_countdown(self):' in line:
        trace(f"   [FOUND] _tick_full_countdown на строке {i}")
        i += 1
        # Добавляем docstring если есть
        while i < len(lines):
            new_lines.append(lines[i])
            if '"""' in lines[i] and lines[i].strip() != '"""':
                # Однострочный docstring
                i += 1
                break
            elif '"""' in lines[i]:
                # Многострочный - ищем закрывающий
                i += 1
                while i < len(lines) and '"""' not in lines[i]:
                    new_lines.append(lines[i])
                    i += 1
                if i < len(lines):
                    new_lines.append(lines[i])
                    i += 1
                break
            i += 1
            if lines[i-1].strip() and not lines[i-1].strip().startswith('"""'):
                break
        
        # Проверяем, нет ли уже вызова
        if i < len(lines) and 'V2_AVAILABLE' not in lines[i]:
            new_lines.append(V2_CALL)
            trace(f"   [OK] Вызов V2 добавлен после строки {i}")
        continue
    
    i += 1

content = '\n'.join(new_lines)

# ============================================================================
# 8. ПРОВЕРКА СИНТАКСИСА
# ============================================================================
trace(f"\n[STEP 8] Проверка синтаксиса...")

# Сохраняем во временный файл
temp_file = MAIN_FILE + ".temp"
with open(temp_file, 'w', encoding='utf-8') as f:
    f.write(content)

import py_compile
try:
    py_compile.compile(temp_file, doraise=True)
    trace(f"   [OK] Синтаксис корректен!")
    
    # Заменяем основной файл
    shutil.move(temp_file, MAIN_FILE)
    trace(f"   [OK] main.py обновлён")
    
except py_compile.PyCompileError as e:
    trace(f"   [ERROR] Ошибка синтаксиса: {e}")
    trace(f"   [ROLLBACK] Восстанавливаю из бэкапа...")
    shutil.copy(backup_path, MAIN_FILE)
    if os.path.exists(temp_file):
        os.remove(temp_file)
    trace(f"   [OK] Файл восстановлен")

# ============================================================================
# 9. ФИНАЛЬНАЯ ПРОВЕРКА
# ============================================================================
trace(f"\n[STEP 9] Финальная проверка...")

with open(MAIN_FILE, 'r', encoding='utf-8') as f:
    final_content = f.read()

checks = [
    ('V2_AVAILABLE', 'Переменная V2_AVAILABLE'),
    ('from core.config_v2', 'Импорт config_v2'),
    ('def _update_v2_progress', 'Метод _update_v2_progress'),
    ('self._update_v2_progress()', 'Вызов _update_v2_progress'),
]

all_ok = True
for pattern, desc in checks:
    found = pattern in final_content
    status = "[OK]" if found else "[FAIL]"
    trace(f"   {status} {desc}")
    if not found:
        all_ok = False

# ============================================================================
trace(f"\n" + "=" * 70)
if all_ok:
    trace("УСПЕХ! V2 интегрирован в main.py")
    trace("Запустите сканер через _Start.bat")
else:
    trace("ОШИБКА! Не все компоненты добавлены")
trace("=" * 70)

save_trace()
input("\nНажмите Enter...")
