# ============================================================
# COLLECT LOGS V2 - Сборщик логов для отладки
# ============================================================
# Версия: v2.0
# Дата: 02.01.2025
# ============================================================

"""
СБОРЩИК ЛОГОВ
=============

Собирает все логи и состояние системы в один ZIP-архив для отладки.

Использование:
    python collect_logs_v2.py

Создаёт файл: logs_debug_YYYYMMDD_HHMMSS.zip
"""

import os
import sys
import json
import time
import zipfile
import traceback
from datetime import datetime
from typing import List, Dict, Optional

# Базовая директория проекта
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = BASE_DIR
OUTPUT_DIR = os.path.join(BASE_DIR, "logs_export")


def collect_logs() -> str:
    """
    Собирает все логи и создаёт ZIP-архив.
    Возвращает путь к созданному архиву.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"logs_debug_{timestamp}.zip"
    archive_path = os.path.join(OUTPUT_DIR, archive_name)
    
    # Создаём папку для экспорта
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print(f"🔄 Сбор логов...")
    print(f"📁 Базовая директория: {BASE_DIR}")
    
    files_to_collect = []
    
    # 1. Основные лог-файлы
    log_files = [
        "errors.txt",
        "app.log",
        "trainer_trace.txt",
        "trainer_errors.txt",
        "trades_log.txt",
        "trainer_decisions.jsonl",
    ]
    
    for f in log_files:
        path = os.path.join(BASE_DIR, f)
        if os.path.exists(path):
            files_to_collect.append((path, f"logs/{f}"))
            print(f"  ✅ {f}")
        else:
            print(f"  ⚠️ {f} - не найден")
    
    # 2. Файлы состояния (JSON)
    state_files = [
        "bridge_snapshot.json",
        "trainer_state.json",
        "app_state.json",
        "scanner_state.json",
        "config.json",
    ]
    
    for f in state_files:
        path = os.path.join(BASE_DIR, f)
        if os.path.exists(path):
            files_to_collect.append((path, f"state/{f}"))
            print(f"  ✅ {f}")
        else:
            print(f"  ⚠️ {f} - не найден")
    
    # 3. Логи из папки logs/
    logs_dir = os.path.join(BASE_DIR, "logs")
    if os.path.exists(logs_dir):
        for f in os.listdir(logs_dir):
            if f.startswith("."):
                continue
            path = os.path.join(logs_dir, f)
            if os.path.isfile(path):
                files_to_collect.append((path, f"logs/{f}"))
                print(f"  ✅ logs/{f}")
    
    # 4. ML данные (последние 1000 строк)
    ml_files = [
        ("ml_data/signals.jsonl", 1000),
        ("ml_data/trades.jsonl", 500),
    ]
    
    for rel_path, max_lines in ml_files:
        path = os.path.join(BASE_DIR, rel_path)
        if os.path.exists(path):
            # Читаем последние N строк
            try:
                with open(path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    tail = lines[-max_lines:] if len(lines) > max_lines else lines
                
                # Сохраняем во временный файл
                temp_name = rel_path.replace("/", "_") + f".last{max_lines}"
                temp_path = os.path.join(OUTPUT_DIR, temp_name)
                with open(temp_path, "w", encoding="utf-8") as f:
                    f.writelines(tail)
                
                files_to_collect.append((temp_path, f"ml/{temp_name}"))
                print(f"  ✅ {rel_path} (последние {max_lines} строк)")
            except Exception as e:
                print(f"  ❌ {rel_path}: {e}")
    
    # 5. Конфигурация
    config_files = [
        "core/config.py",
        "core/config_v2.py",
        "core/params.py",
        "params/DEFAULT.json",
    ]
    
    for f in config_files:
        path = os.path.join(BASE_DIR, f)
        if os.path.exists(path):
            files_to_collect.append((path, f"config/{os.path.basename(f)}"))
            print(f"  ✅ {f}")
    
    # 6. Системная информация
    sys_info = collect_system_info()
    sys_info_path = os.path.join(OUTPUT_DIR, "system_info.json")
    with open(sys_info_path, "w", encoding="utf-8") as f:
        json.dump(sys_info, f, indent=2, ensure_ascii=False)
    files_to_collect.append((sys_info_path, "system_info.json"))
    print(f"  ✅ system_info.json")
    
    # 7. Создаём ZIP-архив
    print(f"\n📦 Создание архива: {archive_name}")
    
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for src_path, arc_name in files_to_collect:
            try:
                zf.write(src_path, arc_name)
            except Exception as e:
                print(f"  ❌ Ошибка при добавлении {arc_name}: {e}")
    
    # 8. Очистка временных файлов
    for src_path, arc_name in files_to_collect:
        if src_path.startswith(OUTPUT_DIR) and "last" in src_path:
            try:
                os.remove(src_path)
            except:
                pass
    
    try:
        os.remove(sys_info_path)
    except:
        pass
    
    archive_size = os.path.getsize(archive_path)
    print(f"\n✅ Архив создан: {archive_path}")
    print(f"📊 Размер: {archive_size / 1024:.1f} KB")
    print(f"📁 Файлов собрано: {len(files_to_collect)}")
    
    return archive_path


def collect_system_info() -> Dict:
    """Собирает информацию о системе."""
    info = {
        "timestamp": datetime.now().isoformat(),
        "python_version": sys.version,
        "platform": sys.platform,
        "cwd": os.getcwd(),
        "base_dir": BASE_DIR,
    }
    
    # Версия проекта (из README или TZ)
    try:
        tz_path = os.path.join(BASE_DIR, "TZ_FULL_v309.txt")
        if os.path.exists(tz_path):
            with open(tz_path, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
                info["project_version"] = first_line[:100]
    except:
        pass
    
    # Размеры файлов состояния
    state_files = ["bridge_snapshot.json", "trainer_state.json"]
    for f in state_files:
        path = os.path.join(BASE_DIR, f)
        if os.path.exists(path):
            info[f"{f}_size"] = os.path.getsize(path)
            info[f"{f}_mtime"] = datetime.fromtimestamp(
                os.path.getmtime(path)
            ).isoformat()
    
    # Последние ошибки
    errors_path = os.path.join(BASE_DIR, "errors.txt")
    if os.path.exists(errors_path):
        try:
            with open(errors_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                info["errors_count"] = len([l for l in lines if l.startswith("=")])
                info["last_error_line"] = lines[-1].strip() if lines else ""
        except:
            pass
    
    return info


def main():
    """Главная функция."""
    print("=" * 60)
    print("📋 СБОРЩИК ЛОГОВ v2.0")
    print("=" * 60)
    print()
    
    try:
        archive_path = collect_logs()
        
        print()
        print("=" * 60)
        print("✅ ГОТОВО!")
        print(f"📦 Архив: {archive_path}")
        print()
        print("Отправьте этот файл для анализа.")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
