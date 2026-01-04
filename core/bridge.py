# ===== core/bridge.py =====
# Мост между Scanner и Trainer (file-based IPC)
# ==============================================

import os
import json
import time
from typing import Dict, List, Optional
from dataclasses import asdict

from core.types import CoinRow


# Пути по умолчанию
DEFAULT_BRIDGE_DIR = r"C:\Pythone\Log_Short"
BRIDGE_FILENAME = "bridge_snapshot.json"


class BridgeWriter:
    """
    Записывает данные для Trainer.
    
    Формат bridge_snapshot.json:
    {
        "ts": 1234567890,
        "bridge_version": "2.0",
        "strategy": "ShortExhaustion",
        "top_n": 30,
        "items": [
            {
                "symbol": "BTCUSDT",
                "status": "Интерес",
                "score": 65.5,
                "watch_type": "Рост/Кор",
                ...
            }
        ]
    }
    """
    
    def __init__(self, bridge_dir: str = DEFAULT_BRIDGE_DIR):
        self.bridge_dir = bridge_dir
        self.bridge_path = os.path.join(bridge_dir, BRIDGE_FILENAME)
    
    def write(
        self, 
        rows: Dict[str, CoinRow], 
        top_n: int = 30,
        strategy_name: str = "ShortExhaustion"
    ) -> bool:
        """
        Записать snapshot для Trainer.
        
        Args:
            rows: Словарь CoinRow по символам
            top_n: Количество топ кандидатов
            strategy_name: Название стратегии
        
        Returns:
            True если успешно
        """
        try:
            os.makedirs(self.bridge_dir, exist_ok=True)
            
            # Собираем и сортируем
            items = []
            for symbol, row in rows.items():
                if not getattr(row, 'valid', True):
                    continue
                items.append(self._row_to_dict(row))
            
            # Сортируем: сначала по статусу, потом по скору
            status_priority = {
                "ВХОД": 0, 
                "Готовность": 1, 
                "Интерес": 2, 
                "Наблюдение": 3, 
                "": 4
            }
            items.sort(key=lambda x: (
                status_priority.get(x.get("status", ""), 99),
                -x.get("score", 0)
            ))
            
            # Берём топ N
            items = items[:top_n]
            
            payload = {
                "ts": int(time.time()),
                "bridge_version": "2.0",
                "strategy": strategy_name,
                "top_n": len(items),
                "items": items
            }
            
            # Атомарная запись
            self._atomic_write(payload)
            return True
            
        except Exception as e:
            self._log_error(f"write error: {e}")
            return False
    
    def _row_to_dict(self, row: CoinRow) -> Dict:
        """Конвертировать CoinRow в словарь для JSON."""
        return {
            "symbol": row.symbol,
            "status": row.status,
            "score": float(row.score),
            "watch_type": row.watch_type,
            "signal": (row.signal or "")[:100],
            
            # Рыночные данные
            "price_now": float(row.price_now),
            "high_24h": float(row.high_24h),
            "low_24h": float(row.low_24h),
            "change_24h_pct": float(row.change_24h_pct),
            "vol24h_m": int(row.vol24_m),
            
            # Позиция
            "range_position": float(row.range_position),
            "dist_high_pct": float(row.dist_high_pct),
            
            # Торговый план
            "entry": float(row.entry_price),
            "sl": float(row.sl_price),
            "tp1": float(row.tp1),
            "tp2": float(row.tp2),
            "rr": float(row.rr),
            
            # Индикаторы
            "short_prob": float(row.short_prob),
            "short_conf": float(row.short_conf),
            "candidate_pct": float(row.candidate_pct),
            
            # Гейты
            "gate0_passed": row.gate0_passed,
            "gate1_passed": row.gate1_passed,
            "gate2_passed": row.gate2_passed,
            "gate3_passed": row.gate3_passed,
            
            "grade": row.grade,
        }
    
    def _atomic_write(self, payload: Dict):
        """Атомарная запись (temp -> rename)."""
        tmp_path = self.bridge_path + ".tmp"
        
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        
        os.replace(tmp_path, self.bridge_path)
        
        # Обновляем mtime для Trainer
        try:
            os.utime(self.bridge_path, None)
        except:
            pass
    
    def _log_error(self, msg: str):
        """Логирование ошибок."""
        try:
            err_path = os.path.join(self.bridge_dir, "bridge_errors.txt")
            with open(err_path, "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
        except:
            pass


class BridgeReader:
    """
    Читает данные из bridge_snapshot.json для Trainer.
    """
    
    def __init__(self, bridge_dir: str = DEFAULT_BRIDGE_DIR):
        self.bridge_dir = bridge_dir
        self.bridge_path = os.path.join(bridge_dir, BRIDGE_FILENAME)
        self.last_mtime_ns: int = 0
    
    def has_update(self) -> bool:
        """Проверить есть ли обновление."""
        try:
            if not os.path.exists(self.bridge_path):
                return False
            st = os.stat(self.bridge_path)
            return st.st_mtime_ns > self.last_mtime_ns
        except:
            return False
    
    def read(self) -> Optional[Dict]:
        """
        Прочитать snapshot.
        
        Returns:
            Словарь с данными или None
        """
        try:
            if not os.path.exists(self.bridge_path):
                return None
            
            st = os.stat(self.bridge_path)
            self.last_mtime_ns = st.st_mtime_ns
            
            with open(self.bridge_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    
    def get_items(self) -> List[Dict]:
        """Получить список items."""
        data = self.read()
        if data:
            return data.get("items", [])
        return []
    
    def get_candidates(self, statuses: tuple = ("Интерес", "Готовность", "ВХОД")) -> List[Dict]:
        """
        Получить кандидатов с нужными статусами.
        """
        items = self.get_items()
        return [x for x in items if x.get("status") in statuses]
    
    def get_age_sec(self) -> float:
        """Возраст snapshot в секундах."""
        data = self.read()
        if data:
            ts = data.get("ts", 0)
            return time.time() - ts
        return float("inf")


# Синглтоны
_writer: Optional[BridgeWriter] = None
_reader: Optional[BridgeReader] = None


def get_bridge_writer(bridge_dir: str = DEFAULT_BRIDGE_DIR) -> BridgeWriter:
    """Получить writer."""
    global _writer
    if _writer is None:
        _writer = BridgeWriter(bridge_dir)
    return _writer


def get_bridge_reader(bridge_dir: str = DEFAULT_BRIDGE_DIR) -> BridgeReader:
    """Получить reader."""
    global _reader
    if _reader is None:
        _reader = BridgeReader(bridge_dir)
    return _reader


# Удобные функции
def write_bridge_snapshot(rows: Dict[str, CoinRow], top_n: int = 30) -> bool:
    """Записать snapshot."""
    return get_bridge_writer().write(rows, top_n)


def read_bridge_items() -> List[Dict]:
    """Прочитать items."""
    return get_bridge_reader().get_items()


def read_bridge_candidates() -> List[Dict]:
    """Прочитать кандидатов."""
    return get_bridge_reader().get_candidates()
