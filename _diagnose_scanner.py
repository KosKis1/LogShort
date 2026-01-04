# ===== _diagnose_scanner.py =====
# Диагностика проблем сканера
# Запуск: python _diagnose_scanner.py
# ================================

import os
import sys

BASE_DIR = r"C:\Pythone\Log_Short"
SCANNER_FILE = os.path.join(BASE_DIR, "auto-short_v095_with_trainer_bridge.py")

def check_chart_module():
    """Проверка модуля графиков."""
    print("=" * 50)
    print("1. ПРОВЕРКА МОДУЛЯ ГРАФИКОВ")
    print("=" * 50)
    
    chart_path = os.path.join(BASE_DIR, "ui", "chart_window.py")
    ui_init = os.path.join(BASE_DIR, "ui", "__init__.py")
    
    print(f"   Путь: {chart_path}")
    
    if os.path.exists(chart_path):
        print("   ✅ Файл ui/chart_window.py НАЙДЕН")
        # Проверяем содержимое
        with open(chart_path, "r", encoding="utf-8") as f:
            content = f.read()
        if "def show_chart" in content:
            print("   ✅ Функция show_chart найдена")
        else:
            print("   ❌ Функция show_chart НЕ найдена!")
        
        if "class ChartWindow" in content:
            print("   ✅ Класс ChartWindow найден")
        else:
            print("   ❌ Класс ChartWindow НЕ найден!")
    else:
        print("   ❌ Файл ui/chart_window.py НЕ НАЙДЕН!")
        print("   >>> Нужно установить chart_window_v1.zip")
    
    # Проверяем __init__.py
    if os.path.exists(ui_init):
        print(f"   ✅ ui/__init__.py существует")
    else:
        print(f"   ⚠️ ui/__init__.py не существует (может быть нужен)")
    
    # Пробуем импортировать
    print("\n   Тест импорта:")
    sys.path.insert(0, BASE_DIR)
    try:
        from ui.chart_window import show_chart
        print("   ✅ Импорт успешен!")
        return True
    except ImportError as e:
        print(f"   ❌ Ошибка импорта: {e}")
        return False
    except Exception as e:
        print(f"   ❌ Другая ошибка: {e}")
        return False


def check_double_click_method():
    """Проверка метода двойного клика."""
    print("\n" + "=" * 50)
    print("2. ПРОВЕРКА МЕТОДА ДВОЙНОГО КЛИКА")
    print("=" * 50)
    
    if not os.path.exists(SCANNER_FILE):
        print(f"   ❌ Сканер не найден: {SCANNER_FILE}")
        return False
    
    with open(SCANNER_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Проверяем подключение сигнала
    if "tbl_main.cellDoubleClicked.connect" in content:
        print("   ✅ Сигнал cellDoubleClicked подключен для tbl_main")
    else:
        print("   ❌ Сигнал cellDoubleClicked НЕ подключен для tbl_main!")
    
    if "tbl_focus.cellDoubleClicked.connect" in content:
        print("   ✅ Сигнал cellDoubleClicked подключен для tbl_focus")
    else:
        print("   ❌ Сигнал cellDoubleClicked НЕ подключен для tbl_focus!")
    
    # Проверяем определение метода
    if "def _on_table_double_click" in content:
        print("   ✅ Метод _on_table_double_click определён")
        
        # Проверяем что внутри метода
        import re
        match = re.search(r'def _on_table_double_click\(self.*?\n(.*?)(?=\n    def |\nclass |\Z)', content, re.DOTALL)
        if match:
            method_body = match.group(1)
            if "show_chart" in method_body:
                print("   ✅ Вызов show_chart присутствует")
            else:
                print("   ❌ Вызов show_chart НЕ найден в методе!")
            
            if "HAS_CHART" in method_body:
                print("   ✅ Проверка HAS_CHART присутствует")
            else:
                print("   ⚠️ Проверка HAS_CHART не найдена")
    else:
        print("   ❌ Метод _on_table_double_click НЕ определён!")
    
    return True


def check_header_click():
    """Проверка сортировки по клику на заголовок."""
    print("\n" + "=" * 50)
    print("3. ПРОВЕРКА СОРТИРОВКИ ПО ЗАГОЛОВКУ")
    print("=" * 50)
    
    if not os.path.exists(SCANNER_FILE):
        print(f"   ❌ Сканер не найден")
        return False
    
    with open(SCANNER_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    
    if "sectionClicked.connect" in content:
        print("   ✅ Сигнал sectionClicked подключен")
    else:
        print("   ❌ Сигнал sectionClicked НЕ подключен!")
    
    if "def on_header_clicked" in content:
        print("   ✅ Метод on_header_clicked определён")
    else:
        print("   ❌ Метод on_header_clicked НЕ определён!")
    
    if "def sorted_by_current_sort" in content:
        print("   ✅ Метод sorted_by_current_sort определён")
    else:
        print("   ❌ Метод sorted_by_current_sort НЕ определён!")
    
    return True


def add_debug_logging():
    """Добавляет отладочное логирование в сканер."""
    print("\n" + "=" * 50)
    print("4. ДОБАВЛЕНИЕ ОТЛАДОЧНЫХ ЛОГОВ")
    print("=" * 50)
    
    if not os.path.exists(SCANNER_FILE):
        print(f"   ❌ Сканер не найден")
        return False
    
    with open(SCANNER_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Бэкап
    backup = SCANNER_FILE + ".debug_backup"
    with open(backup, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"   ✅ Бэкап создан: {backup}")
    
    modified = False
    
    # 1. Добавляем лог в _on_table_double_click
    old_method_start = 'def _on_table_double_click(self, row_idx, col_idx):\n        """Двойной клик на монету - открыть график."""'
    new_method_start = '''def _on_table_double_click(self, row_idx, col_idx):
        """Двойной клик на монету - открыть график."""
        print(f"[DEBUG] Double click: row={row_idx}, col={col_idx}")'''
    
    if old_method_start in content and "[DEBUG] Double click" not in content:
        content = content.replace(old_method_start, new_method_start)
        modified = True
        print("   ✅ Добавлен лог в _on_table_double_click")
    
    # 2. Добавляем лог в on_header_clicked
    old_header = 'def on_header_clicked(self, col: int):'
    new_header = '''def on_header_clicked(self, col: int):
        print(f"[DEBUG] Header clicked: col={col}")'''
    
    if old_header in content and "[DEBUG] Header clicked" not in content:
        content = content.replace(old_header, new_header)
        modified = True
        print("   ✅ Добавлен лог в on_header_clicked")
    
    # 3. Добавляем лог при проверке HAS_CHART
    if 'if not HAS_CHART:' in content and 'print(f"[DEBUG] HAS_CHART={HAS_CHART}")' not in content:
        content = content.replace(
            'if not HAS_CHART:\n            print("Chart window not available")',
            'print(f"[DEBUG] HAS_CHART={HAS_CHART}")\n        if not HAS_CHART:\n            print("Chart window not available")'
        )
        modified = True
        print("   ✅ Добавлен лог HAS_CHART")
    
    if modified:
        with open(SCANNER_FILE, "w", encoding="utf-8") as f:
            f.write(content)
        print("\n   📝 Логи добавлены. Перезапусти сканер и покажи вывод консоли.")
    else:
        print("\n   ⚠️ Логи уже добавлены или структура файла изменилась")
    
    return True


def main():
    print("=" * 50)
    print("  ДИАГНОСТИКА СКАНЕРА")
    print("=" * 50)
    print(f"  Папка проекта: {BASE_DIR}")
    print()
    
    os.chdir(BASE_DIR)
    
    check_chart_module()
    check_double_click_method()
    check_header_click()
    
    print("\n" + "=" * 50)
    print("  РЕКОМЕНДАЦИЯ")
    print("=" * 50)
    
    response = input("\n  Добавить отладочные логи? (y/n): ").strip().lower()
    if response == 'y':
        add_debug_logging()
    
    print("\n" + "=" * 50)
    print("  ГОТОВО!")
    print("=" * 50)


if __name__ == "__main__":
    main()
    input("\nНажмите Enter...")
