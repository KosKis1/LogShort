# _run_with_debug_logs.py
# Запускает сканер с перенаправлением всех логов в файл
# Использование: python _run_with_debug_logs.py

import sys
import os
import datetime

# Устанавливаем рабочую директорию
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Создаём лог файл с временной меткой
log_filename = f"debug_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), log_filename)

print(f"=== Логи будут записаны в: {log_path} ===")
print("=== Для остановки нажмите Ctrl+C или закройте окно ===")

# Класс для дублирования вывода в файл и консоль
class TeeOutput:
    def __init__(self, filename, mode='w'):
        self.file = open(filename, mode, encoding='utf-8', buffering=1)
        self.stdout = sys.stdout
        self.stderr = sys.stderr
    
    def write(self, data):
        self.file.write(data)
        self.stdout.write(data)
        self.file.flush()
    
    def flush(self):
        self.file.flush()
        self.stdout.flush()

# Перенаправляем stdout и stderr
tee = TeeOutput(log_path)
sys.stdout = tee
sys.stderr = tee

print(f"[DEBUG-LAUNCHER] === Debug session started: {datetime.datetime.now()} ===")
print(f"[DEBUG-LAUNCHER] Log file: {log_path}")
print(f"[DEBUG-LAUNCHER] Python: {sys.executable}")
print(f"[DEBUG-LAUNCHER] Working dir: {os.getcwd()}")
print(f"[DEBUG-LAUNCHER] ==========================================")

# Импортируем и запускаем главный модуль
try:
    # Имя файла с дефисами - используем importlib
    import importlib.util
    spec = importlib.util.spec_from_file_location("scanner", "auto-short_v095_with_trainer_bridge.py")
    scanner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scanner)
    scanner.main()
except Exception as e:
    print(f"[DEBUG-LAUNCHER] FATAL ERROR: {e}")
    import traceback
    traceback.print_exc()
finally:
    print(f"[DEBUG-LAUNCHER] === Session ended: {datetime.datetime.now()} ===")
    tee.file.close()
