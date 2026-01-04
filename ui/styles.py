# ===== ui/styles.py =====
# Стили интерфейса Full HD
# =========================

MAIN_STYLE = """
QWidget { 
    background-color: #0f0f1a; 
    color: #e6e6e6; 
    font-family: 'Segoe UI', Arial, sans-serif;
}
QTableWidget { 
    background-color: #0a0a15; 
    gridline-color: #2a2a3a; 
    border: 1px solid #2a2a3a;
    border-radius: 4px;
    font-size: 13px;
}
QHeaderView::section { 
    background-color: #1a1a2e; 
    color: #00d4ff;
    padding: 8px; 
    border: none;
    border-bottom: 2px solid #00d4ff;
    font-weight: bold;
}
QPushButton { 
    background-color: #1a1a2e; 
    border: 1px solid #3a3a5a; 
    padding: 8px 14px; 
    border-radius: 4px;
}
QPushButton:checked { background-color: #2a2a4e; border-color: #00d4ff; }
QPushButton:hover { background-color: #2a2a4e; }
QLabel { font-size: 13px; }
QTableWidget::item:selected { background: #2a2a4e; color: #fff; }
"""

TABLE_TOP200_STYLE = """
QTableWidget { background-color: #0a0a15; color: #fff; gridline-color: #2a2a3a; font-size: 13px; }
QHeaderView::section { background-color: #1a1a2e; color: #00d4ff; padding: 8px; border: none; font-weight: bold; }
"""

TABLE_CANDIDATES_STYLE = """
QTableWidget { background-color: #0a0a15; color: #fff; gridline-color: #2a2a3a; font-size: 13px; }
QHeaderView::section { background-color: #1a1a2e; color: #ffd700; padding: 8px; border: none; font-weight: bold; }
"""

TABLE_POSITIONS_STYLE = """
QTableWidget { background-color: #0f0f23; color: white; gridline-color: #333; font-size: 13px; }
QHeaderView::section { background-color: #1a1a3e; color: #00d4ff; padding: 8px; border: none; font-weight: bold; }
"""

TABLE_HISTORY_STYLE = """
QTableWidget { background-color: #0f0f23; color: white; gridline-color: #333; font-size: 12px; }
QHeaderView::section { background-color: #1a1a3e; color: #ffd700; padding: 6px; border: none; font-weight: bold; }
"""

BTN_EXIT_STYLE = "QPushButton { background-color: #8b0000; color: white; font-weight: bold; padding: 8px 20px; border-radius: 4px; }"
BTN_RESET_STYLE = "QPushButton { background-color: #e74c3c; color: white; border: none; padding: 8px 16px; border-radius: 5px; font-weight: bold; }"

STATUS_COLORS = {"ВХОД": "#ff4444", "Готовность": "#ffaa00", "Интерес": "#00aaff", "Наблюдение": "#888888"}

SCANNER_SIZE = (1920, 1040)
TRAINER_SIZE = (1920, 1000)
ROW_HEIGHT = 28
