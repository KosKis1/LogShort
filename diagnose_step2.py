#!/usr/bin/env python3
"""
Диагностика Step 2 - проверка применения патча
Запуск: python diagnose_step2.py
"""

import os
import sys
import json
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_FILE = os.path.join(BASE_DIR, "auto-short_v095_with_trainer_bridge.py")
BACKUP_FILE = MAIN_FILE + ".pre_step2"
OUTPUT_FILE = os.path.join(BASE_DIR, "diagnose_step2_result.txt")

def run_diagnostics():
    results = []
    results.append(f"=" * 70)
    results.append(f"ДИАГНОСТИКА STEP 2 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    results.append(f"=" * 70)
    results.append("")
    
    # 1. Проверка файлов V2
    results.append("[1] ПРОВЕРКА ФАЙЛОВ V2:")
    v2_files = [
        ("core/config_v2.py", "Конфигурация V2"),
        ("core/engine_v2.py", "Движок V2"),
        ("strategies/short_after_pump_v2.py", "Стратегии V2"),
        ("ui/table_headers_v2.py", "UI Headers V2"),
    ]
    
    all_v2_exist = True
    for filepath, desc in v2_files:
        full_path = os.path.join(BASE_DIR, filepath)
        exists = os.path.exists(full_path)
        status = "✓ ЕСТЬ" if exists else "✗ НЕТ"
        results.append(f"   {status} - {filepath} ({desc})")
        if not exists:
            all_v2_exist = False
    
    results.append("")
    
    # 2. Проверка бэкапа
    results.append("[2] ПРОВЕРКА БЭКАПА:")
    if os.path.exists(BACKUP_FILE):
        size = os.path.getsize(BACKUP_FILE)
        mtime = datetime.fromtimestamp(os.path.getmtime(BACKUP_FILE))
        results.append(f"   ✓ Бэкап существует: {os.path.basename(BACKUP_FILE)}")
        results.append(f"   Размер: {size:,} байт")
        results.append(f"   Создан: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        results.append(f"   ✗ Бэкап НЕ найден (патч не применялся)")
    
    results.append("")
    
    # 3. Проверка патча в основном файле
    results.append("[3] ПРОВЕРКА ПАТЧА В ОСНОВНОМ ФАЙЛЕ:")
    
    if os.path.exists(MAIN_FILE):
        with open(MAIN_FILE, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        checks = [
            ("V2_AVAILABLE", "Флаг V2_AVAILABLE"),
            ("from core.config_v2 import", "Импорт config_v2"),
            ("from core.engine_v2 import", "Импорт engine_v2"),
            ("from ui.table_headers_v2 import", "Импорт table_headers_v2"),
            ("_update_v2_progress_bars", "Метод прогресс-баров"),
            ("USE_NEW_UI", "Флаг USE_NEW_UI"),
        ]
        
        patch_applied = True
        for pattern, desc in checks:
            found = pattern in content
            status = "✓ НАЙДЕН" if found else "✗ НЕ НАЙДЕН"
            results.append(f"   {status} - {desc}")
            if not found:
                patch_applied = False
        
        results.append("")
        
        # 4. Поиск строки импорта params (куда должен вставляться патч)
        results.append("[4] ТОЧКА ВСТАВКИ ИМПОРТОВ:")
        if "from core.params import P" in content:
            results.append("   ✓ Найдена строка 'from core.params import P'")
            # Найдём номер строки
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if "from core.params import P" in line:
                    results.append(f"   Строка #{i+1}: {line.strip()}")
                    # Покажем следующие 5 строк
                    results.append("   Следующие 5 строк:")
                    for j in range(i+1, min(i+6, len(lines))):
                        results.append(f"      {j+1}: {lines[j][:80]}")
                    break
        else:
            results.append("   ✗ Строка 'from core.params import P' НЕ найдена")
        
        results.append("")
        
    else:
        results.append(f"   ✗ Основной файл НЕ найден: {MAIN_FILE}")
        patch_applied = False
    
    # 5. Проверка config_v2.py
    results.append("[5] НАСТРОЙКИ CONFIG_V2:")
    config_v2_path = os.path.join(BASE_DIR, "core", "config_v2.py")
    if os.path.exists(config_v2_path):
        with open(config_v2_path, 'r', encoding='utf-8') as f:
            config_content = f.read()
        
        if "USE_NEW_UI" in config_content:
            # Попробуем найти значение
            for line in config_content.split('\n'):
                if line.strip().startswith("USE_NEW_UI"):
                    results.append(f"   {line.strip()}")
                    break
        else:
            results.append("   USE_NEW_UI не найден в config_v2.py")
    else:
        results.append("   config_v2.py не существует")
    
    results.append("")
    
    # 6. Итоговый вердикт
    results.append("=" * 70)
    results.append("ВЕРДИКТ:")
    results.append("=" * 70)
    
    if not all_v2_exist:
        results.append("❌ ПРОБЛЕМА: Файлы V2 (Шаг 1) не установлены!")
        results.append("   РЕШЕНИЕ: Сначала установите файлы из step1_migration_v2.zip")
    elif not os.path.exists(BACKUP_FILE):
        results.append("❌ ПРОБЛЕМА: Патч Step 2 не применялся (нет бэкапа)")
        results.append("   РЕШЕНИЕ: Запустите python _patch_step2.py")
    elif not patch_applied:
        results.append("❌ ПРОБЛЕМА: Патч применился некорректно")
        results.append("   РЕШЕНИЕ: Восстановите бэкап и примените патч заново:")
        results.append("   copy auto-short_v095_with_trainer_bridge.py.pre_step2 auto-short_v095_with_trainer_bridge.py")
        results.append("   python _patch_step2.py")
    else:
        results.append("✓ Патч Step 2 применён корректно")
        results.append("   Если UI не изменился - проверьте USE_NEW_UI = True в config_v2.py")
    
    results.append("")
    
    # Сохраняем результат
    output = '\n'.join(results)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(output)
    
    print(output)
    print(f"\nРезультат сохранён в: {OUTPUT_FILE}")
    print("\nНажмите Enter для выхода...")
    input()

if __name__ == "__main__":
    try:
        run_diagnostics()
    except Exception as e:
        print(f"ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        print("\nНажмите Enter для выхода...")
        input()
