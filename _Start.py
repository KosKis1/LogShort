# ===== _Start.py =====
# Запуск сканера напрямую (без меню)
# ==================================

import os
import sys
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    print("=" * 50)
    print("  Bybit SHORT Scanner v3.x")
    print("=" * 50)
    print("\n🚀 Запуск сканера...")
    
    script = os.path.join(BASE_DIR, "main.py")
    subprocess.run([sys.executable, script], cwd=BASE_DIR)
