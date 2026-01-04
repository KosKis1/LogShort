# _collect_debug.py
# Сборщик логов и данных для диагностики
# Запуск: python _collect_debug.py
# Результат: __debug_v###.zip

import os
import sys
import json
import time
import zipfile
from datetime import datetime
from pathlib import Path

# Директория проекта
PROJECT_DIR = Path(__file__).parent
LOG_DIR = PROJECT_DIR / "logs"
ML_DATA_DIR = PROJECT_DIR / "ml_data"

# Версия сборщика
VERSION = 1


def get_next_version() -> int:
    """Находит следующий номер версии архива."""
    existing = list(PROJECT_DIR.glob("__debug_v*.zip"))
    if not existing:
        return 1
    nums = []
    for f in existing:
        try:
            num = int(f.stem.replace("__debug_v", ""))
            nums.append(num)
        except ValueError:
            pass
    return max(nums, default=0) + 1


def collect_file_info() -> dict:
    """Собирает информацию о файлах проекта."""
    info = {
        "collected_at": datetime.now().isoformat(),
        "project_dir": str(PROJECT_DIR),
        "files": {},
        "errors": []
    }
    
    # Основные файлы
    main_files = [
        "auto-short_v095_with_trainer_bridge.py",
        "trainer_live.py",
        "_Start.py",
        "config.json",
    ]
    
    for fname in main_files:
        fpath = PROJECT_DIR / fname
        if fpath.exists():
            info["files"][fname] = {
                "size": fpath.stat().st_size,
                "mtime": datetime.fromtimestamp(fpath.stat().st_mtime).isoformat()
            }
    
    # Core модули
    core_dir = PROJECT_DIR / "core"
    if core_dir.exists():
        for f in core_dir.glob("*.py"):
            key = f"core/{f.name}"
            info["files"][key] = {
                "size": f.stat().st_size,
                "mtime": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
            }
    
    return info


def collect_logs() -> list:
    """Собирает пути к файлам логов."""
    log_files = []
    
    # logs/
    if LOG_DIR.exists():
        for f in LOG_DIR.iterdir():
            if f.is_file() and f.suffix in ('.log', '.txt', '.json'):
                log_files.append(f)
    
    # Корневые логи и состояния
    root_logs = [
        "app.log",
        "bridge_snapshot.json",
        "trainer_state.json",
        "trainer_trace.txt",
        "trainer_errors.txt",
        "trainer_decisions.jsonl",
        "errors.txt",
    ]
    
    for fname in root_logs:
        fpath = PROJECT_DIR / fname
        if fpath.exists():
            log_files.append(fpath)
    
    return log_files


def collect_ml_data() -> list:
    """Собирает ML данные."""
    ml_files = []
    
    if ML_DATA_DIR.exists():
        for f in ML_DATA_DIR.iterdir():
            if f.is_file() and f.suffix in ('.jsonl', '.json', '.csv'):
                ml_files.append(f)
    
    return ml_files


def get_last_n_lines(filepath: Path, n: int = 500) -> str:
    """Читает последние N строк файла."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
            return ''.join(lines[-n:])
    except Exception as e:
        return f"ERROR reading file: {e}"


def analyze_signals() -> dict:
    """Анализирует signals.jsonl."""
    signals_file = ML_DATA_DIR / "signals.jsonl"
    result = {
        "total": 0,
        "by_status": {},
        "by_watch_type": {},
        "last_10": [],
        "errors": []
    }
    
    if not signals_file.exists():
        result["errors"].append("signals.jsonl not found")
        return result
    
    try:
        with open(signals_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        result["total"] = len(lines)
        
        for line in lines:
            try:
                data = json.loads(line)
                
                status = data.get("status", "unknown")
                result["by_status"][status] = result["by_status"].get(status, 0) + 1
                
                wtype = data.get("watch_type", "unknown")
                result["by_watch_type"][wtype] = result["by_watch_type"].get(wtype, 0) + 1
                
            except json.JSONDecodeError:
                result["errors"].append(f"Invalid JSON line")
        
        # Последние 10 записей
        for line in lines[-10:]:
            try:
                result["last_10"].append(json.loads(line))
            except:
                pass
                
    except Exception as e:
        result["errors"].append(str(e))
    
    return result


def analyze_trades() -> dict:
    """Анализирует trades.jsonl."""
    trades_file = ML_DATA_DIR / "trades.jsonl"
    result = {
        "total": 0,
        "opens": 0,
        "closes": 0,
        "by_reason": {},
        "total_pnl": 0.0,
        "wins": 0,
        "losses": 0,
        "last_10": [],
        "errors": []
    }
    
    if not trades_file.exists():
        result["errors"].append("trades.jsonl not found")
        return result
    
    try:
        with open(trades_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        result["total"] = len(lines)
        
        for line in lines:
            try:
                data = json.loads(line)
                action = data.get("action", "")
                
                if action == "OPEN":
                    result["opens"] += 1
                elif action == "CLOSE":
                    result["closes"] += 1
                    reason = data.get("exit_reason", "unknown")
                    result["by_reason"][reason] = result["by_reason"].get(reason, 0) + 1
                    
                    pnl = data.get("profit_usdt", 0)
                    result["total_pnl"] += pnl
                    if pnl > 0:
                        result["wins"] += 1
                    elif pnl < 0:
                        result["losses"] += 1
                        
            except json.JSONDecodeError:
                pass
        
        # Последние 10 записей
        for line in lines[-10:]:
            try:
                result["last_10"].append(json.loads(line))
            except:
                pass
                
    except Exception as e:
        result["errors"].append(str(e))
    
    return result


def analyze_trainer_decisions() -> dict:
    """Анализирует trainer_decisions.jsonl."""
    decisions_file = PROJECT_DIR / "trainer_decisions.jsonl"
    result = {
        "total": 0,
        "by_action": {},
        "last_10": [],
        "errors": []
    }
    
    if not decisions_file.exists():
        result["errors"].append("trainer_decisions.jsonl not found")
        return result
    
    try:
        with open(decisions_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        result["total"] = len(lines)
        
        for line in lines:
            try:
                data = json.loads(line)
                action = data.get("action", "unknown")
                result["by_action"][action] = result["by_action"].get(action, 0) + 1
            except json.JSONDecodeError:
                pass
        
        # Последние 10 записей
        for line in lines[-10:]:
            try:
                result["last_10"].append(json.loads(line))
            except:
                pass
                
    except Exception as e:
        result["errors"].append(str(e))
    
    return result


def check_bridge_snapshot() -> dict:
    """Проверяет bridge_snapshot.json."""
    bridge_file = PROJECT_DIR / "bridge_snapshot.json"
    result = {
        "exists": False,
        "ts": None,
        "age_sec": None,
        "items_count": 0,
        "items_with_status": {},
        "sample_items": [],
        "errors": []
    }
    
    if not bridge_file.exists():
        result["errors"].append("bridge_snapshot.json not found")
        return result
    
    result["exists"] = True
    
    try:
        with open(bridge_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        result["ts"] = data.get("ts")
        if result["ts"]:
            result["age_sec"] = int(time.time() - result["ts"])
        
        items = data.get("items", [])
        result["items_count"] = len(items)
        
        for item in items:
            status = item.get("status", "no_status")
            result["items_with_status"][status] = result["items_with_status"].get(status, 0) + 1
        
        # Первые 5 items
        result["sample_items"] = items[:5]
        
    except Exception as e:
        result["errors"].append(str(e))
    
    return result


def main():
    print("=" * 50)
    print("DEBUG COLLECTOR")
    print("=" * 50)
    
    version = get_next_version()
    zip_name = f"__debug_v{version:03d}.zip"
    zip_path = PROJECT_DIR / zip_name
    
    print(f"\nCollecting data for: {zip_name}")
    
    # Собираем анализ
    analysis = {
        "version": version,
        "collected_at": datetime.now().isoformat(),
        "file_info": collect_file_info(),
        "signals_analysis": analyze_signals(),
        "trades_analysis": analyze_trades(),
        "decisions_analysis": analyze_trainer_decisions(),
        "bridge_snapshot": check_bridge_snapshot(),
    }
    
    # Сохраняем анализ
    analysis_file = PROJECT_DIR / "__debug_analysis.json"
    with open(analysis_file, 'w', encoding='utf-8') as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\nAnalysis saved to: {analysis_file.name}")
    
    # Выводим краткую сводку
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    
    sig = analysis["signals_analysis"]
    print(f"\nSignals: {sig['total']} total")
    print(f"  By status: {sig['by_status']}")
    
    tr = analysis["trades_analysis"]
    print(f"\nTrades: {tr['total']} total ({tr['opens']} opens, {tr['closes']} closes)")
    print(f"  Wins: {tr['wins']}, Losses: {tr['losses']}")
    print(f"  Total PnL: {tr['total_pnl']:.2f}$")
    print(f"  By reason: {tr['by_reason']}")
    
    dec = analysis["decisions_analysis"]
    print(f"\nTrainer decisions: {dec['total']} total")
    print(f"  By action: {dec['by_action']}")
    
    br = analysis["bridge_snapshot"]
    print(f"\nBridge snapshot: {'OK' if br['exists'] else 'NOT FOUND'}")
    if br['exists']:
        print(f"  Items: {br['items_count']}, Age: {br['age_sec']}s")
        print(f"  By status: {br['items_with_status']}")
    
    # Создаём архив
    print(f"\n\nCreating archive: {zip_name}")
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Анализ
        zf.write(analysis_file, "__debug_analysis.json")
        
        # Основные модули (только .py, не .pyc)
        main_files = [
            "auto-short_v095_with_trainer_bridge.py",
            "trainer_live.py",
            "_Start.py",
        ]
        for fname in main_files:
            fpath = PROJECT_DIR / fname
            if fpath.exists():
                zf.write(fpath, fname)
                print(f"  + {fname}")
        
        # Core модули
        core_dir = PROJECT_DIR / "core"
        if core_dir.exists():
            for f in core_dir.glob("*.py"):
                zf.write(f, f"core/{f.name}")
                print(f"  + core/{f.name}")
        
        # Логи
        log_files = collect_logs()
        for lf in log_files:
            rel_path = lf.relative_to(PROJECT_DIR)
            zf.write(lf, str(rel_path))
            print(f"  + {rel_path}")
        
        # ML данные
        ml_files = collect_ml_data()
        for mf in ml_files:
            rel_path = mf.relative_to(PROJECT_DIR)
            zf.write(mf, str(rel_path))
            print(f"  + {rel_path}")
        
        # params/
        params_dir = PROJECT_DIR / "params"
        if params_dir.exists():
            for f in params_dir.glob("*.json"):
                zf.write(f, f"params/{f.name}")
                print(f"  + params/{f.name}")
    
    # Удаляем временный файл анализа
    analysis_file.unlink()
    
    print(f"\n{'=' * 50}")
    print(f"DONE: {zip_name} ({zip_path.stat().st_size / 1024:.1f} KB)")
    print(f"{'=' * 50}")
    print(f"\nОтправь этот файл для диагностики: {zip_name}")
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
