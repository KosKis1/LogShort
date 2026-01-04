#!/usr/bin/env python3
"""
Анализ main.py - поиск точек интеграции V2
С трассировкой для отладки
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_FILE = os.path.join(BASE_DIR, "main.py")
OUTPUT_FILE = os.path.join(BASE_DIR, "main_py_analysis.txt")

print("=" * 70)
print("АНАЛИЗ main.py ДЛЯ ИНТЕГРАЦИИ V2")
print("=" * 70)
print()

results = []
results.append("=" * 80)
results.append("АНАЛИЗ main.py")
results.append("=" * 80)
results.append("")

with open(MAIN_FILE, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()
    lines = content.split('\n')

print(f"[TRACE] Файл загружен: {len(lines)} строк")

# 1. Поиск импортов
results.append("[1] ТЕКУЩИЕ ИМПОРТЫ (первые 50 строк):")
results.append("-" * 80)
for i in range(min(50, len(lines))):
    line = lines[i]
    if 'import' in line or 'from' in line:
        results.append(f"   {i+1}: {line.rstrip()}")
results.append("")

# 2. Поиск class MainWindow
results.append("[2] CLASS MAINWINDOW:")
results.append("-" * 80)
for i, line in enumerate(lines):
    if 'class MainWindow' in line:
        results.append(f"   Строка {i+1}: {line.rstrip()}")
        # Показать 10 строк после
        for j in range(i+1, min(i+11, len(lines))):
            results.append(f"   {j+1}: {lines[j].rstrip()[:80]}")
        break
results.append("")

# 3. Поиск таймеров/tick
results.append("[3] ТАЙМЕРЫ И TICK МЕТОДЫ:")
results.append("-" * 80)
for i, line in enumerate(lines):
    if 'timer' in line.lower() or 'tick' in line.lower():
        results.append(f"   {i+1}: {line.rstrip()[:80]}")
results.append("")

# 4. Поиск lbl_ меток
results.append("[4] МЕТКИ (lbl_):")
results.append("-" * 80)
for i, line in enumerate(lines):
    if 'lbl_' in line and ('=' in line or 'setText' in line):
        results.append(f"   {i+1}: {line.rstrip()[:80]}")
results.append("")

# 5. Поиск заголовков таблиц
results.append("[5] ЗАГОЛОВКИ ТАБЛИЦ (headers):")
results.append("-" * 80)
for i, line in enumerate(lines):
    if 'header' in line.lower() and ('=' in line or '[' in line):
        results.append(f"   {i+1}: {line.rstrip()[:80]}")
results.append("")

# 6. Поиск V2 упоминаний
results.append("[6] УПОМИНАНИЯ V2:")
results.append("-" * 80)
v2_found = False
for i, line in enumerate(lines):
    if 'v2' in line.lower() or 'V2' in line:
        v2_found = True
        results.append(f"   {i+1}: {line.rstrip()[:80]}")
if not v2_found:
    results.append("   НЕ НАЙДЕНО - V2 ещё не интегрирован в main.py!")
results.append("")

# 7. Поиск "До пересчёта" или подобного
results.append("[7] ТЕКСТ СТАТУСА (пересчёт/обновление):")
results.append("-" * 80)
for i, line in enumerate(lines):
    if 'пересч' in line.lower() or 'обновлен' in line.lower() or 'counter' in line.lower():
        results.append(f"   {i+1}: {line.rstrip()[:80]}")
results.append("")

# 8. Структура методов MainWindow
results.append("[8] МЕТОДЫ КЛАССА MAINWINDOW (def внутри класса):")
results.append("-" * 80)
in_class = False
for i, line in enumerate(lines):
    if 'class MainWindow' in line:
        in_class = True
        continue
    if in_class and line.startswith('class '):
        break
    if in_class and '    def ' in line:
        results.append(f"   {i+1}: {line.strip()[:70]}")
results.append("")

# Сохраняем
output = '\n'.join(results)
with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    f.write(output)

print(output)
print()
print(f"[TRACE] Сохранено: {OUTPUT_FILE}")
print()
print("=" * 70)
input("Нажмите Enter...")
