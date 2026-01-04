# _collect_for_claude.py
# Полный сборщик данных для диагностики Claude
# Собирает: логи, историю монет, состояния, конфиги, основные модули
# 
# Запуск: python _collect_for_claude.py
# Результат: __claude_debug_v###.zip
#
# Version: 2.0

import os
import sys
import json
import time
import zipfile
import traceback
from datetime import datetime
from pathlib import Path

# ============================================================
# КОНФИГУРАЦИЯ
# ============================================================

PROJECT_DIR = Path(__file__).parent
LOG_DIR = PROJECT_DIR / "logs"
ML_DATA_DIR = PROJECT_DIR / "ml_data"
CORE_DIR = PROJECT_DIR / "core"
PARAMS_DIR = PROJECT_DIR / "params"

# Максимальные размеры файлов (в байтах)
MAX_LOG_SIZE = 500 * 1024       # 500 KB для логов
MAX_JSONL_LINES = 2000          # последние 2000 строк для .jsonl

# ============================================================
# УТИЛИТЫ
# ============================================================

def safe_read_file(filepath: Path, max_size: int = None) -> str:
    """Безопасно читает файл с ограничением размера."""
    try:
        if not filepath.exists():
            return f"[FILE NOT FOUND: {filepath}]"
        
        size = filepath.stat().st_size
        
        if max_size and size > max_size:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                head = f.read(max_size // 2)
            with open(filepath, 'rb') as f:
                f.seek(-max_size // 2, 2)
                tail = f.read().decode('utf-8', errors='replace')
            return f"{head}\n\n[... TRUNCATED {size - max_size} bytes ...]\n\n{tail}"
        else:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()
    except Exception as e:
        return f"[ERROR READING {filepath}: {e}]"


def safe_read_jsonl_tail(filepath: Path, max_lines: int = 2000) -> list:
    """Читает последние N строк из JSONL файла."""
    try:
        if not filepath.exists():
            return []
        
        lines = []
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                lines.append(line.rstrip())
                if len(lines) > max_lines:
                    lines.pop(0)
        
        result = []
        for line in lines:
            try:
                result.append(json.loads(line))
            except:
                result.append({"_raw": line})
        return result
    except Exception as e:
        return [{"_error": str(e)}]


def get_file_info(filepath: Path) -> dict:
    """Получает информацию о файле."""
    try:
        if not filepath.exists():
            return {"exists": False}
        
        stat = filepath.stat()
        return {
            "exists": True,
            "size_bytes": stat.st_size,
            "size_kb": round(stat.st_size / 1024, 2),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "age_hours": round((time.time() - stat.st_mtime) / 3600, 2)
        }
    except Exception as e:
        return {"exists": False, "error": str(e)}


# ============================================================
# АНАЛИЗАТОРЫ
# ============================================================

def analyze_signals() -> dict:
    """Анализирует signals.jsonl — история всех сигналов."""
    signals_file = ML_DATA_DIR / "signals.jsonl"
    result = {
        "file_info": get_file_info(signals_file),
        "total_records": 0,
        "unique_symbols": [],
        "by_status": {},
        "by_watch_type": {},
        "by_gates": {
            "gate0_passed": 0,
            "gate1_passed": 0,
            "gate2_passed": 0,
            "gate3_passed": 0,
            "all_gates_passed": 0
        },
        "with_entry_price": 0,
        "last_records": [],
        "time_range": {"first": None, "last": None}
    }
    
    if not signals_file.exists():
        return result
    
    try:
        records = safe_read_jsonl_tail(signals_file, MAX_JSONL_LINES)
        result["total_records"] = len(records)
        unique_symbols = set()
        
        for r in records:
            if isinstance(r, dict) and "_error" not in r and "_raw" not in r:
                sym = r.get("symbol", "")
                if sym:
                    unique_symbols.add(sym)
                
                status = r.get("status", "unknown")
                result["by_status"][status] = result["by_status"].get(status, 0) + 1
                
                wtype = r.get("watch_type", "") or "empty"
                result["by_watch_type"][wtype] = result["by_watch_type"].get(wtype, 0) + 1
                
                if r.get("gate0_passed"):
                    result["by_gates"]["gate0_passed"] += 1
                if r.get("gate1_passed"):
                    result["by_gates"]["gate1_passed"] += 1
                if r.get("gate2_passed"):
                    result["by_gates"]["gate2_passed"] += 1
                if r.get("gate3_passed"):
                    result["by_gates"]["gate3_passed"] += 1
                if all([r.get("gate0_passed"), r.get("gate1_passed"), 
                        r.get("gate2_passed"), r.get("gate3_passed")]):
                    result["by_gates"]["all_gates_passed"] += 1
                
                if r.get("entry_price", 0) > 0:
                    result["with_entry_price"] += 1
                
                ts = r.get("ts")
                if ts:
                    if result["time_range"]["first"] is None or ts < result["time_range"]["first"]:
                        result["time_range"]["first"] = ts
                    if result["time_range"]["last"] is None or ts > result["time_range"]["last"]:
                        result["time_range"]["last"] = ts
        
        result["last_records"] = records[-20:]
        result["unique_symbols"] = list(unique_symbols)
        
        if result["time_range"]["first"]:
            result["time_range"]["first_str"] = datetime.fromtimestamp(
                result["time_range"]["first"]).isoformat()
        if result["time_range"]["last"]:
            result["time_range"]["last_str"] = datetime.fromtimestamp(
                result["time_range"]["last"]).isoformat()
            
    except Exception as e:
        result["error"] = str(e)
    
    return result


def analyze_trades() -> dict:
    """Анализирует trades.jsonl — история сделок."""
    trades_file = ML_DATA_DIR / "trades.jsonl"
    result = {
        "file_info": get_file_info(trades_file),
        "total_records": 0,
        "opens": 0,
        "closes": 0,
        "by_exit_reason": {},
        "by_symbol": {},
        "pnl_summary": {
            "total_pnl": 0.0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0
        },
        "last_records": []
    }
    
    if not trades_file.exists():
        return result
    
    try:
        records = safe_read_jsonl_tail(trades_file, MAX_JSONL_LINES)
        result["total_records"] = len(records)
        
        for r in records:
            if isinstance(r, dict) and "_error" not in r:
                action = r.get("action", "")
                
                if action == "OPEN":
                    result["opens"] += 1
                elif action == "CLOSE":
                    result["closes"] += 1
                    reason = r.get("exit_reason", "unknown")
                    result["by_exit_reason"][reason] = result["by_exit_reason"].get(reason, 0) + 1
                    
                    pnl = r.get("profit_usdt", 0)
                    result["pnl_summary"]["total_pnl"] += pnl
                    if pnl > 0:
                        result["pnl_summary"]["wins"] += 1
                    elif pnl < 0:
                        result["pnl_summary"]["losses"] += 1
                
                sym = r.get("symbol", "unknown")
                if sym not in result["by_symbol"]:
                    result["by_symbol"][sym] = {"opens": 0, "closes": 0, "pnl": 0.0}
                if action == "OPEN":
                    result["by_symbol"][sym]["opens"] += 1
                elif action == "CLOSE":
                    result["by_symbol"][sym]["closes"] += 1
                    result["by_symbol"][sym]["pnl"] += r.get("profit_usdt", 0)
        
        total_trades = result["pnl_summary"]["wins"] + result["pnl_summary"]["losses"]
        if total_trades > 0:
            result["pnl_summary"]["win_rate"] = round(
                result["pnl_summary"]["wins"] / total_trades * 100, 2)
        
        result["pnl_summary"]["total_pnl"] = round(result["pnl_summary"]["total_pnl"], 4)
        result["last_records"] = records[-20:]
        
    except Exception as e:
        result["error"] = str(e)
    
    return result


def analyze_bridge_snapshot() -> dict:
    """Анализирует bridge_snapshot.json — текущие данные для trainer."""
    bridge_file = PROJECT_DIR / "bridge_snapshot.json"
    result = {
        "file_info": get_file_info(bridge_file),
        "exists": False,
        "version": None,
        "timestamp": None,
        "age_seconds": None,
        "items_count": 0,
        "by_status": {},
        "items_summary": [],
        "full_content": None
    }
    
    if not bridge_file.exists():
        return result
    
    result["exists"] = True
    
    try:
        with open(bridge_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        result["full_content"] = data
        result["version"] = data.get("bridge_version")
        result["timestamp"] = data.get("ts")
        
        if result["timestamp"]:
            result["age_seconds"] = int(time.time() - result["timestamp"])
            result["timestamp_str"] = datetime.fromtimestamp(result["timestamp"]).isoformat()
        
        items = data.get("items", [])
        result["items_count"] = len(items)
        
        for item in items:
            status = item.get("status", "no_status")
            result["by_status"][status] = result["by_status"].get(status, 0) + 1
            
            result["items_summary"].append({
                "symbol": item.get("symbol"),
                "status": item.get("status"),
                "score": item.get("score"),
                "watch_type": item.get("watch_type"),
                "change_24h": item.get("change_24h_pct"),
                "range_pos": item.get("range_position")
            })
            
    except Exception as e:
        result["error"] = str(e)
    
    return result


def analyze_trainer_state() -> dict:
    """Анализирует trainer_state.json."""
    state_file = PROJECT_DIR / "trainer_state.json"
    result = {"file_info": get_file_info(state_file), "content": None}
    
    if state_file.exists():
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                result["content"] = json.load(f)
        except Exception as e:
            result["error"] = str(e)
    
    return result


def collect_errors() -> dict:
    """Собирает все ошибки."""
    result = {}
    
    for err_name in ["errors.txt", "trainer_errors.txt", "scanner_stderr.txt"]:
        err_path = PROJECT_DIR / err_name
        if err_path.exists():
            result[err_name] = safe_read_file(err_path, MAX_LOG_SIZE)
    
    return result


# ============================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================

def main():
    print("=" * 60)
    print("COLLECT FOR CLAUDE — Full Debug Package")
    print("=" * 60)
    
    # Версия архива
    existing = list(PROJECT_DIR.glob("__claude_debug_v*.zip"))
    version = 1
    if existing:
        nums = []
        for f in existing:
            try:
                num = int(f.stem.replace("__claude_debug_v", ""))
                nums.append(num)
            except:
                pass
        version = max(nums, default=0) + 1
    
    zip_name = f"__claude_debug_v{version:03d}.zip"
    zip_path = PROJECT_DIR / zip_name
    
    print(f"\nProject: {PROJECT_DIR}")
    print(f"Output: {zip_name}\n")
    
    # ===== СБОР ДАННЫХ =====
    
    print("[1/6] Analyzing signals...")
    signals = analyze_signals()
    print(f"       Records: {signals['total_records']}, Status: {signals['by_status']}")
    
    print("[2/6] Analyzing trades...")
    trades = analyze_trades()
    print(f"       Opens: {trades['opens']}, Closes: {trades['closes']}, "
          f"PnL: {trades['pnl_summary']['total_pnl']:.2f}$")
    
    print("[3/6] Analyzing bridge_snapshot...")
    bridge = analyze_bridge_snapshot()
    print(f"       Exists: {bridge['exists']}, Items: {bridge['items_count']}, "
          f"Age: {bridge.get('age_seconds', 'N/A')}s")
    
    print("[4/6] Analyzing trainer_state...")
    trainer_state = analyze_trainer_state()
    
    print("[5/6] Collecting errors...")
    errors = collect_errors()
    
    print("[6/6] Building archive...")
    
    # ===== ОТЧЁТ =====
    
    report = {
        "meta": {
            "collected_at": datetime.now().isoformat(),
            "project_dir": str(PROJECT_DIR),
            "python": sys.version.split()[0],
        },
        "summary": {
            "signals_total": signals['total_records'],
            "signals_by_status": signals['by_status'],
            "signals_gates_all_passed": signals['by_gates']['all_gates_passed'],
            "trades_opens": trades['opens'],
            "trades_closes": trades['closes'],
            "trades_pnl": trades['pnl_summary']['total_pnl'],
            "bridge_exists": bridge['exists'],
            "bridge_items": bridge['items_count'],
            "bridge_by_status": bridge['by_status'],
        },
        "signals_analysis": signals,
        "trades_analysis": trades,
        "bridge_snapshot": bridge,
        "trainer_state": trainer_state,
        "errors": errors,
    }
    
    # ===== АРХИВ =====
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        
        # Отчёт
        zf.writestr("__REPORT.json", json.dumps(report, indent=2, ensure_ascii=False, default=str))
        
        # Основные модули
        for fname in ["auto-short_v095_with_trainer_bridge.py", "trainer_live.py", "_Start.py"]:
            fpath = PROJECT_DIR / fname
            if fpath.exists():
                zf.write(fpath, f"modules/{fname}")
        
        # Core модули
        if CORE_DIR.exists():
            for f in CORE_DIR.glob("*.py"):
                zf.write(f, f"modules/core/{f.name}")
        
        # Params
        if PARAMS_DIR.exists():
            for f in PARAMS_DIR.glob("*.json"):
                zf.write(f, f"params/{f.name}")
        
        # ML Data
        signals_file = ML_DATA_DIR / "signals.jsonl"
        if signals_file.exists() and signals_file.stat().st_size < 2 * 1024 * 1024:
            zf.write(signals_file, "ml_data/signals.jsonl")
        
        trades_file = ML_DATA_DIR / "trades.jsonl"
        if trades_file.exists():
            zf.write(trades_file, "ml_data/trades.jsonl")
        
        # Bridge
        bridge_file = PROJECT_DIR / "bridge_snapshot.json"
        if bridge_file.exists():
            zf.write(bridge_file, "bridge_snapshot.json")
        
        # States
        for name in ["app_state.json", "trainer_state.json"]:
            for loc in [PROJECT_DIR, LOG_DIR]:
                fpath = loc / name
                if fpath.exists():
                    zf.write(fpath, f"states/{name}")
                    break
        
        # Errors
        for name in ["errors.txt", "trainer_errors.txt"]:
            fpath = PROJECT_DIR / name
            if fpath.exists():
                zf.write(fpath, f"errors/{name}")
        
        # Logs
        if LOG_DIR.exists():
            for f in LOG_DIR.iterdir():
                if f.is_file() and f.suffix in ('.log', '.txt'):
                    zf.write(f, f"logs/{f.name}")
        
        # Root logs
        for name in ["trainer_trace.txt", "app.log"]:
            fpath = PROJECT_DIR / name
            if fpath.exists():
                zf.write(fpath, f"logs/{name}")
        
        # Config
        config = PROJECT_DIR / "config.json"
        if config.exists():
            zf.write(config, "config.json")
    
    # ===== ИТОГИ =====
    
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Signals: {signals['total_records']} | Status: {signals['by_status']}")
    print(f"Gates all passed: {signals['by_gates']['all_gates_passed']}")
    print(f"Trades: {trades['opens']} opens, {trades['closes']} closes")
    print(f"PnL: {trades['pnl_summary']['total_pnl']:.2f}$ | "
          f"Win rate: {trades['pnl_summary']['win_rate']}%")
    print(f"Bridge: {'OK' if bridge['exists'] else 'NOT FOUND'} | "
          f"Items: {bridge['items_count']} | Status: {bridge['by_status']}")
    print()
    print("=" * 60)
    print(f"DONE: {zip_name} ({zip_path.stat().st_size / 1024:.1f} KB)")
    print("=" * 60)
    print(f"\n>>> Отправь Claude: {zip_name}\n")
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\nERROR: {e}")
        traceback.print_exc()
        sys.exit(1)
