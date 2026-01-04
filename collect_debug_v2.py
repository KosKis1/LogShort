#!/usr/bin/env python3
"""
ПОЛНЫЙ ДЕБАГ-СБОРЩИК V2
Собирает все файлы, логи, трассировку в один архив для анализа
"""

import os
import sys
import json
import shutil
import zipfile
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "debug_v2_output")
TIMESTAMP = datetime.now().strftime('%Y%m%d_%H%M%S')

print("=" * 70)
print("ПОЛНЫЙ ДЕБАГ-СБОРЩИК V2")
print(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)
print()

# Создаём папку для сбора
if os.path.exists(OUTPUT_DIR):
    shutil.rmtree(OUTPUT_DIR)
os.makedirs(OUTPUT_DIR)

report = []
report.append("=" * 80)
report.append(f"DEBUG REPORT V2 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
report.append("=" * 80)
report.append("")

# ============================================================================
# 1. СТРУКТУРА ПРОЕКТА
# ============================================================================
print("[1/7] Сбор структуры проекта...")
report.append("[1] СТРУКТУРА ПРОЕКТА")
report.append("-" * 80)

for folder in ['', 'core', 'ui', 'strategies', 'workers']:
    folder_path = os.path.join(BASE_DIR, folder) if folder else BASE_DIR
    if os.path.exists(folder_path):
        report.append(f"\n{folder if folder else 'ROOT'}:")
        for f in sorted(os.listdir(folder_path)):
            if f.endswith('.py'):
                full_path = os.path.join(folder_path, f)
                size = os.path.getsize(full_path)
                report.append(f"   {f:<40} {size:>8} bytes")

report.append("")

# ============================================================================
# 2. СОДЕРЖИМОЕ main.py (первые 100 строк + ключевые места)
# ============================================================================
print("[2/7] Анализ main.py...")
report.append("\n[2] АНАЛИЗ main.py")
report.append("-" * 80)

main_file = os.path.join(BASE_DIR, "main.py")
if os.path.exists(main_file):
    with open(main_file, 'r', encoding='utf-8', errors='ignore') as f:
        main_content = f.read()
        main_lines = main_content.split('\n')
    
    # Копируем main.py в debug
    shutil.copy(main_file, os.path.join(OUTPUT_DIR, "main.py"))
    
    report.append(f"Размер: {len(main_content)} символов, {len(main_lines)} строк")
    report.append("")
    
    # Первые 60 строк (импорты)
    report.append("ПЕРВЫЕ 60 СТРОК (импорты):")
    for i, line in enumerate(main_lines[:60]):
        report.append(f"   {i+1:4}: {line.rstrip()[:80]}")
    
    report.append("")
    
    # Поиск V2 компонентов
    report.append("ПОИСК V2 КОМПОНЕНТОВ:")
    v2_checks = [
        'V2_AVAILABLE',
        'USE_NEW_UI', 
        'from core.config_v2',
        'from core.engine_v2',
        'from ui.table_headers_v2',
        'def _update_v2_progress',
        'self._update_v2_progress',
        '_tick_full_countdown',
    ]
    
    for check in v2_checks:
        found_lines = []
        for i, line in enumerate(main_lines):
            if check in line:
                found_lines.append(f"Line {i+1}: {line.strip()[:60]}")
        
        if found_lines:
            report.append(f"   [+] {check}:")
            for fl in found_lines[:5]:  # Макс 5 совпадений
                report.append(f"       {fl}")
        else:
            report.append(f"   [-] {check}: НЕ НАЙДЕН")
    
    report.append("")
    
    # Метод _tick_full_countdown полностью
    report.append("МЕТОД _tick_full_countdown (полностью):")
    in_method = False
    method_lines = []
    for i, line in enumerate(main_lines):
        if 'def _tick_full_countdown' in line:
            in_method = True
        if in_method:
            method_lines.append(f"   {i+1:4}: {line.rstrip()}")
            if line.strip().startswith('def ') and 'tick_full_countdown' not in line:
                break
    
    for ml in method_lines[:30]:
        report.append(ml)
else:
    report.append("main.py НЕ НАЙДЕН!")

report.append("")

# ============================================================================
# 3. ФАЙЛЫ V2
# ============================================================================
print("[3/7] Проверка файлов V2...")
report.append("\n[3] ФАЙЛЫ V2")
report.append("-" * 80)

v2_files = [
    ('core/config_v2.py', 'Конфигурация V2'),
    ('core/engine_v2.py', 'Движок V2'),
    ('strategies/short_after_pump_v2.py', 'Стратегии V2'),
    ('ui/table_headers_v2.py', 'UI Headers V2'),
]

for filepath, desc in v2_files:
    full_path = os.path.join(BASE_DIR, filepath)
    if os.path.exists(full_path):
        size = os.path.getsize(full_path)
        report.append(f"   [+] {filepath}: {size} bytes - {desc}")
        
        # Копируем в debug
        dest_dir = os.path.join(OUTPUT_DIR, os.path.dirname(filepath))
        os.makedirs(dest_dir, exist_ok=True)
        shutil.copy(full_path, os.path.join(OUTPUT_DIR, filepath))
        
        # Показываем первые 30 строк
        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()[:30]
        report.append(f"       Первые 30 строк:")
        for i, line in enumerate(lines):
            report.append(f"          {i+1:3}: {line.rstrip()[:70]}")
    else:
        report.append(f"   [-] {filepath}: НЕ НАЙДЕН - {desc}")

report.append("")

# ============================================================================
# 4. ТЕСТ ИМПОРТА V2
# ============================================================================
print("[4/7] Тест импорта V2 модулей...")
report.append("\n[4] ТЕСТ ИМПОРТА V2 МОДУЛЕЙ")
report.append("-" * 80)

# Добавляем путь
sys.path.insert(0, BASE_DIR)

try:
    from core.config_v2 import USE_NEW_UI
    report.append(f"   [+] core.config_v2: OK, USE_NEW_UI = {USE_NEW_UI}")
except Exception as e:
    report.append(f"   [-] core.config_v2: ОШИБКА - {e}")

try:
    from core.engine_v2 import update_scan_timers, get_scan_state
    report.append(f"   [+] core.engine_v2: OK")
except Exception as e:
    report.append(f"   [-] core.engine_v2: ОШИБКА - {e}")

try:
    from ui.table_headers_v2 import get_header_manager
    report.append(f"   [+] ui.table_headers_v2: OK")
    
    # Тест header manager
    mgr = get_header_manager()
    report.append(f"       header_manager создан: {type(mgr)}")
except Exception as e:
    report.append(f"   [-] ui.table_headers_v2: ОШИБКА - {e}")

report.append("")

# ============================================================================
# 5. ЛОГИ
# ============================================================================
print("[5/7] Сбор логов...")
report.append("\n[5] ЛОГИ")
report.append("-" * 80)

log_files = [
    'patch_v2_trace.log',
    'logs/app.log',
    'logs/errors.txt',
    'logs/start.log',
]

logs_dir = os.path.join(OUTPUT_DIR, 'logs')
os.makedirs(logs_dir, exist_ok=True)

for log_file in log_files:
    log_path = os.path.join(BASE_DIR, log_file)
    if os.path.exists(log_path):
        size = os.path.getsize(log_path)
        report.append(f"   [+] {log_file}: {size} bytes")
        
        # Копируем лог
        shutil.copy(log_path, os.path.join(logs_dir, os.path.basename(log_file)))
        
        # Показываем последние 30 строк
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        report.append(f"       Последние 30 строк:")
        for line in lines[-30:]:
            report.append(f"          {line.rstrip()[:70]}")
    else:
        report.append(f"   [-] {log_file}: не найден")

report.append("")

# ============================================================================
# 6. БЭКАПЫ main.py
# ============================================================================
print("[6/7] Поиск бэкапов...")
report.append("\n[6] БЭКАПЫ main.py")
report.append("-" * 80)

backups = []
for f in os.listdir(BASE_DIR):
    if f.startswith('main.py.') and ('backup' in f or 'bak' in f or 'pre' in f):
        full_path = os.path.join(BASE_DIR, f)
        mtime = datetime.fromtimestamp(os.path.getmtime(full_path))
        size = os.path.getsize(full_path)
        backups.append((f, mtime, size))
        
        # Копируем последний бэкап
        if len(backups) <= 2:
            shutil.copy(full_path, os.path.join(OUTPUT_DIR, f))

backups.sort(key=lambda x: x[1], reverse=True)
for name, mtime, size in backups[:5]:
    report.append(f"   {name}: {mtime.strftime('%Y-%m-%d %H:%M:%S')} - {size} bytes")

if not backups:
    report.append("   Бэкапы не найдены")

report.append("")

# ============================================================================
# 7. _Start.py
# ============================================================================
print("[7/7] Проверка _Start.py...")
report.append("\n[7] _Start.py")
report.append("-" * 80)

start_file = os.path.join(BASE_DIR, "_Start.py")
if os.path.exists(start_file):
    with open(start_file, 'r', encoding='utf-8') as f:
        start_content = f.read()
    report.append("Содержимое:")
    for i, line in enumerate(start_content.split('\n')):
        report.append(f"   {i+1:3}: {line.rstrip()}")
    shutil.copy(start_file, os.path.join(OUTPUT_DIR, "_Start.py"))
else:
    report.append("   _Start.py не найден")

# ============================================================================
# СОХРАНЯЕМ ОТЧЁТ
# ============================================================================
report.append("\n" + "=" * 80)
report.append("КОНЕЦ ОТЧЁТА")
report.append("=" * 80)

report_text = '\n'.join(report)
report_file = os.path.join(OUTPUT_DIR, "DEBUG_REPORT.txt")
with open(report_file, 'w', encoding='utf-8') as f:
    f.write(report_text)

print()
print(report_text)

# ============================================================================
# СОЗДАЁМ ZIP АРХИВ
# ============================================================================
print("\n" + "=" * 70)
print("Создание архива...")

zip_name = f"debug_v2_{TIMESTAMP}.zip"
zip_path = os.path.join(BASE_DIR, zip_name)

with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(OUTPUT_DIR):
        for file in files:
            file_path = os.path.join(root, file)
            arc_name = os.path.relpath(file_path, OUTPUT_DIR)
            zf.write(file_path, arc_name)

print(f"[OK] Архив создан: {zip_name}")
print(f"     Размер: {os.path.getsize(zip_path)} bytes")
print()
print("=" * 70)
print("ЗАГРУЗИТЕ ЭТОТ АРХИВ В ЧАТ:")
print(f"   {zip_path}")
print("=" * 70)

# Очистка
shutil.rmtree(OUTPUT_DIR)

input("\nНажмите Enter...")
