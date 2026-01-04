#!/usr/bin/env python3
"""
Диагностика V2_AVAILABLE - показывает все строки
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_FILE = os.path.join(BASE_DIR, "auto-short_v095_with_trainer_bridge.py")

print("=" * 70)
print("ДИАГНОСТИКА V2_AVAILABLE")
print("=" * 70)
print()

with open(MAIN_FILE, 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

print("[1] ВСЕ СТРОКИ С V2_AVAILABLE:")
print("-" * 70)
for i, line in enumerate(lines):
    if "V2_AVAILABLE" in line:
        print(f"   Строка {i+1}: {line.rstrip()}")

print()
print("[2] ВСЕ СТРОКИ С USE_NEW_UI:")
print("-" * 70)
for i, line in enumerate(lines):
    if "USE_NEW_UI" in line and "import" not in line.lower():
        print(f"   Строка {i+1}: {line.rstrip()[:80]}")

print()
print("[3] БЛОК ИМПОРТА V2 (строки 310-340):")
print("-" * 70)
for i in range(309, min(345, len(lines))):
    print(f"   {i+1}: {lines[i].rstrip()[:85]}")

print()
print("[4] МЕТОД _update_v2_progress_bars:")
print("-" * 70)
found = False
for i, line in enumerate(lines):
    if "def _update_v2_progress_bars" in line:
        found = True
        print(f"   НАЙДЕН на строке {i+1}")
        # Показать первые 20 строк метода
        for j in range(i, min(i+20, len(lines))):
            print(f"   {j+1}: {lines[j].rstrip()[:85]}")
        break

if not found:
    print("   НЕ НАЙДЕН!")

print()
print("=" * 70)
input("Нажмите Enter...")
