# -*- coding: utf-8 -*-
"""
collect_logs_for_gpt.py
Creates a zip bundle with logs + key json files for fast debugging.

Run:
  python collect_logs_for_gpt.py

Output:
  logs_export/logs_bundle_YYYYMMDD_HHMMSS.zip
"""
from __future__ import annotations
import os, time, zipfile

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

INCLUDE_FILES = [
    "start.log",
    "app.log",
    "scanner_state.json",
    "bridge_snapshot.json",
    "config.json",
    ".instance.lock",
]

INCLUDE_DIRS = [
    "logs",
]

def add_if_exists(z: zipfile.ZipFile, path: str, arcname: str) -> None:
    if os.path.isfile(path):
        z.write(path, arcname)
    elif os.path.isdir(path):
        for root, _, files in os.walk(path):
            for fn in files:
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, PROJECT_ROOT)
                z.write(full, rel)

def main() -> str:
    out_dir = os.path.join(PROJECT_ROOT, "logs_export")
    os.makedirs(out_dir, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_zip = os.path.join(out_dir, f"logs_bundle_{ts}.zip")
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for f in INCLUDE_FILES:
            add_if_exists(z, os.path.join(PROJECT_ROOT, f), f)
        for d in INCLUDE_DIRS:
            add_if_exists(z, os.path.join(PROJECT_ROOT, d), d)
        # environment snapshot
        env_txt = os.path.join(out_dir, "env.txt")
        with open(env_txt, "w", encoding="utf-8") as f:
            f.write(f"project_root={PROJECT_ROOT}\n")
            f.write(f"cwd={os.getcwd()}\n")
            f.write(f"time={time.ctime()}\n")
            f.write(f"python={os.sys.version}\n")
        z.write(env_txt, "env.txt")
    try:
        os.remove(env_txt)
    except Exception:
        pass
    return out_zip

if __name__ == "__main__":
    zp = main()
    print("OK:", zp)
