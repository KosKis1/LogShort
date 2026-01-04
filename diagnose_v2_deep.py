#!/usr/bin/env python3
"""
Глубокая диагностика V2 UI - проверка интеграции
Запуск: python diagnose_v2_deep.py
"""

import os
import re
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_FILE = os.path.join(BASE_DIR, "auto-short_v095_with_trainer_bridge.py")
OUTPUT_FILE = os.path.join(BASE_DIR, "diagnose_v2_deep_result.txt")

def run_deep_diagnostics():
    results = []
    results.append("=" * 80)
    results.append(f"ГЛУБОКАЯ ДИАГНОСТИКА V2 UI - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    results.append("=" * 80)
    results.append("")
    
    with open(MAIN_FILE, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        lines = content.split('\n')
    
    # 1. Проверка импорта V2_AVAILABLE
    results.append("[1] ПРОВЕРКА V2_AVAILABLE:")
    v2_available_set = False
    for i, line in enumerate(lines):
        if "V2_AVAILABLE = True" in line:
            results.append(f"   ✓ Строка {i+1}: {line.strip()}")
            v2_available_set = True
        elif "V2_AVAILABLE = False" in line:
            results.append(f"   ✗ Строка {i+1}: {line.strip()} <- ПРОБЛЕМА!")
            v2_available_set = False
    
    if not v2_available_set:
        # Ищем где устанавливается
        for i, line in enumerate(lines):
            if "V2_AVAILABLE" in line and "=" in line:
                results.append(f"   Строка {i+1}: {line.strip()}")
    results.append("")
    
    # 2. Проверка метода _update_v2_progress_bars
    results.append("[2] МЕТОД _update_v2_progress_bars:")
    method_found = False
    method_start = -1
    for i, line in enumerate(lines):
        if "def _update_v2_progress_bars" in line:
            method_found = True
            method_start = i
            results.append(f"   ✓ Найден на строке {i+1}")
            # Показать первые 10 строк метода
            results.append("   Содержимое метода:")
            for j in range(i, min(i+15, len(lines))):
                results.append(f"      {j+1}: {lines[j][:90]}")
            break
    
    if not method_found:
        results.append("   ✗ Метод НЕ найден!")
    results.append("")
    
    # 3. Проверка вызова _update_v2_progress_bars
    results.append("[3] ВЫЗОВ _update_v2_progress_bars:")
    call_found = False
    for i, line in enumerate(lines):
        if "_update_v2_progress_bars()" in line and "def " not in line:
            call_found = True
            results.append(f"   ✓ Вызов на строке {i+1}: {line.strip()}")
            # Контекст - 3 строки до и после
            results.append("   Контекст:")
            for j in range(max(0, i-3), min(i+4, len(lines))):
                marker = ">>>" if j == i else "   "
                results.append(f"      {marker} {j+1}: {lines[j][:90]}")
    
    if not call_found:
        results.append("   ✗ Вызов метода НЕ найден!")
    results.append("")
    
    # 4. Проверка tick_status_line (где должен быть вызов)
    results.append("[4] МЕТОД tick_status_line (где вызывается обновление):")
    for i, line in enumerate(lines):
        if "def tick_status_line" in line or "def _tick_status_line" in line:
            results.append(f"   Найден на строке {i+1}")
            # Показать весь метод до следующего def
            results.append("   Содержимое:")
            for j in range(i, min(i+30, len(lines))):
                results.append(f"      {j+1}: {lines[j][:90]}")
                if j > i and lines[j].strip().startswith("def "):
                    break
            break
    results.append("")
    
    # 5. Проверка заголовков таблиц
    results.append("[5] ЗАГОЛОВКИ ТАБЛИЦ (TABLE1_HEADERS / TABLE2_HEADERS):")
    for i, line in enumerate(lines):
        if "TABLE1_HEADERS" in line or "TABLE2_HEADERS" in line:
            results.append(f"   Строка {i+1}: {line.strip()[:80]}")
    results.append("")
    
    # 6. Проверка lbl_top200_counter
    results.append("[6] МЕТКИ lbl_top200_counter / lbl_candidates_counter:")
    for i, line in enumerate(lines):
        if "lbl_top200_counter" in line or "lbl_candidates_counter" in line:
            if "setText" in line or "setWordWrap" in line or "setMinimumHeight" in line:
                results.append(f"   Строка {i+1}: {line.strip()[:80]}")
    results.append("")
    
    # 7. Проверка get_header_manager
    results.append("[7] ИСПОЛЬЗОВАНИЕ get_header_manager:")
    for i, line in enumerate(lines):
        if "get_header_manager" in line:
            results.append(f"   Строка {i+1}: {line.strip()[:80]}")
    results.append("")
    
    # 8. Итоговая проверка
    results.append("=" * 80)
    results.append("АНАЛИЗ:")
    results.append("=" * 80)
    
    issues = []
    
    if not method_found:
        issues.append("- Метод _update_v2_progress_bars не создан")
    
    if not call_found:
        issues.append("- Метод _update_v2_progress_bars не вызывается")
    
    if "header_manager" not in content:
        issues.append("- header_manager не используется")
    
    if issues:
        results.append("НАЙДЕНЫ ПРОБЛЕМЫ:")
        for issue in issues:
            results.append(f"   {issue}")
    else:
        results.append("Код интегрирован. Проверьте:")
        results.append("   1. Нет ли исключений при импорте V2 модулей")
        results.append("   2. Работает ли tick_status_line вообще")
    
    results.append("")
    
    # Сохраняем
    output = '\n'.join(results)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(output)
    
    print(output)
    print(f"\nСохранено: {OUTPUT_FILE}")
    print("\nНажмите Enter...")
    input()

if __name__ == "__main__":
    try:
        run_deep_diagnostics()
    except Exception as e:
        print(f"ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        input()
