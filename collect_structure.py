#!/usr/bin/env python3
"""
Сборщик структуры проекта для анализа
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(BASE_DIR, "project_structure.txt")

results = []
results.append("=" * 80)
results.append("СТРУКТУРА ПРОЕКТА")
results.append("=" * 80)
results.append("")

# 1. Список файлов в корне
results.append("[1] КОРНЕВАЯ ПАПКА (*.py файлы):")
results.append("-" * 80)
for f in sorted(os.listdir(BASE_DIR)):
    if f.endswith('.py'):
        path = os.path.join(BASE_DIR, f)
        size = os.path.getsize(path)
        results.append(f"   {f:<50} {size:>10} байт")
results.append("")

# 2. Папка ui/
results.append("[2] ПАПКА ui/:")
results.append("-" * 80)
ui_dir = os.path.join(BASE_DIR, "ui")
if os.path.exists(ui_dir):
    for f in sorted(os.listdir(ui_dir)):
        if f.endswith('.py'):
            path = os.path.join(ui_dir, f)
            size = os.path.getsize(path)
            results.append(f"   {f:<50} {size:>10} байт")
results.append("")

# 3. Папка core/
results.append("[3] ПАПКА core/:")
results.append("-" * 80)
core_dir = os.path.join(BASE_DIR, "core")
if os.path.exists(core_dir):
    for f in sorted(os.listdir(core_dir)):
        if f.endswith('.py'):
            path = os.path.join(core_dir, f)
            size = os.path.getsize(path)
            results.append(f"   {f:<50} {size:>10} байт")
results.append("")

# 4. Ищем где определён MainWindow
results.append("[4] ПОИСК CLASS MAINWINDOW:")
results.append("-" * 80)
for root, dirs, files in os.walk(BASE_DIR):
    # Пропускаем __pycache__
    dirs[:] = [d for d in dirs if d != '__pycache__']
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as file:
                    content = file.read()
                    if 'class MainWindow' in content:
                        rel_path = os.path.relpath(path, BASE_DIR)
                        results.append(f"   НАЙДЕН в: {rel_path}")
                        # Найдём строку
                        for i, line in enumerate(content.split('\n')):
                            if 'class MainWindow' in line:
                                results.append(f"   Строка {i+1}: {line.strip()}")
                                break
            except:
                pass
results.append("")

# 5. Ищем где вызывается _tick_status_lines
results.append("[5] ПОИСК _tick_status_lines:")
results.append("-" * 80)
for root, dirs, files in os.walk(BASE_DIR):
    dirs[:] = [d for d in dirs if d != '__pycache__']
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as file:
                    content = file.read()
                    if '_tick_status_lines' in content:
                        rel_path = os.path.relpath(path, BASE_DIR)
                        results.append(f"   Файл: {rel_path}")
                        for i, line in enumerate(content.split('\n')):
                            if '_tick_status_lines' in line:
                                results.append(f"      Строка {i+1}: {line.strip()[:70]}")
            except:
                pass
results.append("")

# 6. Ищем lbl_top200_counter
results.append("[6] ПОИСК lbl_top200_counter:")
results.append("-" * 80)
for root, dirs, files in os.walk(BASE_DIR):
    dirs[:] = [d for d in dirs if d != '__pycache__']
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as file:
                    content = file.read()
                    if 'lbl_top200_counter' in content:
                        rel_path = os.path.relpath(path, BASE_DIR)
                        count = content.count('lbl_top200_counter')
                        results.append(f"   Файл: {rel_path} ({count} упоминаний)")
            except:
                pass
results.append("")

# 7. Содержимое _Start.py
results.append("[7] СОДЕРЖИМОЕ _Start.py:")
results.append("-" * 80)
start_file = os.path.join(BASE_DIR, "_Start.py")
if os.path.exists(start_file):
    with open(start_file, 'r', encoding='utf-8', errors='ignore') as f:
        for i, line in enumerate(f.readlines()[:50]):
            results.append(f"   {i+1}: {line.rstrip()}")
else:
    results.append("   Файл не найден")
results.append("")

# Сохраняем
output = '\n'.join(results)
with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    f.write(output)

print(output)
print(f"\nСохранено: {OUTPUT_FILE}")
print("\nНажмите Enter...")
input()
