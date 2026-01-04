# ===== _patch_chart_integration.py =====
# Патч для интеграции окна графиков
# ====================================
#
# Этот скрипт добавляет:
# 1. Двойной клик на монету в сканере -> открывает график
# 2. Двойной клик на монету в Trainer -> открывает график
#
# Запуск: python _patch_chart_integration.py
#

import os
import re

BASE_DIR = r"C:\Pythone\Log_Short"

# ===============================================
# ПАТЧ ДЛЯ СКАНЕРА (auto-short_v095_with_trainer_bridge.py)
# ===============================================

SCANNER_PATCH_IMPORT = '''
# === Chart Window Integration ===
try:
    from ui.chart_window import show_chart
    HAS_CHART = True
except ImportError:
    HAS_CHART = False
    print("WARN: chart_window not found, double-click disabled")
'''

SCANNER_PATCH_METHOD = '''
    def _on_table_double_click(self, row_idx, col_idx):
        """Двойной клик на монету - открыть график."""
        if not HAS_CHART:
            return
        try:
            # Получаем символ из таблицы
            item = self.sender().item(row_idx, 1)  # колонка с символом
            if not item:
                return
            symbol = item.text() + "USDT"
            
            # Ищем данные монеты
            row = self.rows.get(symbol)
            if not row:
                return
            
            # Получаем свечи
            klines = {}
            try:
                for tf in ["15", "60", "240"]:
                    klines[tf] = self.client.get_klines(symbol, tf, limit=100)
            except:
                pass
            
            # Показываем график
            show_chart(row, self.btc_price, self.btc_change_24h, klines)
        except Exception as e:
            print(f"Chart error: {e}")
'''

SCANNER_PATCH_CONNECT_TOP = '''
        self.tbl_main.cellDoubleClicked.connect(self._on_table_double_click)
'''

SCANNER_PATCH_CONNECT_CAND = '''
        self.tbl_cand.cellDoubleClicked.connect(self._on_table_double_click)
'''


def patch_scanner():
    """Патчим сканер."""
    path = os.path.join(BASE_DIR, "auto-short_v095_with_trainer_bridge.py")
    
    if not os.path.exists(path):
        print(f"[SKIP] Сканер не найден: {path}")
        return False
    
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    
    modified = False
    
    # 1. Добавляем импорт
    if "from ui.chart_window import show_chart" not in content:
        # Ищем место после других импортов
        match = re.search(r'(import requests\n)', content)
        if match:
            content = content[:match.end()] + SCANNER_PATCH_IMPORT + content[match.end():]
            modified = True
            print("[OK] Добавлен импорт chart_window в сканер")
    
    # 2. Добавляем метод _on_table_double_click
    if "_on_table_double_click" not in content:
        # Ищем конец класса MainWindow или перед if __name__
        match = re.search(r'(\n    def keyPressEvent\(self.*?(?=\n    def |\nclass |\nif __name__))', content, re.DOTALL)
        if match:
            content = content[:match.end()] + "\n" + SCANNER_PATCH_METHOD + content[match.end():]
            modified = True
            print("[OK] Добавлен метод _on_table_double_click")
    
    # 3. Подключаем сигнал для верхней таблицы
    if "tbl_main.cellDoubleClicked" not in content:
        # Ищем создание tbl_main
        match = re.search(r'(self\.tbl_main\.setStyleSheet\([^)]+\))', content)
        if match:
            content = content[:match.end()] + SCANNER_PATCH_CONNECT_TOP + content[match.end():]
            modified = True
            print("[OK] Подключен двойной клик для верхней таблицы")
    
    # 4. Подключаем сигнал для нижней таблицы
    if "tbl_cand.cellDoubleClicked" not in content:
        match = re.search(r'(self\.tbl_cand\.setStyleSheet\([^)]+\))', content)
        if match:
            content = content[:match.end()] + SCANNER_PATCH_CONNECT_CAND + content[match.end():]
            modified = True
            print("[OK] Подключен двойной клик для таблицы кандидатов")
    
    if modified:
        # Бэкап
        backup_path = path + ".bak"
        with open(backup_path, "w", encoding="utf-8") as f:
            with open(path, "r", encoding="utf-8") as orig:
                f.write(orig.read())
        
        # Сохраняем
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[OK] Сканер пропатчен. Бэкап: {backup_path}")
        return True
    else:
        print("[SKIP] Сканер уже пропатчен")
        return False


# ===============================================
# ПАТЧ ДЛЯ TRAINER (trainer_live.py)
# ===============================================

TRAINER_PATCH_IMPORT = '''
# === Chart Window Integration ===
try:
    from ui.chart_window import show_chart
    HAS_CHART = True
except ImportError:
    HAS_CHART = False
'''

TRAINER_PATCH_METHOD = '''
    def _on_pos_double_click(self, row_idx, col_idx):
        """Двойной клик на позицию - открыть график."""
        if not HAS_CHART or row_idx >= len(self.positions):
            return
        try:
            pos = self.positions[row_idx]
            symbol = pos.get("symbol", "")
            if not symbol:
                return
            
            # Создаём минимальный row-объект для графика
            class SimpleRow:
                pass
            
            row = SimpleRow()
            row.symbol = symbol
            row.price_now = pos.get("current_price", pos.get("current", 0))
            row.status = pos.get("status", "")
            row.score = pos.get("score", 0)
            row.watch_type = pos.get("watch_type", "")
            row.change_24h_pct = 0
            row.dist_high_pct = 0
            row.rr = 0
            row.entry_price = pos.get("entry_price", 0)
            row.trend_1h_ppm = 0
            row.trend_3h_ppm = 0
            row.exhaustion = 0
            row.structure_score = 50
            row.btc_div_1h = 0
            
            # Загружаем свечи
            klines = {}
            try:
                from core.bybit_client import get_client
                client = get_client()
                for tf in ["15", "60", "240"]:
                    klines[tf] = client.get_klines(symbol, tf, limit=100)
            except:
                pass
            
            show_chart(row, 0, 0, klines)
        except Exception as e:
            print(f"Chart error: {e}")
'''


def patch_trainer():
    """Патчим trainer."""
    path = os.path.join(BASE_DIR, "trainer_live.py")
    
    if not os.path.exists(path):
        print(f"[SKIP] Trainer не найден: {path}")
        return False
    
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    
    modified = False
    
    # 1. Добавляем импорт
    if "from ui.chart_window import show_chart" not in content:
        match = re.search(r'(from PyQt5\.QtWidgets import.*?\n)', content)
        if match:
            content = content[:match.end()] + TRAINER_PATCH_IMPORT + content[match.end():]
            modified = True
            print("[OK] Добавлен импорт chart_window в trainer")
    
    # 2. Добавляем метод
    if "_on_pos_double_click" not in content:
        match = re.search(r'(\n    def _render_positions\(self\).*?(?=\n    def ))', content, re.DOTALL)
        if match:
            content = content[:match.end()] + "\n" + TRAINER_PATCH_METHOD + content[match.end():]
            modified = True
            print("[OK] Добавлен метод _on_pos_double_click")
    
    # 3. Подключаем сигнал
    if "pos_table.cellDoubleClicked" not in content:
        match = re.search(r'(self\.pos_table\.setMaximumHeight\(\d+\))', content)
        if match:
            content = content[:match.end()] + "\n        self.pos_table.cellDoubleClicked.connect(self._on_pos_double_click)" + content[match.end():]
            modified = True
            print("[OK] Подключен двойной клик для таблицы позиций")
    
    if modified:
        backup_path = path + ".bak"
        with open(backup_path, "w", encoding="utf-8") as f:
            with open(path, "r", encoding="utf-8") as orig:
                f.write(orig.read())
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[OK] Trainer пропатчен. Бэкап: {backup_path}")
        return True
    else:
        print("[SKIP] Trainer уже пропатчен")
        return False


def main():
    print("=" * 50)
    print("  ИНТЕГРАЦИЯ ОКНА ГРАФИКОВ")
    print("=" * 50)
    print()
    
    # Проверяем наличие chart_window
    chart_path = os.path.join(BASE_DIR, "ui", "chart_window.py")
    if not os.path.exists(chart_path):
        print(f"[ERROR] Не найден ui/chart_window.py!")
        print(f"        Сначала установите chart_window_v1.zip")
        return
    
    print("[OK] ui/chart_window.py найден")
    print()
    
    patch_scanner()
    print()
    patch_trainer()
    
    print()
    print("=" * 50)
    print("  ГОТОВО!")
    print("=" * 50)
    print()
    print("Теперь двойной клик на монету откроет график.")
    print("Перезапустите приложение.")


if __name__ == "__main__":
    main()
    input("\nНажмите Enter...")
