# trainer_live.py
# PySide6 Live window — 3 блока: общая инфо, открытые позиции, закрытые сделки
# ============================================================================

import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QFrame,
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QSplitter,
    QPushButton
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont


BASE_DIR = Path(__file__).resolve().parent
BRIDGE_FILE = BASE_DIR / "bridge_snapshot.json"
STATE_FILE = BASE_DIR / "trainer_state.json"

# Параметры трейдинга
SL_PCT = 2.5
TP1_PCT = 1.5
TP2_PCT = 3.0
TIMEOUT_SEC = 4 * 3600  # 4 часа
MIN_LEVERAGE = 5.0
MAX_LEVERAGE = 20.0
TRADE_AMOUNT = 100.0
INITIAL_BALANCE = 1000.0
MAX_POSITIONS = 50  # Без ограничения
# Вход в сделку ТОЛЬКО по статусу "ВХОД" (все факторы совпали)
ENTRY_STATUSES = ("ВХОД",)

# Файл логов сделок
TRADES_LOG_FILE = BASE_DIR / "trades_log.txt"


@dataclass
class Position:
    """Открытая позиция."""
    symbol: str
    status: str
    watch_type: str
    score: float
    entry_price: float
    current_price: float
    sl_price: float
    tp1_price: float
    leverage: float
    amount: float
    opened_at: float
    tp1_hit: bool = False
    
    @property
    def pnl_pct(self) -> float:
        if self.entry_price <= 0 or self.current_price <= 0:
            return 0.0
        # SHORT: прибыль когда цена падает
        return (self.entry_price - self.current_price) / self.entry_price * 100
    
    @property
    def pnl_usd(self) -> float:
        if self.entry_price <= 0 or self.current_price <= 0:
            return 0.0
        return self.amount * self.leverage * self.pnl_pct / 100
    
    @property
    def age_sec(self) -> float:
        return time.time() - self.opened_at
    
    @property
    def age_str(self) -> str:
        age = int(self.age_sec)
        if age < 60:
            return f"{age}с"
        elif age < 3600:
            return f"{age // 60}м"
        else:
            return f"{age // 3600}ч {(age % 3600) // 60}м"
    
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "status": self.status,
            "watch_type": self.watch_type,
            "score": self.score,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "sl_price": self.sl_price,
            "tp1_price": self.tp1_price,
            "leverage": self.leverage,
            "amount": self.amount,
            "opened_at": self.opened_at,
            "tp1_hit": self.tp1_hit,
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> "Position":
        return cls(
            symbol=d.get("symbol", ""),
            status=d.get("status", ""),
            watch_type=d.get("watch_type", ""),
            score=d.get("score", 0),
            entry_price=d.get("entry_price", 0),
            current_price=d.get("current_price", 0),
            sl_price=d.get("sl_price", 0),
            tp1_price=d.get("tp1_price", 0),
            leverage=d.get("leverage", MIN_LEVERAGE),
            amount=d.get("amount", TRADE_AMOUNT),
            opened_at=d.get("opened_at", time.time()),
            tp1_hit=d.get("tp1_hit", False),
        )


@dataclass
class ClosedTrade:
    """Закрытая сделка."""
    symbol: str
    status: str
    watch_type: str
    score: float
    entry_price: float
    exit_price: float
    leverage: float
    amount: float
    pnl_pct: float
    pnl_usd: float
    reason: str
    closed_at: float
    duration_sec: float
    
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "status": self.status,
            "watch_type": self.watch_type,
            "score": self.score,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "leverage": self.leverage,
            "amount": self.amount,
            "pnl_pct": self.pnl_pct,
            "pnl_usd": self.pnl_usd,
            "reason": self.reason,
            "closed_at": self.closed_at,
            "duration_sec": self.duration_sec,
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> "ClosedTrade":
        return cls(
            symbol=d.get("symbol", ""),
            status=d.get("status", ""),
            watch_type=d.get("watch_type", ""),
            score=d.get("score", 0),
            entry_price=d.get("entry_price", 0),
            exit_price=d.get("exit_price", 0),
            leverage=d.get("leverage", MIN_LEVERAGE),
            amount=d.get("amount", TRADE_AMOUNT),
            pnl_pct=d.get("pnl_pct", 0),
            pnl_usd=d.get("pnl_usd", 0),
            reason=d.get("reason", ""),
            closed_at=d.get("closed_at", time.time()),
            duration_sec=d.get("duration_sec", 0),
        )


def calc_leverage(entry: float, high_24h: float) -> float:
    """Расчёт плеча на основе расстояния до хая."""
    if entry <= 0 or high_24h <= entry:
        return MIN_LEVERAGE
    move = (high_24h - entry) / entry
    if move <= 0:
        return MIN_LEVERAGE
    lev = 0.8 / move
    return max(MIN_LEVERAGE, min(MAX_LEVERAGE, lev))


class TrainerLive(QWidget):
    """
    Окно Live Monitor с 3 блоками:
    1. Общая информация (баланс, WinRate, PnL)
    2. Открытые позиции
    3. Закрытые сделки (история)
    """
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Live Monitor — Trainer")
        self.resize(1300, 900)  # Увеличен размер
        self.setMinimumSize(1000, 700)
        
        # Состояние
        self._active = True
        self._last_mtime = 0
        self.balance = INITIAL_BALANCE
        self.positions: List[Position] = []
        self.closed_trades: List[ClosedTrade] = []
        
        # Статистика
        self.stats = {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "total_pnl": 0.0,
            "today_pnl": 0.0,
            "today_trades": 0,
        }
        
        self._build_ui()
        self._load_state()
        
        # Начальная отрисовка загруженных данных
        self._render_positions()
        self._render_history()
        self._update_stats_ui()
        
        print(f"[LIVE] Запущен: {len(self.positions)} открытых позиций, {len(self.closed_trades)} в истории")
        
        # Таймер обновления (каждые 2 сек)
        self.timer = QTimer(self)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
    
    def _build_ui(self):
        """Построение UI с 3 блоками."""
        self.setStyleSheet("""
            QWidget { background: #0f0f1a; color: #e0e0e0; }
            QFrame { background: #1a1a2e; border-radius: 8px; }
            QTableWidget { 
                background: #0f0f1a; 
                gridline-color: #2a2a3a;
                border: none;
            }
            QTableWidget::item { padding: 4px; }
            QTableWidget::item:selected { background: #2a2a4e; }
            QHeaderView::section { 
                background: #1a1a2e; 
                color: #00d4ff; 
                padding: 6px;
                border: none;
                border-bottom: 2px solid #2a2a3a;
                font-weight: bold;
            }
        """)
        
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)
        
        # === Блок 1: Общая информация ===
        info_frame = QFrame()
        info_layout = QHBoxLayout(info_frame)
        info_layout.setContentsMargins(10, 8, 10, 8)
        
        # Баланс
        self.lbl_balance = QLabel("💰 $1,000.00")
        self.lbl_balance.setStyleSheet("font-size: 16px; font-weight: bold; color: #00d4ff;")
        self.lbl_balance.setMinimumWidth(120)
        info_layout.addWidget(self.lbl_balance)
        
        info_layout.addSpacing(15)
        
        # Позиции
        self.lbl_positions = QLabel("📈 Поз: 0")
        self.lbl_positions.setStyleSheet("font-size: 13px; color: #9aa4b2;")
        info_layout.addWidget(self.lbl_positions)
        
        info_layout.addSpacing(15)
        
        # WinRate
        self.lbl_winrate = QLabel("🎯 WR: —")
        self.lbl_winrate.setStyleSheet("font-size: 13px; color: #9aa4b2;")
        info_layout.addWidget(self.lbl_winrate)
        
        info_layout.addSpacing(15)
        
        # PnL общий
        self.lbl_total_pnl = QLabel("💵 PnL: $0.00")
        self.lbl_total_pnl.setStyleSheet("font-size: 13px; color: #22c55e;")
        info_layout.addWidget(self.lbl_total_pnl)
        
        info_layout.addSpacing(15)
        
        # PnL за день
        self.lbl_today_pnl = QLabel("📅 Сегодня: $0.00")
        self.lbl_today_pnl.setStyleSheet("font-size: 13px; color: #9aa4b2;")
        info_layout.addWidget(self.lbl_today_pnl)
        
        info_layout.addStretch()
        
        # Кнопка закрыть все сделки
        self.btn_close_all = QPushButton("❌ Закрыть все")
        self.btn_close_all.setFixedWidth(110)
        self.btn_close_all.setStyleSheet("""
            QPushButton {
                background: #f97316;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #ea580c;
            }
        """)
        self.btn_close_all.clicked.connect(self._close_all_positions)
        info_layout.addWidget(self.btn_close_all)
        
        info_layout.addSpacing(5)
        
        # Кнопка сброса
        self.btn_reset = QPushButton("🗑 Сброс")
        self.btn_reset.setFixedWidth(80)
        self.btn_reset.setStyleSheet("""
            QPushButton {
                background: #ef4444;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #dc2626;
            }
        """)
        self.btn_reset.clicked.connect(self._reset_all)
        info_layout.addWidget(self.btn_reset)
        
        info_layout.addSpacing(5)
        
        # Кнопка закрыть все сделки
        self.btn_close_all = QPushButton("❌ Закрыть все")
        self.btn_close_all.setFixedWidth(100)
        self.btn_close_all.setStyleSheet("""
            QPushButton {
                background: #f59e0b;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #d97706;
            }
        """)
        self.btn_close_all.clicked.connect(self._close_all_positions)
        info_layout.addWidget(self.btn_close_all)
        
        info_layout.addSpacing(10)
        
        # Статус bridge
        self.lbl_bridge = QLabel("🔗 Bridge: ожидание...")
        self.lbl_bridge.setStyleSheet("font-size: 12px; color: #666;")
        info_layout.addWidget(self.lbl_bridge)
        
        root.addWidget(info_frame)
        
        # === Splitter для таблиц ===
        splitter = QSplitter(Qt.Vertical)
        
        # === Блок 2: Открытые позиции ===
        pos_widget = QWidget()
        pos_layout = QVBoxLayout(pos_widget)
        pos_layout.setContentsMargins(0, 0, 0, 0)
        
        lbl_pos = QLabel("📊 Открытые позиции")
        lbl_pos.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffd700; padding: 5px;")
        pos_layout.addWidget(lbl_pos)
        
        self.tbl_positions = QTableWidget(0, 12)
        self.tbl_positions.setHorizontalHeaderLabels([
            "Монета", "Статус", "Тип", "Скор", "Вход", "Текущая",
            "SL", "TP1", "PnL%", "PnL$", "Время", "X"
        ])
        self.tbl_positions.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_positions.verticalHeader().setVisible(False)
        self.tbl_positions.setMinimumHeight(300)  # Минимум для ~10 позиций
        self.tbl_positions.verticalHeader().setDefaultSectionSize(28)  # Высота строки
        pos_layout.addWidget(self.tbl_positions)
        
        splitter.addWidget(pos_widget)
        
        # === Блок 3: Закрытые сделки с фильтрами ===
        hist_widget = QWidget()
        hist_layout = QVBoxLayout(hist_widget)
        hist_layout.setContentsMargins(0, 0, 0, 0)
        
        # Заголовок + кнопки фильтров
        hist_header = QHBoxLayout()
        
        lbl_hist = QLabel("📜 История сделок")
        lbl_hist.setStyleSheet("font-size: 14px; font-weight: bold; color: #00d4ff; padding: 5px;")
        hist_header.addWidget(lbl_hist)
        
        hist_header.addStretch()
        
        # Кнопки фильтров по периоду
        self.period_filter = "all"  # all, day, 3days, week, month
        
        self.btn_all = QPushButton("Все")
        self.btn_day = QPushButton("Сутки")
        self.btn_3days = QPushButton("3 дня")
        self.btn_week = QPushButton("Неделя")
        self.btn_month = QPushButton("Месяц")
        
        for btn, period in [
            (self.btn_all, "all"),
            (self.btn_day, "day"),
            (self.btn_3days, "3days"),
            (self.btn_week, "week"),
            (self.btn_month, "month"),
        ]:
            btn.setCheckable(True)
            btn.setFixedWidth(70)
            btn.setStyleSheet("""
                QPushButton {
                    background: #2a2a3a;
                    color: #9aa4b2;
                    border: 1px solid #3a3a4a;
                    border-radius: 4px;
                    padding: 4px 8px;
                }
                QPushButton:checked {
                    background: #00d4ff;
                    color: #000;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: #3a3a5a;
                }
            """)
            btn.clicked.connect(lambda checked, p=period: self._set_period_filter(p))
            hist_header.addWidget(btn)
        
        self.btn_all.setChecked(True)
        
        # Метка итогов за период
        self.lbl_period_stats = QLabel("")
        self.lbl_period_stats.setStyleSheet("font-size: 12px; color: #9aa4b2; padding-left: 15px;")
        hist_header.addWidget(self.lbl_period_stats)
        
        hist_layout.addLayout(hist_header)
        
        self.tbl_history = QTableWidget(0, 12)
        self.tbl_history.setHorizontalHeaderLabels([
            "Время", "Монета", "Статус", "Тип", "Скор", "Вход",
            "Выход", "Плечо", "PnL%", "PnL$", "Причина", "Длит."
        ])
        self.tbl_history.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_history.verticalHeader().setVisible(False)
        hist_layout.addWidget(self.tbl_history)
        
        splitter.addWidget(hist_widget)
        splitter.setSizes([200, 400])
        
        root.addWidget(splitter)
    
    def set_active(self, active: bool):
        """Включить/выключить обновления."""
        self._active = active
        if active:
            self.timer.start()
        else:
            self.timer.stop()
    
    def _tick(self):
        """Тик таймера — обновление данных."""
        if not self._active:
            return
        
        # Проверяем bridge
        self._check_bridge()
        
        # Обновляем цены и проверяем SL/TP
        self._update_prices()
        self._check_sl_tp()
        
        # Обновляем UI
        self._render_positions()
        self._render_history()
        self._update_stats_ui()
        
        # Сохраняем состояние
        self._save_state()
    
    def _check_bridge(self):
        """Проверка и чтение bridge_snapshot.json."""
        if not BRIDGE_FILE.exists():
            self.lbl_bridge.setText("⚠ bridge_snapshot.json не найден")
            return
        
        try:
            mtime = BRIDGE_FILE.stat().st_mtime
            if mtime == self._last_mtime:
                return
            self._last_mtime = mtime
            
            with open(BRIDGE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            items = data.get("items", [])
            age = int(time.time() - mtime)
            self.lbl_bridge.setText(f"🔗 Bridge: {len(items)} items | {age}s ago")
            
            # Пытаемся открыть позиции — все со статусом "Готовность"
            self._try_open_positions(items)
                
        except Exception as e:
            self.lbl_bridge.setText(f"❌ Bridge error: {e}")
    
    def _try_open_positions(self, items: List[dict]):
        """Попытка открыть позиции из bridge — ВСЕ со статусом Готовность."""
        candidates = [
            x for x in items 
            if x.get("status") in ENTRY_STATUSES
        ]
        candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        opened_count = 0
        
        for item in candidates:  # Без ограничения — открываем все
            if len(self.positions) >= MAX_POSITIONS:
                break
            
            symbol = item.get("symbol", "")
            if not symbol:
                continue
            
            # Проверяем что нет такой позиции
            if any(p.symbol == symbol for p in self.positions):
                continue
            
            # Получаем цену входа
            entry = item.get("price_now", 0)
            if entry <= 0:
                entry = item.get("entry", 0)
            if entry <= 0:
                continue
            
            # SL и TP из bridge или вычисляем
            sl_from_bridge = item.get("sl", 0)
            tp1_from_bridge = item.get("tp1", 0)
            
            if sl_from_bridge > 0:
                sl_price = sl_from_bridge
            else:
                sl_price = entry * (1 + SL_PCT / 100)
            
            if tp1_from_bridge > 0:
                tp1_price = tp1_from_bridge
            else:
                tp1_price = entry * (1 - TP1_PCT / 100)
            
            # Плечо
            high_24h = item.get("high_24h", entry * 1.05)
            leverage = calc_leverage(entry, high_24h)
            
            pos = Position(
                symbol=symbol,
                status=item.get("status", ""),
                watch_type=item.get("watch_type", ""),
                score=item.get("score", 0),
                entry_price=entry,
                current_price=entry,  # Начальная цена = цена входа
                sl_price=sl_price,
                tp1_price=tp1_price,
                leverage=leverage,
                amount=TRADE_AMOUNT,
                opened_at=time.time(),
            )
            self.positions.append(pos)
            print(f"[LIVE] Открыта позиция: {symbol} @ {entry:.6f}, SL={sl_price:.6f}, TP1={tp1_price:.6f}")
    
    def _update_prices(self):
        """Обновление текущих цен (из bridge или API)."""
        if not BRIDGE_FILE.exists():
            return
        
        try:
            with open(BRIDGE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            items = data.get("items", [])
            prices = {x.get("symbol"): x.get("price_now", 0) for x in items}
            
            for pos in self.positions:
                if pos.symbol in prices and prices[pos.symbol] > 0:
                    pos.current_price = prices[pos.symbol]
                    
        except Exception:
            pass
    
    def _check_sl_tp(self):
        """Проверка SL/TP для открытых позиций."""
        to_close = []
        
        for pos in self.positions:
            if pos.current_price <= 0 or pos.entry_price <= 0:
                continue
            
            # SL hit
            if pos.current_price >= pos.sl_price:
                to_close.append((pos, "SL_HIT"))
                continue
            
            # TP1 hit (частичное закрытие)
            if not pos.tp1_hit and pos.current_price <= pos.tp1_price:
                self._partial_close(pos)
                pos.tp1_hit = True
                continue
            
            # TP2 hit
            tp2_price = pos.entry_price * (1 - TP2_PCT / 100)
            if pos.current_price <= tp2_price:
                to_close.append((pos, "TP2_HIT"))
                continue
            
            # Timeout
            if pos.age_sec > TIMEOUT_SEC:
                to_close.append((pos, "TIMEOUT"))
        
        for pos, reason in to_close:
            self._close_position(pos, reason)
    
    def _partial_close(self, pos: Position):
        """Частичное закрытие (50%) на TP1."""
        half_amount = pos.amount * 0.5
        pnl_pct = pos.pnl_pct
        pnl_usd = half_amount * pos.leverage * pnl_pct / 100
        
        self.balance += pnl_usd
        pos.amount = half_amount
        
        # Записываем в историю
        trade = ClosedTrade(
            symbol=pos.symbol,
            status=pos.status,
            watch_type=pos.watch_type,
            score=pos.score,
            entry_price=pos.entry_price,
            exit_price=pos.current_price,
            leverage=pos.leverage,
            amount=half_amount,
            pnl_pct=pnl_pct,
            pnl_usd=pnl_usd,
            reason="TP1_HIT",
            closed_at=time.time(),
            duration_sec=pos.age_sec,
        )
        self.closed_trades.insert(0, trade)
        self._update_stats(trade)
    
    def _close_position(self, pos: Position, reason: str):
        """Полное закрытие позиции."""
        pnl_pct = pos.pnl_pct
        pnl_usd = pos.amount * pos.leverage * pnl_pct / 100
        
        self.balance += pnl_usd
        
        # Записываем в историю
        trade = ClosedTrade(
            symbol=pos.symbol,
            status=pos.status,
            watch_type=pos.watch_type,
            score=pos.score,
            entry_price=pos.entry_price,
            exit_price=pos.current_price,
            leverage=pos.leverage,
            amount=pos.amount,
            pnl_pct=pnl_pct,
            pnl_usd=pnl_usd,
            reason=reason,
            closed_at=time.time(),
            duration_sec=pos.age_sec,
        )
        self.closed_trades.insert(0, trade)
        self._update_stats(trade)
        
        # Логируем сделку
        self._log_trade(trade)
        
        # Удаляем позицию
        self.positions = [p for p in self.positions if p.symbol != pos.symbol]
    
    def _manual_close(self, symbol: str):
        """Ручное закрытие позиции по символу."""
        pos = next((p for p in self.positions if p.symbol == symbol), None)
        if pos:
            self._close_position(pos, "MANUAL")
            self._render_positions()
            self._render_history()
            self._update_stats_ui()
            self._save_state()
            print(f"[LIVE] Позиция {symbol} закрыта вручную")
    
    def _close_all_positions(self):
        """Закрыть все открытые позиции."""
        if not self.positions:
            return
        
        from PySide6.QtWidgets import QMessageBox
        
        reply = QMessageBox.question(
            self,
            "Закрыть все позиции",
            f"Вы уверены что хотите закрыть все {len(self.positions)} позиций?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            count = len(self.positions)
            # Копируем список чтобы избежать проблем при итерации
            for pos in list(self.positions):
                self._close_position(pos, "MANUAL_ALL")
            
            self._render_positions()
            self._render_history()
            self._update_stats_ui()
            self._save_state()
            print(f"[LIVE] Закрыто {count} позиций")
    
    def _update_stats(self, trade: ClosedTrade):
        """Обновление статистики."""
        self.stats["total_trades"] += 1
        self.stats["total_pnl"] += trade.pnl_usd
        
        if trade.pnl_usd > 0:
            self.stats["wins"] += 1
        else:
            self.stats["losses"] += 1
        
        # Проверяем сегодняшние сделки
        today_start = time.time() - (time.time() % 86400)
        if trade.closed_at >= today_start:
            self.stats["today_trades"] += 1
            self.stats["today_pnl"] += trade.pnl_usd
    
    def _render_positions(self):
        """Отрисовка таблицы позиций с кнопками закрытия."""
        self.tbl_positions.setRowCount(len(self.positions))
        
        for i, pos in enumerate(self.positions):
            pnl_color = QColor("#22c55e") if pos.pnl_usd >= 0 else QColor("#ef4444")
            
            values = [
                pos.symbol.replace("USDT", ""),
                pos.status,
                pos.watch_type,
                f"{pos.score:.0f}",
                f"{pos.entry_price:.6f}",
                f"{pos.current_price:.6f}",
                f"{pos.sl_price:.6f}",
                f"{pos.tp1_price:.6f}",
                f"{pos.pnl_pct:+.2f}%",
                f"${pos.pnl_usd:+.2f}",
                pos.age_str,
            ]
            
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter)
                if col in (8, 9):
                    item.setForeground(pnl_color)
                self.tbl_positions.setItem(i, col, item)
            
            # Кнопка закрытия
            btn_close = QPushButton("✕")
            btn_close.setFixedSize(28, 24)
            btn_close.setStyleSheet("""
                QPushButton {
                    background: #ef4444;
                    color: white;
                    border: none;
                    border-radius: 3px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: #dc2626;
                }
            """)
            btn_close.clicked.connect(lambda checked, s=pos.symbol: self._manual_close(s))
            self.tbl_positions.setCellWidget(i, 11, btn_close)
    
    def _render_history(self):
        """Отрисовка таблицы истории с учётом фильтра."""
        # Фильтруем по периоду
        trades = self._filter_trades_by_period()
        
        # Показываем последние 50 сделок
        trades = trades[:50]
        self.tbl_history.setRowCount(len(trades))
        
        for i, trade in enumerate(trades):
            pnl_color = QColor("#22c55e") if trade.pnl_usd >= 0 else QColor("#ef4444")
            
            # Форматируем время
            closed_time = time.strftime("%d.%m %H:%M", time.localtime(trade.closed_at))
            duration = f"{int(trade.duration_sec // 60)}м"
            
            values = [
                closed_time,
                trade.symbol.replace("USDT", ""),
                trade.status,
                trade.watch_type,
                f"{trade.score:.0f}",
                f"{trade.entry_price:.6f}",
                f"{trade.exit_price:.6f}",
                f"{trade.leverage:.1f}x",
                f"{trade.pnl_pct:+.2f}%",
                f"${trade.pnl_usd:+.2f}",
                trade.reason,
                duration,
            ]
            
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter)
                if col in (8, 9):
                    item.setForeground(pnl_color)
                self.tbl_history.setItem(i, col, item)
        
        # Обновляем статистику за период
        self._update_period_stats(trades)
    
    def _filter_trades_by_period(self) -> List[ClosedTrade]:
        """Фильтрация сделок по выбранному периоду."""
        if self.period_filter == "all":
            return self.closed_trades
        
        now = time.time()
        
        if self.period_filter == "day":
            cutoff = now - 86400  # 24 часа
        elif self.period_filter == "3days":
            cutoff = now - 86400 * 3
        elif self.period_filter == "week":
            cutoff = now - 86400 * 7
        elif self.period_filter == "month":
            cutoff = now - 86400 * 30
        else:
            return self.closed_trades
        
        return [t for t in self.closed_trades if t.closed_at >= cutoff]
    
    def _set_period_filter(self, period: str):
        """Установка фильтра по периоду."""
        self.period_filter = period
        
        # Обновляем кнопки
        self.btn_all.setChecked(period == "all")
        self.btn_day.setChecked(period == "day")
        self.btn_3days.setChecked(period == "3days")
        self.btn_week.setChecked(period == "week")
        self.btn_month.setChecked(period == "month")
        
        # Перерисовываем
        self._render_history()
    
    def _update_period_stats(self, trades: List[ClosedTrade]):
        """Обновление статистики за выбранный период."""
        if not trades:
            self.lbl_period_stats.setText("Нет сделок за период")
            return
        
        total = len(trades)
        wins = sum(1 for t in trades if t.pnl_usd > 0)
        losses = total - wins
        total_pnl = sum(t.pnl_usd for t in trades)
        winrate = wins / total * 100 if total > 0 else 0
        
        pnl_color = "#22c55e" if total_pnl >= 0 else "#ef4444"
        
        period_names = {
            "all": "всего",
            "day": "за сутки",
            "3days": "за 3 дня",
            "week": "за неделю",
            "month": "за месяц",
        }
        period_name = period_names.get(self.period_filter, "")
        
        self.lbl_period_stats.setText(
            f"📊 {period_name}: {total} сделок | "
            f"WR: {winrate:.0f}% ({wins}W/{losses}L) | "
            f"<span style='color:{pnl_color}'>PnL: ${total_pnl:+.2f}</span>"
        )
    
    def _update_stats_ui(self):
        """Обновление UI статистики."""
        # Баланс
        balance_color = "#22c55e" if self.balance >= INITIAL_BALANCE else "#ef4444"
        self.lbl_balance.setText(f"💰 ${self.balance:,.2f}")
        self.lbl_balance.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {balance_color};")
        
        # Позиции
        self.lbl_positions.setText(f"📈 Поз: {len(self.positions)}")
        
        # WinRate
        total = self.stats["total_trades"]
        if total > 0:
            winrate = self.stats["wins"] / total * 100
            self.lbl_winrate.setText(f"🎯 WR: {winrate:.0f}% ({self.stats['wins']}/{total})")
        else:
            self.lbl_winrate.setText("🎯 WR: —")
        
        # PnL общий
        pnl = self.stats["total_pnl"]
        pnl_color = "#22c55e" if pnl >= 0 else "#ef4444"
        self.lbl_total_pnl.setText(f"💵 PnL: ${pnl:+,.2f}")
        self.lbl_total_pnl.setStyleSheet(f"font-size: 13px; color: {pnl_color};")
        
        # PnL за день
        today_pnl = self.stats["today_pnl"]
        today_color = "#22c55e" if today_pnl >= 0 else "#ef4444"
        self.lbl_today_pnl.setText(f"📅 Сегодня: ${today_pnl:+.2f} ({self.stats['today_trades']})")
        self.lbl_today_pnl.setStyleSheet(f"font-size: 13px; color: {today_color};")
    
    def _save_state(self):
        """Сохранение состояния."""
        try:
            state = {
                "balance": self.balance,
                "positions": [p.to_dict() for p in self.positions],
                "closed_trades": [t.to_dict() for t in self.closed_trades[:100]],
                "stats": self.stats,
            }
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception:
            pass
    
    def _load_state(self):
        """Загрузка состояния."""
        # Дефолтные значения stats
        default_stats = {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "total_pnl": 0.0,
            "today_pnl": 0.0,
            "today_trades": 0,
        }
        
        try:
            if not STATE_FILE.exists():
                self.stats = default_stats.copy()
                return
            
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
            
            self.balance = state.get("balance", INITIAL_BALANCE)
            
            # Загружаем позиции с валидацией
            raw_positions = state.get("positions", [])
            self.positions = []
            for p in raw_positions:
                pos = Position.from_dict(p)
                # Валидация: пропускаем "битые" позиции
                if pos.entry_price <= 0:
                    print(f"[LIVE] Пропущена битая позиция: {pos.symbol} (entry=0)")
                    continue
                # Починка SL/TP если = 0
                if pos.sl_price <= 0:
                    pos.sl_price = pos.entry_price * (1 + SL_PCT / 100)
                if pos.tp1_price <= 0:
                    pos.tp1_price = pos.entry_price * (1 - TP1_PCT / 100)
                # Починка current_price если = 0
                if pos.current_price <= 0:
                    pos.current_price = pos.entry_price
                self.positions.append(pos)
            
            self.closed_trades = [ClosedTrade.from_dict(t) for t in state.get("closed_trades", [])]
            
            # Загружаем stats с проверкой всех ключей
            loaded_stats = state.get("stats", {})
            self.stats = default_stats.copy()
            for key in default_stats:
                if key in loaded_stats:
                    self.stats[key] = loaded_stats[key]
            
            # Сбрасываем дневную статистику если новый день
            today_start = time.time() - (time.time() % 86400)
            last_trade_time = self.closed_trades[0].closed_at if self.closed_trades else 0
            if last_trade_time < today_start:
                self.stats["today_pnl"] = 0.0
                self.stats["today_trades"] = 0
            
            print(f"[LIVE] Загружено: {len(self.positions)} позиций, {len(self.closed_trades)} сделок")
                
        except Exception as e:
            print(f"[DEBUG] Load state error: {e}")
            self.stats = default_stats.copy()
    
    def closeEvent(self, event):
        """При закрытии сохраняем состояние."""
        self._save_state()
        event.accept()
    
    def _reset_all(self):
        """Полный сброс всех данных."""
        from PySide6.QtWidgets import QMessageBox
        
        reply = QMessageBox.question(
            self,
            "Сброс данных",
            "Вы уверены? Это удалит:\n"
            "• Все открытые позиции\n"
            "• Всю историю сделок\n"
            "• Статистику\n\n"
            "Баланс будет сброшен до $1,000.00",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.balance = INITIAL_BALANCE
            self.positions = []
            self.closed_trades = []
            self.stats = {
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "total_pnl": 0.0,
                "today_pnl": 0.0,
                "today_trades": 0,
            }
            
            # Удаляем файл состояния
            try:
                if STATE_FILE.exists():
                    STATE_FILE.unlink()
            except Exception:
                pass
            
            # Обновляем UI
            self._render_positions()
            self._render_history()
            self._update_stats_ui()
            
            print("[LIVE] Все данные сброшены")
    
    def _manual_close(self, symbol: str):
        """Ручное закрытие позиции по символу."""
        pos = next((p for p in self.positions if p.symbol == symbol), None)
        if pos:
            self._close_position(pos, "MANUAL")
            self._render_positions()
            self._render_history()
            self._update_stats_ui()
            self._save_state()
            print(f"[LIVE] Позиция {symbol} закрыта вручную")
    
    def _close_all_positions(self):
        """Закрытие всех позиций."""
        from PySide6.QtWidgets import QMessageBox
        
        if not self.positions:
            QMessageBox.information(self, "Информация", "Нет открытых позиций")
            return
        
        reply = QMessageBox.question(
            self,
            "Закрыть все позиции",
            f"Вы уверены, что хотите закрыть все {len(self.positions)} позиций?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            positions_to_close = list(self.positions)
            for pos in positions_to_close:
                self._close_position(pos, "MANUAL_ALL")
            
            self._render_positions()
            self._render_history()
            self._update_stats_ui()
            self._save_state()
            print(f"[LIVE] Все позиции ({len(positions_to_close)}) закрыты")
    
    def _log_trade(self, trade: ClosedTrade):
        """Запись сделки в лог-файл."""
        try:
            log_line = (
                f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(trade.closed_at))} | "
                f"{trade.symbol} | {trade.status} | {trade.watch_type} | "
                f"Score: {trade.score:.0f} | "
                f"Entry: {trade.entry_price:.6f} | Exit: {trade.exit_price:.6f} | "
                f"Leverage: {trade.leverage:.1f}x | "
                f"PnL: {trade.pnl_pct:+.2f}% (${trade.pnl_usd:+.2f}) | "
                f"Reason: {trade.reason} | "
                f"Duration: {int(trade.duration_sec // 60)}m\n"
            )
            
            with open(TRADES_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(log_line)
                
        except Exception as e:
            print(f"[DEBUG] Log trade error: {e}")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = TrainerLive()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
