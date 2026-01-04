# ===== _patch_scanner_v2.py =====
# Патч для добавления двойного клика и таймеров
# Запуск: python _patch_scanner_v2.py
# ================================

import os
import re

BASE_DIR = r"C:\Pythone\Log_Short"
SCANNER_FILE = os.path.join(BASE_DIR, "auto-short_v095_with_trainer_bridge.py")

# Метод для двойного клика на таблицы
DOUBLE_CLICK_METHOD = '''
    def _on_table_double_click(self, row_idx, col_idx):
        """Двойной клик на монету - открыть график."""
        if not HAS_CHART:
            print("Chart window not available")
            return
        try:
            table = self.sender()
            # Определяем колонку с символом
            if table == self.tbl_main:
                item = table.item(row_idx, 1)  # Колонка "Монета"
            else:
                item = table.item(row_idx, 0)  # Первая колонка в tbl_focus
            
            if not item:
                return
            
            symbol = item.text()
            if not symbol:
                return
            if not symbol.endswith("USDT"):
                symbol += "USDT"
            
            row = self.rows_by_symbol.get(symbol)
            if not row:
                print(f"Row not found for {symbol}")
                return
            
            # Загружаем свечи для графика
            klines = {}
            try:
                for tf in ["15", "60", "240"]:
                    klines[tf] = self.client.get_kline(symbol, int(tf) if tf.isdigit() else 60, 100)
            except Exception as e:
                print(f"Klines error: {e}")
            
            # BTC данные
            btc_row = self.rows_by_symbol.get("BTCUSDT")
            btc_price = btc_row.price_now if btc_row else 0
            btc_change = btc_row.change_24h_pct if btc_row else 0
            
            show_chart(row, btc_price, btc_change, klines)
            
        except Exception as e:
            print(f"Double click error: {e}")
            import traceback
            traceback.print_exc()
'''

def patch_scanner():
    if not os.path.exists(SCANNER_FILE):
        print(f"[ERROR] Файл не найден: {SCANNER_FILE}")
        return False
    
    with open(SCANNER_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Бэкап
    backup = SCANNER_FILE + ".backup2"
    with open(backup, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[OK] Бэкап: {backup}")
    
    modified = False
    
    # 1. Проверяем есть ли метод _on_table_double_click
    if "def _on_table_double_click" not in content:
        # Ищем место для вставки - перед def on_main_selection или после _build_ui
        match = re.search(r'(\n    def on_main_selection\(self\))', content)
        if match:
            content = content[:match.start()] + DOUBLE_CLICK_METHOD + content[match.start():]
            modified = True
            print("[OK] Добавлен метод _on_table_double_click")
        else:
            print("[WARN] Не найдено место для вставки метода")
    else:
        print("[SKIP] Метод _on_table_double_click уже существует")
    
    # 2. Подключаем двойной клик для tbl_focus если нет
    if "tbl_focus.cellDoubleClicked" not in content:
        # Ищем где создаётся tbl_focus
        match = re.search(r'(self\.tbl_focus\.setHorizontalHeaderLabels\(focus_headers\))', content)
        if match:
            insert = "\n        self.tbl_focus.cellDoubleClicked.connect(self._on_table_double_click)"
            content = content[:match.end()] + insert + content[match.end():]
            modified = True
            print("[OK] Подключен двойной клик для tbl_focus")
    else:
        print("[SKIP] Двойной клик для tbl_focus уже подключен")
    
    if modified:
        with open(SCANNER_FILE, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[OK] Сканер обновлён")
        return True
    else:
        print("[INFO] Изменений не требуется")
        return False


def main():
    print("=" * 50)
    print("  ПАТЧ СКАНЕРА v2 - Двойной клик + Графики")
    print("=" * 50)
    print()
    
    # Проверяем chart_window
    chart_path = os.path.join(BASE_DIR, "ui", "chart_window.py")
    if not os.path.exists(chart_path):
        print(f"[WARN] Не найден ui/chart_window.py")
        print(f"       Сначала установите chart_window_v1.zip")
        print()
    else:
        print(f"[OK] ui/chart_window.py найден")
    
    patch_scanner()
    
    print()
    print("=" * 50)
    print("  ГОТОВО! Перезапустите приложение.")
    print("=" * 50)


if __name__ == "__main__":
    main()
    input("\nНажмите Enter...")
