#!/usr/bin/env python3
"""
Проверка интеграции V2 в main.py
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_FILE = os.path.join(BASE_DIR, "main.py")

print("=" * 70)
print("ПРОВЕРКА V2 В main.py")
print("=" * 70)
print()

with open(MAIN_FILE, 'r', encoding='utf-8') as f:
    content = f.read()

checks = [
    ("V2_AVAILABLE", "Переменная V2_AVAILABLE"),
    ("USE_NEW_UI", "Переменная USE_NEW_UI"),
    ("from core.config_v2", "Импорт config_v2"),
    ("from core.engine_v2", "Импорт engine_v2"),
    ("from ui.table_headers_v2", "Импорт table_headers_v2"),
    ("def _update_v2_progress", "Метод _update_v2_progress"),
    ("self._update_v2_progress()", "Вызов _update_v2_progress"),
]

print("[ПРОВЕРКА КОДА main.py]")
print("-" * 70)
all_ok = True
for pattern, desc in checks:
    found = pattern in content
    status = "OK" if found else "НЕТ"
    mark = "[+]" if found else "[-]"
    print(f"   {mark} {desc}: {status}")
    if not found:
        all_ok = False

print()
print("-" * 70)

if all_ok:
    print("[РЕЗУЛЬТАТ] Все компоненты V2 найдены в main.py")
    print()
    print("Проблема может быть в:")
    print("  1. USE_NEW_UI = False в config_v2.py")
    print("  2. Ошибка импорта модулей V2")
    print("  3. Метод _update_v2_progress не вызывается")
else:
    print("[РЕЗУЛЬТАТ] Некоторые компоненты V2 отсутствуют!")

# Показать контекст вызова
print()
print("[КОНТЕКСТ ВЫЗОВА _update_v2_progress]")
print("-" * 70)
lines = content.split('\n')
for i, line in enumerate(lines):
    if '_update_v2_progress' in line:
        print(f"   Строка {i+1}: {line.strip()[:70]}")

# Проверим config_v2.py
print()
print("[ПРОВЕРКА config_v2.py]")
print("-" * 70)
config_v2_path = os.path.join(BASE_DIR, "core", "config_v2.py")
if os.path.exists(config_v2_path):
    with open(config_v2_path, 'r', encoding='utf-8') as f:
        config_content = f.read()
    for line in config_content.split('\n'):
        if 'USE_NEW_UI' in line and '=' in line and '#' not in line.split('=')[0]:
            print(f"   {line.strip()}")
else:
    print("   config_v2.py не найден!")

print()
print("=" * 70)
input("Нажмите Enter...")
