#!/usr/bin/env python3
"""
ФИНАЛЬНОЕ ИСПРАВЛЕНИЕ V2
Проблема: старый код перезаписывает V2 прогресс-бары
Решение: добавляем return после V2 обновления
"""

import os
import shutil
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_FILE = os.path.join(BASE_DIR, "main.py")
LOG_FILE = os.path.join(BASE_DIR, "fix_v2_final_trace.log")

trace_log = []

def trace(msg):
    print(msg)
    trace_log.append(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} | {msg}")

def save_trace():
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(trace_log))

trace("=" * 70)
trace("ФИНАЛЬНОЕ ИСПРАВЛЕНИЕ V2")
trace("=" * 70)

# Читаем файл
trace("\n[STEP 1] Чтение main.py...")
with open(MAIN_FILE, 'r', encoding='utf-8') as f:
    content = f.read()
trace(f"   Размер: {len(content)} символов")

# Создаём бэкап
backup = MAIN_FILE + f".pre_final_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
shutil.copy(MAIN_FILE, backup)
trace(f"   Бэкап: {os.path.basename(backup)}")

# ============================================================================
# ИСПРАВЛЕНИЕ 1: _tick_full_countdown - добавляем return после V2
# ============================================================================
trace("\n[STEP 2] Исправление _tick_full_countdown...")

old_v2_call = '''        # === V2 CALL ===
        print("[TRACE-V2] _tick_full_countdown выполняется")
        if V2_AVAILABLE and USE_NEW_UI:
            try:
                self._update_v2_progress()
            except Exception as e:
                print(f"[TRACE-V2] Ошибка вызова: {e}")
        # === END V2 CALL ==='''

new_v2_call = '''        # === V2 CALL ===
        print("[TRACE-V2] _tick_full_countdown выполняется")
        if V2_AVAILABLE and USE_NEW_UI:
            try:
                self._update_v2_progress()
                print("[TRACE-V2] V2 обновлён, return")
                return  # V2 уже обновил UI, не перезаписываем
            except Exception as e:
                print(f"[TRACE-V2] Ошибка вызова: {e}")
        # === END V2 CALL ==='''

if old_v2_call in content:
    content = content.replace(old_v2_call, new_v2_call)
    trace("   [OK] Добавлен return после V2 в _tick_full_countdown")
else:
    trace("   [WARN] Старый блок V2 не найден, пробую альтернативу...")
    
    # Альтернативный поиск
    if 'self._update_v2_progress()' in content and 'return  # V2' not in content:
        # Находим строку с вызовом и добавляем return после
        lines = content.split('\n')
        new_lines = []
        for i, line in enumerate(lines):
            new_lines.append(line)
            if 'self._update_v2_progress()' in line and 'return' not in lines[i+1] if i+1 < len(lines) else True:
                indent = len(line) - len(line.lstrip())
                new_lines.append(' ' * indent + '    print("[TRACE-V2] V2 обновлён, return")')
                new_lines.append(' ' * indent + '    return  # V2 уже обновил UI')
                trace(f"   [OK] return добавлен после строки {i+1}")
        content = '\n'.join(new_lines)

# ============================================================================
# ИСПРАВЛЕНИЕ 2: _tick_cand_countdown - аналогично
# ============================================================================
trace("\n[STEP 3] Проверка _tick_cand_countdown...")

# Проверяем, есть ли V2 вызов в _tick_cand_countdown
if '_tick_cand_countdown' in content:
    # Находим метод
    lines = content.split('\n')
    in_method = False
    method_has_v2 = False
    
    for i, line in enumerate(lines):
        if 'def _tick_cand_countdown' in line:
            in_method = True
            trace(f"   Метод найден на строке {i+1}")
        elif in_method and line.strip().startswith('def '):
            break
        elif in_method and 'V2_AVAILABLE' in line:
            method_has_v2 = True
    
    if not method_has_v2:
        trace("   [INFO] V2 вызов не нужен в _tick_cand_countdown (обновляется через _tick_full_countdown)")
    else:
        trace("   [OK] V2 вызов уже есть")

# ============================================================================
# ПРОВЕРКА И СОХРАНЕНИЕ
# ============================================================================
trace("\n[STEP 4] Проверка синтаксиса...")

temp_file = MAIN_FILE + ".temp"
with open(temp_file, 'w', encoding='utf-8') as f:
    f.write(content)

import py_compile
try:
    py_compile.compile(temp_file, doraise=True)
    trace("   [OK] Синтаксис корректен!")
    shutil.move(temp_file, MAIN_FILE)
    trace("   [OK] main.py сохранён")
except py_compile.PyCompileError as e:
    trace(f"   [ERROR] Синтаксис: {e}")
    if os.path.exists(temp_file):
        os.remove(temp_file)

# ============================================================================
# ФИНАЛЬНАЯ ПРОВЕРКА
# ============================================================================
trace("\n[STEP 5] Финальная проверка...")

with open(MAIN_FILE, 'r', encoding='utf-8') as f:
    final = f.read()

if 'return  # V2' in final:
    trace("   [OK] return после V2 присутствует")
else:
    trace("   [FAIL] return после V2 НЕ найден!")

# Показываем итоговый код _tick_full_countdown
trace("\n[ИТОГ] Метод _tick_full_countdown:")
lines = final.split('\n')
for i, line in enumerate(lines):
    if 'def _tick_full_countdown' in line:
        for j in range(i, min(i+25, len(lines))):
            trace(f"   {j+1}: {lines[j]}")
            if j > i and lines[j].strip().startswith('def '):
                break
        break

trace("\n" + "=" * 70)
trace("ГОТОВО! Перезапустите сканер через _Start.bat")
trace("=" * 70)

save_trace()
input("\nНажмите Enter...")
