# ===== ui/chart_window.py =====
# Окно графиков монеты v1.0
# ==========================

from typing import Dict, List, Optional, Tuple
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QSizePolicy

COLORS = {"bg": "#0f0f1a", "panel": "#1a1a2e", "border": "#2a2a4a", "text": "#e6e6e6", "text_dim": "#888888", "green": "#00c853", "red": "#ff5252", "yellow": "#ffd700", "blue": "#00d4ff", "orange": "#ff9800", "support": "#00e676", "resistance": "#ff5252", "local_max": "#ffd700", "entry": "#ff1744", "candle_up": "#26a69a", "candle_down": "#ef5350", "volume_high": "#b0bec5", "volume_low": "#37474f"}

def trend_arrow(v): return "▲▲" if v > 0.5 else "▲" if v > 0 else "▼▼" if v < -0.5 else "▼" if v < 0 else "—"
def trend_text(p): return "Сильный рост" if p > 5 else "Рост" if p > 2 else "Слабый рост" if p > 0.5 else "Флэт" if p > -0.5 else "Слабое падение" if p > -2 else "Падение" if p > -5 else "Сильное падение"
def trend_color(p): return COLORS["green"] if p > 0.5 else COLORS["red"] if p < -0.5 else COLORS["text_dim"]
def market_state(b): return ("Сильно бычий", COLORS["green"]) if b > 3 else ("Бычий", COLORS["green"]) if b > 1 else ("Нейтральный", COLORS["text_dim"]) if b > -1 else ("Медвежий", COLORS["red"]) if b > -3 else ("Сильно медвежий", COLORS["red"])

def maturity_text(row):
    conds, sc = [], 0
    for name, ok in [("Близко к хаю", row.dist_high_pct <= 5), ("Истощение тренда", getattr(row, 'exhaustion', 0) >= 0.3), ("Тренд 1ч вниз", row.trend_1h_ppm < 0), ("Слабее BTC", getattr(row, 'btc_div_1h', 0) < 0), ("Подтверждение падения", getattr(row, 'structure_score', 50) >= 50)]:
        conds.append((name, ok))
        if ok: sc += 1
    pct = int(sc / 5 * 100)
    desc = "Готов к входу!" if pct >= 80 else "Ждём разворот тренда" if pct >= 60 and not conds[2][1] else "Ждём подтверждения" if pct >= 60 else "Ждём подход к хаю" if pct >= 40 and not conds[0][1] else "Ждём истощения" if pct >= 40 else "Мониторим"
    return pct, desc, conds

class InfoPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"QFrame{{background:{COLORS['panel']};border:1px solid {COLORS['border']};border-radius:8px;}}QLabel{{color:{COLORS['text']};font-size:13px;}}")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(6)
        
        row1 = QHBoxLayout()
        self.lbl_symbol = QLabel("—"); self.lbl_symbol.setStyleSheet(f"font-size:20px;font-weight:bold;color:{COLORS['blue']};")
        self.lbl_status = QLabel("—")
        self.lbl_score = QLabel("Скор: —")
        self.lbl_type = QLabel("—"); self.lbl_type.setStyleSheet(f"color:{COLORS['text_dim']};")
        for w in [self.lbl_symbol, self.lbl_status, self.lbl_score, self.lbl_type]: row1.addWidget(w)
        row1.addStretch(); layout.addLayout(row1)
        
        row2 = QHBoxLayout()
        self.lbl_price = QLabel("Цена: —"); self.lbl_change24 = QLabel("24ч: —"); self.lbl_dist_high = QLabel("До хая: —"); self.lbl_rr = QLabel("R/R: —")
        for w in [self.lbl_price, self.lbl_change24, self.lbl_dist_high, self.lbl_rr]: row2.addWidget(w)
        row2.addStretch(); layout.addLayout(row2)
        
        row3 = QHBoxLayout()
        self.lbl_trend_3h = QLabel("📈 Тренд 3ч: —"); self.lbl_trend_24h = QLabel("Тренд 24ч: —")
        row3.addWidget(self.lbl_trend_3h); row3.addWidget(self.lbl_trend_24h); row3.addStretch(); layout.addLayout(row3)
        
        row4 = QHBoxLayout()
        self.lbl_market = QLabel("🌍 Рынок: —"); self.lbl_btc = QLabel("BTC: —"); self.lbl_corr = QLabel("Корреляция: —")
        for w in [self.lbl_market, self.lbl_btc, self.lbl_corr]: row4.addWidget(w)
        row4.addStretch(); layout.addLayout(row4)
        
        self.lbl_maturity = QLabel("🎯 Зрелость: —"); self.lbl_maturity.setStyleSheet("font-size:14px;font-weight:bold;")
        self.lbl_waiting = QLabel("Ждём: —"); self.lbl_waiting.setWordWrap(True); self.lbl_waiting.setStyleSheet(f"color:{COLORS['yellow']};")
        self.lbl_conditions = QLabel(""); self.lbl_conditions.setStyleSheet(f"color:{COLORS['text_dim']};font-size:12px;")
        for w in [self.lbl_maturity, self.lbl_waiting, self.lbl_conditions]: layout.addWidget(w)
    
    def update_data(self, row, btc_price=0, btc_change=0):
        self.lbl_symbol.setText(row.symbol.replace("USDT", ""))
        status = getattr(row, 'status', '') or ''
        bg = {"ВХОД": COLORS["red"], "Готовность": COLORS["orange"], "Интерес": COLORS["blue"]}.get(status, COLORS["text_dim"])
        self.lbl_status.setText(status or "—"); self.lbl_status.setStyleSheet(f"font-size:14px;padding:2px 8px;border-radius:4px;background:{bg};color:#fff;")
        score = getattr(row, 'score', 0) or 0
        self.lbl_score.setText(f"Скор: {score:.0f}"); self.lbl_type.setText(getattr(row, 'watch_type', '') or "—")
        self.lbl_price.setText(f"Цена: {row.price_now:.6f}")
        c24 = getattr(row, 'change_24h_pct', 0); col = COLORS["green"] if c24 > 0 else COLORS["red"] if c24 < 0 else COLORS["text"]
        self.lbl_change24.setText(f"<span style='color:{col}'>24ч: {c24:+.1f}%</span>")
        dist = getattr(row, 'dist_high_pct', 0)
        rr = getattr(row, 'rr', 0)
        self.lbl_dist_high.setText(f"До хая: {dist:.2f}%"); self.lbl_rr.setText(f"R/R: {rr:.2f}")
        t3h = getattr(row, 'trend_3h_ppm', 0) * 180
        self.lbl_trend_3h.setText(f"📈 Тренд 3ч: <span style='color:{trend_color(t3h)}'>{trend_arrow(t3h)} {trend_text(t3h)} ({t3h:+.1f}%)</span>")
        self.lbl_trend_24h.setText(f"Тренд 24ч: <span style='color:{trend_color(c24)}'>{trend_arrow(c24)} {trend_text(c24)}</span>")
        mkt_text, mkt_color = market_state(btc_change)
        self.lbl_market.setText(f"🌍 Рынок: <span style='color:{mkt_color}'>{mkt_text}</span>")
        self.lbl_btc.setText(f"BTC: <span style='color:{COLORS['green'] if btc_change > 0 else COLORS['red']}'>{btc_change:+.1f}%</span>")
        div = getattr(row, 'btc_div_1h', 0); corr = "сильная" if abs(div) < 0.01 else "средняя" if abs(div) < 0.03 else "слабая"
        self.lbl_corr.setText(f"Корреляция: {corr}")
        pct, desc, conditions = maturity_text(row)
        mat_color = COLORS["green"] if pct >= 80 else COLORS["yellow"] if pct >= 50 else COLORS["text_dim"]
        self.lbl_maturity.setText(f"🎯 Зрелость: <span style='color:{mat_color}'>{pct}%</span>")
        self.lbl_waiting.setText(f"Ждём: {desc}")
        self.lbl_conditions.setText(" │ ".join([f"<span style='color:{COLORS['green'] if ok else COLORS['text_dim']}'>{'✓' if ok else '✗'} {n}</span>" for n, ok in conditions]))

class CandleChartWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(300); self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.klines, self.supports, self.resistances, self.local_maxes = [], [], [], []
        self.entry_price, self.entry_index = None, None
        self.margin, self.volume_h = (60, 20, 20, 60), 50
    
    def set_data(self, klines, supports=None, resistances=None, entry_price=None):
        self.klines = klines or []; self.supports = supports or []; self.resistances = resistances or []
        self.entry_price = entry_price
        self.local_maxes = [i for i in range(1, len(self.klines)-1) if float(self.klines[i].get("high",0)) > float(self.klines[i-1].get("high",0)) and float(self.klines[i].get("high",0)) > float(self.klines[i+1].get("high",0))] if len(self.klines) >= 3 else []
        self.entry_index = next((i for i, k in enumerate(self.klines) if entry_price and float(k.get("low",0)) <= entry_price <= float(k.get("high",0))), None)
        self.update()
    
    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); p.fillRect(self.rect(), QColor(COLORS["bg"]))
        if not self.klines: p.setPen(QColor(COLORS["text_dim"])); p.drawText(self.rect(), Qt.AlignCenter, "Нет данных"); return
        ml, mr, mt, mb = self.margin; w, h = self.width() - ml - mr, self.height() - mt - mb
        if w <= 0 or h <= 0: return
        prices = [p for k in self.klines for p in [float(k.get("high",0)), float(k.get("low",0))]]
        pmin, pmax = min(prices) * 0.998, max(prices) * 1.002; prange = pmax - pmin
        if prange <= 0: return
        n, cw = len(self.klines), max(2, (w - len(self.klines)) / len(self.klines))
        y = lambda pr: int(mt + h - (pr - pmin) / prange * h); x = lambda i: int(ml + i * (cw + 1))
        
        p.setPen(QPen(QColor("#2a2a3a"), 1, Qt.DotLine))
        for i in range(5):
            pr = pmin + prange * i / 4; p.drawLine(ml, y(pr), self.width() - mr, y(pr))
            p.setPen(QColor(COLORS["text_dim"])); p.drawText(5, y(pr) + 4, f"{pr:.4f}"); p.setPen(QPen(QColor("#2a2a3a"), 1, Qt.DotLine))
        
        p.setPen(QPen(QColor(COLORS["resistance"]), 1, Qt.DashLine))
        for lv in self.resistances:
            if pmin <= lv <= pmax: p.drawLine(ml, y(lv), self.width() - mr, y(lv))
        p.setPen(QPen(QColor(COLORS["support"]), 1, Qt.DashLine))
        for lv in self.supports:
            if pmin <= lv <= pmax: p.drawLine(ml, y(lv), self.width() - mr, y(lv))
        
        for i, k in enumerate(self.klines):
            o, hi, lo, c = [float(k.get(f,0)) for f in ["open","high","low","close"]]
            col = QColor(COLORS["candle_up"] if c >= o else COLORS["candle_down"])
            p.setPen(QPen(col, 1)); p.drawLine(x(i)+int(cw/2), y(hi), x(i)+int(cw/2), y(lo))
            p.fillRect(x(i), min(y(o), y(c)), int(cw), max(1, abs(y(o)-y(c))), col)
        
        p.setPen(Qt.NoPen); p.setBrush(QColor(COLORS["local_max"]))
        for idx in self.local_maxes: p.drawEllipse(x(idx)+int(cw/2)-4, y(float(self.klines[idx].get("high",0)))-12, 8, 8)
        
        if self.entry_price and self.entry_index is not None:
            p.setPen(QPen(QColor(COLORS["entry"]), 2)); p.setBrush(QColor(COLORS["entry"]))
            p.drawEllipse(x(self.entry_index)+int(cw/2)-6, y(self.entry_price)-6, 12, 12)
        
        vols = [float(k.get("volume",0) or k.get("turnover",0) or 0) for k in self.klines]
        if vols:
            maxv, avgv = max(vols) or 1, sum(vols)/len(vols) if vols else 1
            for i, v in enumerate(vols):
                bh = int(v/maxv*(self.volume_h-10)) if maxv else 0
                p.fillRect(x(i), self.height()-mb+10+(self.volume_h-10)-bh, int(cw), bh, QColor(COLORS["volume_high"] if v > avgv*1.5 else COLORS["volume_low"]))

class TimeframeSelector(QWidget):
    timeframe_changed = Signal(str)
    def __init__(self, parent=None):
        super().__init__(parent); self.current = "60"; layout = QHBoxLayout(self); layout.setContentsMargins(0,0,0,0); layout.setSpacing(5)
        self.btns = {}
        for label, tf in [("15м","15"),("1ч","60"),("4ч","240"),("24ч","D"),("7д","W")]:
            btn = QPushButton(label); btn.setCheckable(True); btn.setFixedWidth(50)
            btn.setStyleSheet(f"QPushButton{{background:{COLORS['panel']};border:1px solid {COLORS['border']};color:{COLORS['text']};padding:5px;border-radius:4px;}}QPushButton:checked{{background:{COLORS['blue']};color:#000;font-weight:bold;}}")
            btn.clicked.connect(lambda _, t=tf: self._click(t)); layout.addWidget(btn); self.btns[tf] = btn
        self.btns["60"].setChecked(True); layout.addStretch()
    def _click(self, tf): self.current = tf; [b.setChecked(t==tf) for t,b in self.btns.items()]; self.timeframe_changed.emit(tf)

class ChartWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle("График монеты"); self.resize(1000, 700); self.setMinimumSize(800, 600)
        self.setStyleSheet(f"background-color:{COLORS['bg']};")
        self.symbol, self.row, self.btc_price, self.btc_change, self.klines_cache = "", None, 0, 0, {}
        layout = QVBoxLayout(self); layout.setContentsMargins(10, 10, 10, 10); layout.setSpacing(10)
        header = QHBoxLayout()
        self.lbl_title = QLabel("📊 График"); self.lbl_title.setStyleSheet(f"color:{COLORS['blue']};font-size:18px;font-weight:bold;")
        header.addWidget(self.lbl_title); header.addStretch()
        btn_close = QPushButton("✕"); btn_close.setFixedSize(30,30); btn_close.setStyleSheet(f"QPushButton{{background:{COLORS['red']};color:white;border:none;border-radius:4px;font-size:16px;}}")
        btn_close.clicked.connect(self.close); header.addWidget(btn_close); layout.addLayout(header)
        self.info_panel = InfoPanel(); layout.addWidget(self.info_panel)
        self.tf_selector = TimeframeSelector(); self.tf_selector.timeframe_changed.connect(self._load_chart); layout.addWidget(self.tf_selector)
        self.chart = CandleChartWidget(); layout.addWidget(self.chart, stretch=1)
        self.lbl_status = QLabel("Готово"); self.lbl_status.setStyleSheet(f"color:{COLORS['text_dim']};font-size:11px;"); layout.addWidget(self.lbl_status)
    
    def show_coin(self, row, btc_price=0, btc_change=0, klines=None):
        print(f"[DEBUG-CHART] show_coin: row.symbol={row.symbol}")
        self.row, self.symbol, self.btc_price, self.btc_change = row, row.symbol, btc_price, btc_change
        self.lbl_title.setText(f"📊 {row.symbol.replace('USDT','')}"); self.setWindowTitle(f"График — {row.symbol}")
        print(f"[DEBUG-CHART] Updating info panel...")
        self.info_panel.update_data(row, btc_price, btc_change)
        if klines: self.klines_cache = klines
        print(f"[DEBUG-CHART] Loading chart for tf={self.tf_selector.current}")
        self._load_chart(self.tf_selector.current)
        print(f"[DEBUG-CHART] Showing window...")
        self.show(); self.raise_(); self.activateWindow()
        print(f"[DEBUG-CHART] Window shown")
    
    def _load_chart(self, tf):
        self.lbl_status.setText(f"Загрузка {tf}..."); klines = self.klines_cache.get(tf, [])
        if not klines:
            try:
                from core.bybit_client import get_client; klines = get_client().get_klines(self.symbol, tf, limit=100); self.klines_cache[tf] = klines
            except Exception as e: self.lbl_status.setText(f"Ошибка: {e}"); return
        supports, resistances = self._calc_levels(klines)
        self.chart.set_data(klines, supports, resistances, self.row.entry_price if self.row else None)
        self.lbl_status.setText(f"Загружено {len(klines)} свечей ({tf})")
    
    def _calc_levels(self, klines):
        if not klines or not self.row: return [], []
        price = self.row.price_now; highs, lows = [], []
        for i in range(1, len(klines)-1):
            h = [float(klines[j].get("high",0)) for j in [i-1,i,i+1]]; l = [float(klines[j].get("low",0)) for j in [i-1,i,i+1]]
            if h[1] > h[0] and h[1] > h[2]: highs.append(h[1])
            if l[1] < l[0] and l[1] < l[2]: lows.append(l[1])
        return sorted([l for l in lows if l < price], reverse=True)[:3], sorted([h for h in highs if h > price])[:3]
    
    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape: self.close()
        elif e.key() in [Qt.Key_1,Qt.Key_2,Qt.Key_3,Qt.Key_4,Qt.Key_5]: self.tf_selector._click(["15","60","240","D","W"][e.key()-Qt.Key_1])

_chart_window = None
def show_chart(row, btc_price=0, btc_change=0, klines=None):
    print(f"[DEBUG-CHART] show_chart called")
    print(f"[DEBUG-CHART] row={row}")
    print(f"[DEBUG-CHART] row.symbol={getattr(row, 'symbol', 'NO_SYMBOL')}")
    print(f"[DEBUG-CHART] btc_price={btc_price}, btc_change={btc_change}")
    print(f"[DEBUG-CHART] klines keys={list(klines.keys()) if klines else None}")
    global _chart_window
    try:
        if _chart_window is None:
            print(f"[DEBUG-CHART] Creating new ChartWindow...")
            _chart_window = ChartWindow()
            print(f"[DEBUG-CHART] ChartWindow created: {_chart_window}")
        print(f"[DEBUG-CHART] Calling show_coin...")
        _chart_window.show_coin(row, btc_price, btc_change, klines)
        print(f"[DEBUG-CHART] show_coin completed")
    except Exception as e:
        print(f"[DEBUG-CHART] EXCEPTION in show_chart: {e}")
        import traceback
        traceback.print_exc()
