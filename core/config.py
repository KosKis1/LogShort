# ===== core/config.py =====
# Конфигурация приложения
# ========================

import os
import json
from typing import Optional
from dataclasses import dataclass, asdict


# Базовая директория
BASE_DIR = r"C:\Pythone\Log_Short"


@dataclass
class AppConfig:
    """Конфигурация приложения."""
    
    # Пути
    base_dir: str = BASE_DIR
    logs_dir: str = ""
    ml_data_dir: str = ""
    
    # Сканер
    universe_size: int = 200
    auto_recalc_minutes: int = 10
    page_size: int = 25
    max_workers: int = 8
    
    # Trainer
    trade_amount: float = 100.0
    initial_balance: float = 1000.0
    max_positions: int = 3
    
    # Risk Management
    sl_pct: float = 2.5
    tp1_pct: float = 1.5
    tp2_pct: float = 3.0
    timeout_hours: int = 4
    min_leverage: float = 5.0
    max_leverage: float = 20.0
    
    # Entry filters
    entry_statuses: tuple = ("Интерес", "Готовность", "ВХОД")
    min_score: float = 50.0
    min_volume_m: int = 3
    
    # Telegram
    tg_enabled: bool = False
    tg_token: str = ""
    tg_chat_id: int = 0
    tg_thread_id: Optional[int] = None
    
    def __post_init__(self):
        if not self.logs_dir:
            self.logs_dir = os.path.join(self.base_dir, "logs")
        if not self.ml_data_dir:
            self.ml_data_dir = os.path.join(self.base_dir, "ml_data")
    
    def save(self, path: Optional[str] = None):
        """Сохранить конфигурацию."""
        if path is None:
            path = os.path.join(self.base_dir, "config.json")
        
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        data = asdict(self)
        # tuple -> list для JSON
        data["entry_statuses"] = list(data["entry_statuses"])
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load(cls, path: Optional[str] = None) -> "AppConfig":
        """Загрузить конфигурацию."""
        if path is None:
            path = os.path.join(BASE_DIR, "config.json")
        
        if not os.path.exists(path):
            return cls()
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # list -> tuple
            if "entry_statuses" in data:
                data["entry_statuses"] = tuple(data["entry_statuses"])
            
            return cls(**data)
        except:
            return cls()


# Singleton
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """Получить конфигурацию."""
    global _config
    if _config is None:
        _config = AppConfig.load()
    return _config


def set_config(config: AppConfig):
    """Установить конфигурацию."""
    global _config
    _config = config


def reload_config():
    """Перезагрузить конфигурацию."""
    global _config
    _config = AppConfig.load()
