# ===== ui/dialogs.py =====
# Диалоговые окна
# ================

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton


class CountdownDialog(QDialog):
    """Диалог обратного отсчёта перед авто-сканированием."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Авто-пересчёт")
        self.setFixedSize(300, 120)
        self.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint)
        
        layout = QVBoxLayout(self)
        
        self.label = QLabel("Пересчёт через: --")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("font-size: 18px; font-weight: bold; color: #00d4ff;")
        layout.addWidget(self.label)
        
        self.btn_cancel = QPushButton("Отмена (ESC)")
        self.btn_cancel.setStyleSheet("padding: 10px; font-size: 14px;")
        self.btn_cancel.clicked.connect(self.reject)
        layout.addWidget(self.btn_cancel)
    
    def set_seconds(self, sec: int):
        """Обновить отображение."""
        self.label.setText(f"Пересчёт через: {sec} сек")
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)


class ConfirmDialog(QDialog):
    """Диалог подтверждения."""
    
    def __init__(self, title: str, message: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(350, 150)
        
        layout = QVBoxLayout(self)
        
        label = QLabel(message)
        label.setAlignment(Qt.AlignCenter)
        label.setWordWrap(True)
        label.setStyleSheet("font-size: 14px; padding: 10px;")
        layout.addWidget(label)
        
        btn_layout = QVBoxLayout()
        
        btn_yes = QPushButton("Да")
        btn_yes.setStyleSheet("background-color: #27ae60; color: white; padding: 10px;")
        btn_yes.clicked.connect(self.accept)
        btn_layout.addWidget(btn_yes)
        
        btn_no = QPushButton("Нет")
        btn_no.setStyleSheet("background-color: #e74c3c; color: white; padding: 10px;")
        btn_no.clicked.connect(self.reject)
        btn_layout.addWidget(btn_no)
        
        layout.addLayout(btn_layout)


class ErrorDialog(QDialog):
    """Диалог ошибки."""
    
    def __init__(self, title: str, error_text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(400, 200)
        
        layout = QVBoxLayout(self)
        
        label = QLabel(error_text)
        label.setAlignment(Qt.AlignCenter)
        label.setWordWrap(True)
        label.setStyleSheet("font-size: 13px; color: #ff6b6b; padding: 15px;")
        layout.addWidget(label)
        
        btn_ok = QPushButton("OK")
        btn_ok.setStyleSheet("padding: 10px;")
        btn_ok.clicked.connect(self.accept)
        layout.addWidget(btn_ok)
