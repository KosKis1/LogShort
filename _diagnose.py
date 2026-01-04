# ===== _diagnose.py =====
# Диагностика и автоисправление
# =============================

import os
import sys
import re

BASE_DIR = r"C:\Pythone\Log_Short"
os.chdir(BASE_DIR)

print("=" * 50)
print("  ДИАГНОСТИКА SHORT PROJECT")
print("=" * 50)
print()

# 1. Удаляем lock
lock_path = os.path.join(BASE_DIR, "_instance.lock")
if os.path.exists(lock_path):
    os.remove(lock_path)
    print("[1] Lock файл УДАЛЁН")
else:
    print("[1] Lock файла нет - OK")

# 2. Проверяем trainer_live.py
trainer_path = os.path.join(BASE_DIR, "trainer_live.py")
print()
print("[2] Проверка trainer_live.py...")

if not os.path.exists(trainer_path):
    print("    ОШИБКА: trainer_live.py НЕ НАЙДЕН!")
    sys.exit(1)

with open(trainer_path, "r", encoding="utf-8") as f:
    content = f.read()

# Проверяем версию
version_match = re.search(r'# Trainer Live (v\d+)', content)
if version_match:
    print(f"    Версия: {version_match.group(1)}")
else:
    print("    Версия: не определена")

# Проверяем ENTRY_STATUSES
if 'ENTRY_STATUSES' in content:
    match = re.search(r'ENTRY_STATUSES\s*=\s*(\([^)]+\)|\[[^\]]+\])', content)
    if match:
        print(f"    ENTRY_STATUSES = {match.group(1)}")
else:
    print("    ENTRY_STATUSES: НЕ НАЙДЕН")

# Проверяем строгий фильтр
has_strict = "NO_ENTRY" in content or "no candidates with status" in content
print(f"    Строгий фильтр: {'✅ ЕСТЬ' if has_strict else '❌ НЕТ (старая версия!)'}")

# Проверяем fallback
has_fallback = re.search(r'if not candidates:\s*\n\s*candidates\s*=', content)
print(f"    Fallback на все монеты: {'❌ ЕСТЬ (плохо!)' if has_fallback else '✅ НЕТ'}")

# 3. Проверяем импорты
print()
print("[3] Проверка импортов...")

try:
    from PyQt5.QtWidgets import QApplication
    print("    PyQt5: OK")
except ImportError as e:
    print(f"    PyQt5: ОШИБКА - {e}")

try:
    from PySide6.QtWidgets import QApplication
    print("    PySide6: OK")
except ImportError as e:
    print(f"    PySide6: ОШИБКА - {e}")

# 4. Проверяем core модули
print()
print("[4] Проверка core модулей...")

core_modules = ["types", "config", "bridge", "bybit_client", "ml_logger"]
for mod in core_modules:
    try:
        __import__(f"core.{mod}")
        print(f"    core.{mod}: OK")
    except ImportError as e:
        print(f"    core.{mod}: ОШИБКА - {e}")

# 5. Проверяем _Start.py
print()
print("[5] Проверка _Start.py...")

start_path = os.path.join(BASE_DIR, "_Start.py")
if os.path.exists(start_path):
    with open(start_path, "r", encoding="utf-8") as f:
        start_content = f.read()
    
    if "trainer_live.py" in start_content:
        print("    Запуск trainer: OK")
    else:
        print("    Запуск trainer: НЕ НАЙДЕН")
    
    if "auto-short" in start_content or "main.py" in start_content:
        print("    Запуск сканера: OK")
    else:
        print("    Запуск сканера: НЕ НАЙДЕН")
else:
    print("    _Start.py НЕ НАЙДЕН!")

# 6. Автоисправление trainer_live.py если нужно
print()
print("[6] Автоисправление...")

if has_fallback:
    print("    Исправляю fallback в trainer_live.py...")
    
    # Паттерн старого кода
    old_pattern = r'if not candidates:\s*\n\s*candidates\s*=\s*sorted\([^)]+\)'
    
    # Новый код
    new_code = '''if not candidates:
            trace(f"NO_ENTRY: no candidates with status in {ENTRY_STATUSES}")
            return'''
    
    new_content = re.sub(old_pattern, new_code, content)
    
    if new_content != content:
        with open(trainer_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print("    ✅ ИСПРАВЛЕНО!")
    else:
        print("    Не удалось найти паттерн для исправления")
else:
    print("    Исправление не требуется")

print()
print("=" * 50)
print("  ДИАГНОСТИКА ЗАВЕРШЕНА")
print("=" * 50)
input("\nНажмите Enter...")
