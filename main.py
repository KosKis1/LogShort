# ===== main.py =====
# Bybit SHORT Scanner — Main Entry Point
# С интеграцией V2 (прогресс-бары, новые метрики)
# =======================================

import os
import sys
import time
import json
import subprocess
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QTimer, QEvent, QObject
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QSplitter, QMessageBox
)

# Импорты модулей
from core.config import get_config, AppConfig
from core.types import CoinRow
from core.bybit_client import BybitClient, get_client
from core.bridge import write_bridge_snapshot
from core.ml_logger import get_ml_logger
from strategies import get_strategy
from workers import ScannerWorker, CandidatesUpdateWorker, PriceUpdateWorker, PumpDetectorWorker
from ui.styles import (
    MAIN_STYLE, TABLE_TOP200_STYLE, TABLE_CANDIDATES_STYLE,
    BTN_EXIT_STYLE, SCANNER_SIZE, ROW_HEIGHT
)
from ui.dialogs import CountdownDialog

# Chart window (опционально)
try:
    from ui.chart_window import show_chart
    HAS_CHART = True
    print("[TRACE] chart_window imported successfully")
except ImportError as e:
    HAS_CHART = False
    print(f"[TRACE] chart_window not available: {e}")

# === V2 IMPORTS ===
try:
    from core.config_v2 import USE_NEW_UI
    from core.engine_v2 import update_scan_timers, get_scan_state
    from ui.table_headers_v2 import get_header_manager
    V2_AVAILABLE = True
    print("[TRACE-V2] V2 модули загружены: USE_NEW_UI =", USE_NEW_UI)
except ImportError as e:
    V2_AVAILABLE = False
    USE_NEW_UI = False
    print(f"[TRACE-V2] V2 модули недоступны: {e}")
# === END V2 IMPORTS ===

# Константы
CONFIG = get_config()
PAGE_SIZE = CONFIG.page_size
AUTO_RECALC_MIN = CONFIG.auto_recalc_minutes


class EscFilter(QObject):
    """Фильтр ESC для отмены авто-сканирования."""
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
    
    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
            self.callback()
            return True
        return False


class MainWindow(QMainWindow):
    """Главное окно сканера."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bybit SHORT Scanner — Modular v3.0")
        self.resize(*SCANNER_SIZE)
        self.setMinimumSize(1400, 800)
        
        # Компоненты
        self.client = get_client()
        self.strategy = get_strategy()
        self.ml_logger = get_ml_logger()
        
        # Состояние
        self.rows: Dict[str, CoinRow] = {}
        self.worker: Optional[ScannerWorker] = None
        self.cand_worker: Optional[CandidatesUpdateWorker] = None
        self.current_page = 0
        self.scan_in_progress = False
        self.cand_update_in_progress = False
        
        # === ТРЁХУРОВНЕВАЯ СИСТЕМА V2 ===
        self.price_worker: Optional[PriceUpdateWorker] = None
        self.pump_worker: Optional[PumpDetectorWorker] = None
        self.price_update_in_progress = False
        self.pump_detect_in_progress = False
        
        # Сортировка
        self.sort_col = 6  # По умолчанию по обороту
        self.sort_desc = True
        
        # UI
        self._build_ui()
        self._apply_styles()
        
        # Таймеры
        self.auto_timer = QTimer(self)
        self.auto_timer.setInterval(AUTO_RECALC_MIN * 60 * 1000)
        self.auto_timer.timeout.connect(self._start_countdown)
        self.auto_timer.start()
        
        self.countdown_timer: Optional[QTimer] = None
        self.countdown_dialog: Optional[CountdownDialog] = None
        self.countdown_sec = 0
        
        # ESC фильтр
        self.esc_filter = EscFilter(self._cancel_countdown)
        QApplication.instance().installEventFilter(self.esc_filter)

        # Live window (создаётся по кнопке)
        self.live_window = None

        # === ТРЁХУРОВНЕВЫЕ ТАЙМЕРЫ V2 ===
        # Уровень 1: Полный пересчёт (120 сек)
        self._full_countdown = 120
        # Уровень 2: Обновление цен (30 сек)
        self._price_countdown = 30
        # Уровень 3: Детектор пампов (10 сек)
        self._pump_countdown = 10
        # Кандидаты (5 сек)
        self._cand_countdown = 5
        self._cand_update_delay = 5

        # Единый таймер тикает каждую секунду
        self.main_tick_timer = QTimer(self)
        self.main_tick_timer.setInterval(1000)
        self.main_tick_timer.timeout.connect(self._tick_all_levels)
        self.main_tick_timer.start()

        # Загрузка состояния
        self._load_state()
        
        print("[TRACE] MainWindow инициализирован, V2_AVAILABLE =", V2_AVAILABLE)
        print("[TRACE-V2] Трёхуровневая система: L1=120с, L2=30с, L3=10с")
    
    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        main = QVBoxLayout(root)
        main.setContentsMargins(10, 10, 10, 10)
        main.setSpacing(8)
        
        # === Top bar ===
        topbar = QHBoxLayout()
        
        self.lbl_status = QLabel("Готово")
        self.lbl_status.setMinimumWidth(200)
        topbar.addWidget(self.lbl_status)
        
        self.lbl_progress = QLabel("UNIVERSE: 0/200")
        topbar.addWidget(self.lbl_progress)
        
        topbar.addStretch()
        
        self.btn_prev = QPushButton("◀ Пред")
        self.btn_next = QPushButton("След ▶")
        self.btn_refresh = QPushButton("🔄 Обновить")
        
        self.btn_prev.clicked.connect(self._prev_page)
        self.btn_next.clicked.connect(self._next_page)
        self.btn_refresh.clicked.connect(self._start_scan)
        
        topbar.addWidget(self.btn_prev)
        topbar.addWidget(self.btn_next)
        topbar.addWidget(self.btn_refresh)
        
        self.btn_live = QPushButton("📈 Live")
        self.btn_live.clicked.connect(self._toggle_live)
        topbar.addWidget(self.btn_live)
        
        self.btn_exit = QPushButton("⏻ Выход")
        self.btn_exit.setStyleSheet(BTN_EXIT_STYLE)
        self.btn_exit.clicked.connect(self._exit_app)
        topbar.addWidget(self.btn_exit)
        
        main.addLayout(topbar)
        
        # === Splitter ===
        splitter = QSplitter(Qt.Vertical)
        
        # TOP200 таблица
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        
        self.lbl_top200 = QLabel("📊 TOP 200 по обороту")
        self.lbl_top200.setStyleSheet("color: #00d4ff; font-size: 14px; font-weight: bold;")
        top_layout.addWidget(self.lbl_top200)
        
        # Метка таймера/прогресс-бара V2
        self.lbl_full_timer = QLabel("До пересчёта: 120 сек")
        self.lbl_full_timer.setStyleSheet("color:#cfcfcf; font-size:12px;")
        if V2_AVAILABLE and USE_NEW_UI:
            self.lbl_full_timer.setWordWrap(True)
            self.lbl_full_timer.setMinimumHeight(50)
        top_layout.addWidget(self.lbl_full_timer)
        
        self.tbl_main = QTableWidget()
        self.tbl_main.setColumnCount(10)
        self.tbl_main.setHorizontalHeaderLabels([
            "Ранг", "Монета", "Позиция%", "До хая%", "24ч%",
            "Цена", "Оборот(М)", "Фандинг", "Статус", "Скор"
        ])
        self.tbl_main.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_main.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_main.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl_main.verticalHeader().setDefaultSectionSize(ROW_HEIGHT)
        self.tbl_main.setStyleSheet(TABLE_TOP200_STYLE)
        
        self.tbl_main.cellDoubleClicked.connect(self._on_double_click)
        self.tbl_main.horizontalHeader().sectionClicked.connect(self._on_header_click)
        
        top_layout.addWidget(self.tbl_main)
        splitter.addWidget(top_widget)
        
        # Кандидаты таблица
        cand_widget = QWidget()
        cand_layout = QVBoxLayout(cand_widget)
        cand_layout.setContentsMargins(0, 0, 0, 0)
        
        self.lbl_candidates = QLabel("🎯 Кандидаты на SHORT")
        self.lbl_candidates.setStyleSheet("color: #ffd700; font-size: 14px; font-weight: bold;")
        cand_layout.addWidget(self.lbl_candidates)
        
        # Метка таймера/прогресс-бара V2 для кандидатов
        self.lbl_cand_timer = QLabel("До обновления: 10 сек")
        self.lbl_cand_timer.setStyleSheet("color:#cfcfcf; font-size:12px;")
        if V2_AVAILABLE and USE_NEW_UI:
            self.lbl_cand_timer.setWordWrap(True)
            self.lbl_cand_timer.setMinimumHeight(50)
        cand_layout.addWidget(self.lbl_cand_timer)
        
        self.tbl_cand = QTableWidget()
        self.tbl_cand.setColumnCount(15)
        self.tbl_cand.setHorizontalHeaderLabels([
            "Монета", "Время", "Статус", "Скор", "Тип", "Позиция%", "До хая%",
            "24ч%", "Вход", "SL", "TP1", "R/R", "G0", "G1", "G2"
        ])
        self.tbl_cand.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_cand.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_cand.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl_cand.verticalHeader().setDefaultSectionSize(ROW_HEIGHT - 2)
        self.tbl_cand.setStyleSheet(TABLE_CANDIDATES_STYLE)
        
        self.tbl_cand.cellDoubleClicked.connect(self._on_double_click_cand)
        
        cand_layout.addWidget(self.tbl_cand)
        splitter.addWidget(cand_widget)
        splitter.setSizes([400, 300])
        
        main.addWidget(splitter)
    
    def _apply_styles(self):
        self.setStyleSheet(MAIN_STYLE)
        f = QFont()
        f.setPointSize(11)
        self.tbl_main.setFont(f)
        self.tbl_cand.setFont(f)
    
    # === V2 ПРОГРЕСС-БАРЫ ===
    
    def _update_v2_ui(self):
        """Обновление V2 прогресс-баров в заголовках."""
        if not V2_AVAILABLE or not USE_NEW_UI:
            return
        
        try:
            # Получаем header manager
            header_mgr = get_header_manager()
            
            # Устанавливаем правильные total_sec для прогресс-баров
            header_mgr.level1_bar.total_sec = 120  # Полный пересчёт
            header_mgr.level2_bar.total_sec = 30   # Обновление цен
            header_mgr.level3_bar.total_sec = 10   # Детектор пампов
            header_mgr.candidates_bar.total_sec = 5  # Кандидаты
            
            # РЕАЛЬНЫЕ таймеры уровней (не симуляция!)
            header_mgr.update_level_timers(
                level1_remaining=self._full_countdown,   # 120 → 0
                level2_remaining=self._price_countdown,  # 30 → 0
                level3_remaining=self._pump_countdown,   # 10 → 0
                candidates_remaining=self._cand_countdown
            )
            
            # Статусы процессов
            header_mgr.level1_bar.in_progress = self.scan_in_progress
            header_mgr.level2_bar.in_progress = self.price_update_in_progress
            header_mgr.level3_bar.in_progress = self.pump_detect_in_progress
            header_mgr.candidates_bar.in_progress = self.cand_update_in_progress
            
            # Подсчёт по данным TOP200
            if self.rows:
                rows_list = list(self.rows.values())
                # Считаем монеты с любым статусом (кроме пустого)
                selected = len([r for r in rows_list if r.status and r.status.strip()])
                
                # Считаем по типам (watch_type может быть "Памп/Кор", "Пл/Пад", etc.)
                watch_types = [str(r.watch_type or '') for r in rows_list]
                pump_count = sum(1 for wt in watch_types if 'Памп' in wt or 'амп' in wt)
                classic_count = sum(1 for wt in watch_types if 'Кор' in wt or 'Пад' in wt)
                
                # Экстремальные позиции
                extr_count = sum(1 for r in rows_list if r.range_position > 90)
                combo_count = sum(1 for r in rows_list if r.status == 'ВХОД')
                
                header_mgr.update_counts(
                    selected=selected,
                    classic=classic_count,
                    pump_5m=pump_count,
                    pump_1m=extr_count,
                    combo=combo_count
                )
            
            # Подсчёт статусов кандидатов
            if self.rows:
                all_rows = list(self.rows.values())
                watch = sum(1 for r in all_rows if r.status == 'Наблюдение')
                interest = sum(1 for r in all_rows if r.status == 'Интерес')
                ready = sum(1 for r in all_rows if r.status == 'Готовность')
                entry = sum(1 for r in all_rows if r.status == 'ВХОД')
                
                header_mgr.update_status_counts(
                    watch=watch,
                    interest=interest,
                    ready=ready,
                    entry=entry
                )
            
            # Генерируем и устанавливаем текст
            top200_text = header_mgr.get_table1_header_text()
            cand_text = header_mgr.get_table2_header_text()
            
            if top200_text:
                self.lbl_full_timer.setText(top200_text)
            
            if cand_text:
                self.lbl_cand_timer.setText(cand_text)
                
        except Exception as e:
            print(f"[TRACE-V2] Ошибка обновления UI: {e}")
            import traceback
            traceback.print_exc()
    
    # === Сканирование ===
    
    def _start_scan(self):
        if self.scan_in_progress:
            return
        
        self.scan_in_progress = True
        self.lbl_status.setText("⏳ Сканирование...")
        
        if not (V2_AVAILABLE and USE_NEW_UI):
            try:
                self.lbl_full_timer.setStyleSheet("color:#ffd700; font-size:12px; font-weight:bold;")
                self.lbl_full_timer.setText("Пересчёт: 0/…")
            except Exception:
                pass
        
        self.btn_refresh.setEnabled(False)
        
        self.worker = ScannerWorker(
            client=self.client,
            strategy=self.strategy,
            top_n=CONFIG.universe_size,
            max_workers=CONFIG.max_workers
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_all.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()
    
    def _on_progress(self, current: int, total: int, symbol: str):
        self.lbl_progress.setText(f"UNIVERSE: {current}/{total} | {symbol}")
        
        if not (V2_AVAILABLE and USE_NEW_UI):
            try:
                self.lbl_full_timer.setStyleSheet("color:#ffd700; font-size:12px; font-weight:bold;")
                self.lbl_full_timer.setText(f"Пересчёт: {current}/{total}")
            except Exception:
                pass
    
    def _on_finished(self, results: Dict[str, CoinRow]):
        self.rows = results
        self.scan_in_progress = False
        self.btn_refresh.setEnabled(True)
        self.lbl_status.setText(f"✅ Готово ({len(results)} монет)")
        self._full_countdown = 120
        
        if not (V2_AVAILABLE and USE_NEW_UI):
            try:
                self.lbl_full_timer.setStyleSheet("color:#cfcfcf; font-size:12px;")
                self.lbl_full_timer.setText(f"До пересчёта: {self._full_countdown} сек")
            except Exception:
                pass
        
        self._render_main_table()
        self._render_candidates()
        write_bridge_snapshot(self.rows, top_n=30)
        self._save_state()
    
    def _on_error(self, msg: str):
        self.scan_in_progress = False
        self.btn_refresh.setEnabled(True)
        self.lbl_status.setText("❌ Ошибка")
        QMessageBox.warning(self, "Ошибка", msg)
    
    # === Таблицы ===
    
    def _render_main_table(self):
        def get_sort_key(r: CoinRow):
            if self.sort_col == 0:
                return r.vol24_m
            elif self.sort_col == 1:
                return r.symbol
            elif self.sort_col == 2:
                return r.range_position
            elif self.sort_col == 3:
                return r.dist_high_pct
            elif self.sort_col == 4:
                return r.change_24h_pct
            elif self.sort_col == 5:
                return r.price_now
            elif self.sort_col == 6:
                return r.vol24_m
            elif self.sort_col == 7:
                return r.funding_rate
            elif self.sort_col == 8:
                status_order = {"ВХОД": 4, "Готовность": 3, "Интерес": 2, "Наблюдение": 1, "": 0}
                return status_order.get(r.status, 0)
            elif self.sort_col == 9:
                return r.score
            return r.vol24_m
        
        sorted_rows = sorted(self.rows.values(), key=get_sort_key, reverse=self.sort_desc)
        
        start = self.current_page * PAGE_SIZE
        end = start + PAGE_SIZE
        page_rows = sorted_rows[start:end]
        
        self.tbl_main.setRowCount(len(page_rows))
        
        for i, row in enumerate(page_rows):
            rank = start + i + 1
            
            if row.status == "ВХОД":
                color = QColor(255, 80, 80)
            elif row.status == "Готовность":
                color = QColor(255, 180, 0)
            elif row.status == "Интерес":
                color = QColor(100, 180, 255)
            else:
                color = QColor(200, 200, 200)
            
            values = [
                str(rank),
                row.symbol.replace("USDT", ""),
                f"{row.range_position:.1f}",
                f"{row.dist_high_pct:.2f}",
                f"{row.change_24h_pct:+.1f}",
                f"{row.price_now:.6f}",
                f"{row.vol24_m}",
                f"{row.funding_rate*100:.4f}",
                row.status,
                f"{row.score:.0f}"
            ]
            
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter)
                if col >= 8:
                    item.setForeground(color)
                self.tbl_main.setItem(i, col, item)
        
        total_pages = (len(sorted_rows) + PAGE_SIZE - 1) // PAGE_SIZE
        self.lbl_top200.setText(f"📊 TOP 200 | Страница {self.current_page + 1}/{total_pages}")
    
    def _render_candidates(self):
        import time as time_module
        now = time_module.time()
        
        to_remove = []
        for sym, row in self.rows.items():
            if row.status == "Наблюдение" and row.added_at > 0:
                age_min = (now - row.added_at) / 60
                if age_min > 30:
                    to_remove.append(sym)
        
        for sym in to_remove:
            del self.rows[sym]
        
        candidates = [
            r for r in self.rows.values()
            if r.status in ("Интерес", "Готовность", "ВХОД", "Наблюдение")
            and r.score > 20
        ]
        
        status_priority = {"ВХОД": 0, "Готовность": 1, "Интерес": 2, "Наблюдение": 3}
        candidates.sort(key=lambda r: (status_priority.get(r.status, 99), -r.score))
        
        if len(candidates) > 50:  # Увеличено с 30 до 50
            weak = candidates[50:]
            candidates = candidates[:50]
            for r in weak:
                if r.status == "Наблюдение" and r.symbol in self.rows:
                    del self.rows[r.symbol]
        
        self.tbl_cand.setRowCount(len(candidates))
        
        for i, row in enumerate(candidates):
            if row.status == "ВХОД":
                color = QColor(255, 80, 80)
            elif row.status == "Готовность":
                color = QColor(255, 180, 0)
            elif row.status == "Интерес":
                color = QColor(100, 180, 255)
            else:
                color = QColor(150, 150, 150)
            
            if row.added_at > 0:
                age_sec = int(now - row.added_at)
                age_min = age_sec // 60
                age_sec_rem = age_sec % 60
                time_str = f"{age_min}м{age_sec_rem:02d}с"
            else:
                time_str = "—"
            
            values = [
                row.symbol.replace("USDT", ""),
                time_str,
                row.status,
                f"{row.score:.0f}",
                row.watch_type,
                f"{row.range_position:.1f}",
                f"{row.dist_high_pct:.2f}",
                f"{row.change_24h_pct:+.1f}",
                f"{row.entry_price:.6f}",
                f"{row.sl_price:.6f}",
                f"{row.tp1:.6f}",
                f"{row.rr:.2f}",
                "✓" if row.gate0_passed else "✗",
                "✓" if row.gate1_passed else "✗",
                "✓" if row.gate2_passed else "✗"
            ]
            
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter)
                if col <= 4:
                    item.setForeground(color)
                self.tbl_cand.setItem(i, col, item)
        
        self.lbl_candidates.setText(f"🎯 Кандидаты на SHORT ({len(candidates)})")
    
    def _add_to_candidates(self, row: CoinRow):
        import time as time_module
        if row.added_at <= 0:
            row.added_at = time_module.time()
        self.rows[row.symbol] = row
    
    # === Двойной клик и сортировка ===
    
    def _on_double_click(self, row_idx: int, col_idx: int):
        if not HAS_CHART:
            return
        
        try:
            item = self.tbl_main.item(row_idx, 1)
            if not item:
                return
            
            symbol = item.text().strip()
            if not symbol:
                return
            if not symbol.endswith("USDT"):
                symbol += "USDT"
            
            row = self.rows.get(symbol)
            if not row:
                return
            
            klines = {}
            try:
                for tf in ["15", "60", "240"]:
                    klines[tf] = self.client.get_klines(symbol, tf, limit=100)
            except Exception as e:
                print(f"[TRACE] Klines error: {e}")
            
            btc_row = self.rows.get("BTCUSDT")
            btc_price = btc_row.price_now if btc_row else 0
            btc_change = btc_row.change_24h_pct if btc_row else 0
            
            show_chart(row, btc_price, btc_change, klines)
            
        except Exception as e:
            print(f"[TRACE] Double click error: {e}")
    
    def _on_double_click_cand(self, row_idx: int, col_idx: int):
        if not HAS_CHART:
            return
        
        try:
            item = self.tbl_cand.item(row_idx, 0)
            if not item:
                return
            
            symbol = item.text().strip()
            if not symbol:
                return
            if not symbol.endswith("USDT"):
                symbol += "USDT"
            
            row = self.rows.get(symbol)
            if not row:
                return
            
            klines = {}
            try:
                for tf in ["15", "60", "240"]:
                    klines[tf] = self.client.get_klines(symbol, tf, limit=100)
            except Exception as e:
                print(f"[TRACE] Klines error: {e}")
            
            btc_row = self.rows.get("BTCUSDT")
            btc_price = btc_row.price_now if btc_row else 0
            btc_change = btc_row.change_24h_pct if btc_row else 0
            
            show_chart(row, btc_price, btc_change, klines)
            
        except Exception as e:
            print(f"[TRACE] Double click error: {e}")
    
    def _on_header_click(self, col: int):
        if self.sort_col == col:
            self.sort_desc = not self.sort_desc
        else:
            self.sort_col = col
            self.sort_desc = True
        
        self._render_main_table()
    
    # === Пагинация ===
    
    def _prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self._render_main_table()
    
    def _next_page(self):
        total = len(self.rows)
        max_page = (total + PAGE_SIZE - 1) // PAGE_SIZE - 1
        if self.current_page < max_page:
            self.current_page += 1
            self._render_main_table()
    
    # === Countdown ===
    
    def _start_countdown(self):
        if self.scan_in_progress:
            return
        
        self.countdown_sec = 10
        self.countdown_dialog = CountdownDialog(self)
        self.countdown_dialog.set_seconds(self.countdown_sec)
        self.countdown_dialog.rejected.connect(self._cancel_countdown)
        self.countdown_dialog.show()
        
        self.countdown_timer = QTimer(self)
        self.countdown_timer.setInterval(1000)
        self.countdown_timer.timeout.connect(self._countdown_tick)
        self.countdown_timer.start()
    
    def _countdown_tick(self):
        self.countdown_sec -= 1
        
        if self.countdown_sec <= 0:
            self._stop_countdown()
            self._start_scan()
        elif self.countdown_dialog:
            self.countdown_dialog.set_seconds(self.countdown_sec)
    
    def _cancel_countdown(self):
        self._stop_countdown()
        self.lbl_status.setText("Авто-пересчёт отменён")
    
    def _stop_countdown(self):
        if self.countdown_timer:
            self.countdown_timer.stop()
            self.countdown_timer = None
        if self.countdown_dialog:
            self.countdown_dialog.close()
            self.countdown_dialog = None
    
    # === State ===
    
    def _save_state(self):
        try:
            state = {
                "current_page": self.current_page,
                "last_scan": time.time()
            }
            path = os.path.join(CONFIG.base_dir, "scanner_state.json")
            with open(path, "w") as f:
                json.dump(state, f)
        except:
            pass
    
    def _load_state(self):
        try:
            path = os.path.join(CONFIG.base_dir, "scanner_state.json")
            if os.path.exists(path):
                with open(path) as f:
                    state = json.load(f)
                self.current_page = state.get("current_page", 0)
        except:
            pass

    # === ТРЁХУРОВНЕВАЯ СИСТЕМА ТАЙМЕРОВ V2 ===
    
    def _tick_all_levels(self):
        """Единый тик для всех уровней (каждую секунду)."""
        
        # Обновляем V2 UI
        if V2_AVAILABLE and USE_NEW_UI:
            self._update_v2_ui()
        
        # === УРОВЕНЬ 3: Детектор пампов (каждые 10 сек) ===
        if not self.pump_detect_in_progress and self.rows:
            self._pump_countdown -= 1
            if self._pump_countdown <= 0:
                self._pump_countdown = 10
                self._start_pump_detect()
        
        # === УРОВЕНЬ 2: Обновление цен (каждые 30 сек) ===
        if not self.price_update_in_progress and not self.scan_in_progress and self.rows:
            self._price_countdown -= 1
            if self._price_countdown <= 0:
                self._price_countdown = 30
                self._start_price_update()
        
        # === УРОВЕНЬ 1: Полный пересчёт (каждые 120 сек) ===
        if not self.scan_in_progress:
            self._full_countdown -= 1
            if self._full_countdown <= 0:
                self._full_countdown = 120
                self._price_countdown = 30  # Сброс
                self._pump_countdown = 10   # Сброс
                self._start_scan()
        
        # === Обновление кандидатов (каждые 5 сек) ===
        if not self.scan_in_progress and not self.cand_update_in_progress and self.rows:
            self._cand_countdown -= 1
            if self._cand_countdown <= 0:
                self._cand_countdown = 5
                self._start_cand_update()
        
        # Старый UI (если V2 отключен)
        if not (V2_AVAILABLE and USE_NEW_UI):
            try:
                self.lbl_full_timer.setText(f"До пересчёта: {self._full_countdown} сек")
                self.lbl_cand_timer.setText(f"До обновления: {self._cand_countdown} сек")
            except Exception:
                pass
    
    def _start_price_update(self):
        """УРОВЕНЬ 2: Быстрое обновление цен."""
        if not self.rows:
            print("[TRACE-V2] ⚠️ Пропуск обновления цен: нет данных")
            return
        if self.price_update_in_progress:
            print("[TRACE-V2] ⚠️ Пропуск обновления цен: уже в процессе")
            return
        if self.scan_in_progress:
            print("[TRACE-V2] ⚠️ Пропуск обновления цен: идёт полный пересчёт")
            return
        
        if self.price_worker is not None:
            if self.price_worker.isRunning():
                return
            try:
                self.price_worker.deleteLater()
            except Exception:
                pass
            self.price_worker = None
        
        self.price_update_in_progress = True
        print(f"[TRACE-V2] 🔄 Запуск обновления цен (Level 2)... rows={len(self.rows)}")
        
        self.price_worker = PriceUpdateWorker(
            client=self.client,
            rows=self.rows
        )
        self.price_worker.finished.connect(self._on_price_update_finished)
        self.price_worker.error.connect(self._on_price_update_error)
        self.price_worker.start()
    
    def _on_price_update_finished(self, updated_rows: Dict[str, CoinRow]):
        """Цены обновлены."""
        self.price_update_in_progress = False
        
        if updated_rows:
            self.rows = updated_rows
            
            # Перерисовываем таблицы
            self._render_main_table()
            self._render_candidates()
            
            # Принудительное обновление Qt
            self.tbl_main.viewport().update()
            self.tbl_cand.viewport().update()
            QApplication.processEvents()
            
            print(f"[TRACE-V2] ✅ Цены обновлены: {len(updated_rows)} монет")
        else:
            print(f"[TRACE-V2] ⚠️ Пустой результат обновления цен")
    
    def _on_price_update_error(self, msg: str):
        """Ошибка обновления цен."""
        self.price_update_in_progress = False
        print(f"[TRACE-V2] Ошибка обновления цен: {msg}")
    
    def _start_pump_detect(self):
        """УРОВЕНЬ 3: Детектор пампов."""
        if not self.rows or self.pump_detect_in_progress:
            return
        
        if self.pump_worker is not None:
            if self.pump_worker.isRunning():
                return
            try:
                self.pump_worker.deleteLater()
            except Exception:
                pass
            self.pump_worker = None
        
        self.pump_detect_in_progress = True
        
        self.pump_worker = PumpDetectorWorker(
            client=self.client,
            rows=self.rows,
            top_n=200,  # Проверяем ВСЕ 200 монет
            pump_threshold=1.0  # Порог 1% за 5 минут
        )
        self.pump_worker.pump_detected.connect(self._on_pump_detected)
        self.pump_worker.finished.connect(self._on_pump_detect_finished)
        self.pump_worker.error.connect(self._on_pump_detect_error)
        self.pump_worker.start()
    
    def _on_pump_detected(self, symbol: str, change_5m: float, vol_spike: float):
        """Обнаружен памп — добавляем монету в кандидаты."""
        print(f"[TRACE-V2] 🚀 ПАМП: {symbol} +{change_5m:.1f}% за 5м, объём x{vol_spike:.1f}")
        
        # Обновляем статус монеты в self.rows
        if symbol in self.rows:
            row = self.rows[symbol]
            old_status = row.status
            
            # Повышаем статус если памп значительный
            if change_5m >= 3.0:
                row.status = "Готовность"
                row.signal = f"ПАМП +{change_5m:.1f}%"
            elif change_5m >= 2.0:
                if row.status not in ("Готовность", "ВХОД"):
                    row.status = "Интерес"
                    row.signal = f"Памп +{change_5m:.1f}%"
            
            # Сохраняем данные пампа
            row.change_5m = change_5m
            row.volume_spike = vol_spike
            
            # Увеличиваем скор
            row.score = min(100, row.score + int(change_5m * 5))
            
            # Устанавливаем время добавления если ещё не установлено
            if row.added_at == 0:
                import time as time_module
                row.added_at = time_module.time()
            
            print(f"[TRACE-V2] 📊 {symbol}: статус {old_status} → {row.status}, скор={row.score}")
            
            # Перерисовываем таблицы
            self._render_main_table()
            self._render_candidates()
        
        # Добавляем событие в header manager
        if V2_AVAILABLE and USE_NEW_UI:
            try:
                header_mgr = get_header_manager()
                header_mgr.add_event(symbol, f"+{change_5m:.1f}%")
            except Exception:
                pass
    
    def _on_pump_detect_finished(self, pumps: list):
        """Детектор пампов завершён."""
        self.pump_detect_in_progress = False
        if pumps:
            print(f"[TRACE-V2] Детектор: найдено {len(pumps)} пампов")
    
    def _on_pump_detect_error(self, msg: str):
        """Ошибка детектора пампов."""
        self.pump_detect_in_progress = False
        print(f"[TRACE-V2] Ошибка детектора: {msg}")

    def _start_cand_update(self):
        """Запуск фонового обновления кандидатов."""
        if not self.rows or self.cand_update_in_progress:
            return
        
        if self.cand_worker is not None:
            if self.cand_worker.isRunning():
                return
            try:
                self.cand_worker.deleteLater()
            except Exception:
                pass
            self.cand_worker = None
        
        self.cand_update_in_progress = True
        
        if not (V2_AVAILABLE and USE_NEW_UI):
            try:
                self.lbl_cand_timer.setStyleSheet("color:#ffd700; font-size:12px; font-weight:bold;")
                self.lbl_cand_timer.setText("🔄 Сканирование...")
            except Exception:
                pass
        
        self.cand_worker = CandidatesUpdateWorker(
            client=self.client,
            strategy=self.strategy,
            rows=self.rows,
            max_candidates=50,  # Увеличено с 25 до 50
        )
        self.cand_worker.progress.connect(self._on_cand_progress)
        self.cand_worker.coin_updated.connect(self._on_coin_updated)
        self.cand_worker.finished.connect(self._on_cand_finished)
        self.cand_worker.error.connect(self._on_cand_error)
        self.cand_worker.start()
    
    def _on_cand_progress(self, current: int, total: int, symbol: str):
        if not (V2_AVAILABLE and USE_NEW_UI):
            try:
                self.lbl_cand_timer.setText(f"🔄 {current}/{total} | {symbol}")
            except Exception:
                pass
    
    def _on_coin_updated(self, symbol: str, row: CoinRow):
        self.rows[symbol] = row
    
    def _on_cand_finished(self, updated_rows: Dict[str, CoinRow]):
        self.cand_update_in_progress = False
        
        if updated_rows:
            self.rows = updated_rows
        
        self._render_candidates()
        self._render_main_table()
        write_bridge_snapshot(self.rows, top_n=30)
        
        self._cand_countdown = 5
        
        if not (V2_AVAILABLE and USE_NEW_UI):
            try:
                self.lbl_cand_timer.setStyleSheet("color:#22c55e; font-size:12px;")
                self.lbl_cand_timer.setText(f"✓ Обновлено | След: {self._cand_countdown} сек")
            except Exception:
                pass
    
    def _on_cand_error(self, msg: str):
        self.cand_update_in_progress = False
        
        if not (V2_AVAILABLE and USE_NEW_UI):
            try:
                self.lbl_cand_timer.setStyleSheet("color:#ef4444; font-size:12px;")
                self.lbl_cand_timer.setText(f"❌ Ошибка | След: {self._cand_countdown} сек")
            except Exception:
                pass

    def _toggle_live(self):
        if self.live_window is None:
            try:
                from trainer_live import TrainerLive
                self.live_window = TrainerLive()
            except Exception as e:
                QMessageBox.critical(self, "Live", f"Не удалось открыть Live: {e}")
                self.live_window = None
                return

        if self.live_window.isVisible():
            try:
                if hasattr(self.live_window, "set_active"):
                    self.live_window.set_active(False)
            except Exception:
                pass
            self.live_window.hide()
        else:
            self.live_window.show()
            try:
                self.live_window.raise_()
                self.live_window.activateWindow()
                if hasattr(self.live_window, "set_active"):
                    self.live_window.set_active(True)
            except Exception:
                pass

    def _exit_app(self):
        """Корректное завершение приложения."""
        print("[TRACE] Завершение приложения...")
        
        try:
            self.auto_timer.stop()
            self.main_tick_timer.stop()  # Единый таймер V2
            if self.countdown_timer:
                self.countdown_timer.stop()
        except Exception:
            pass
        
        # Останавливаем воркеры
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(2000)
        
        if self.cand_worker and self.cand_worker.isRunning():
            self.cand_worker.stop()
            self.cand_worker.wait(2000)
        
        if self.price_worker and self.price_worker.isRunning():
            self.price_worker.stop()
            self.price_worker.wait(1000)
        
        if self.pump_worker and self.pump_worker.isRunning():
            self.pump_worker.stop()
            self.pump_worker.wait(1000)
        
        if self.live_window:
            try:
                self.live_window.close()
            except Exception:
                pass
        
        self._save_state()
        QApplication.quit()
    
    def closeEvent(self, event):
        self._exit_app()
        event.accept()


def main():
    os.makedirs(CONFIG.base_dir, exist_ok=True)
    os.makedirs(CONFIG.logs_dir, exist_ok=True)
    os.makedirs(CONFIG.ml_data_dir, exist_ok=True)
    
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = MainWindow()
    window.show()
    
    QTimer.singleShot(1000, window._start_scan)
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
