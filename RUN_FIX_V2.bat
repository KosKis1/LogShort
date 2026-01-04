@echo off
cd /d "%~dp0"
echo ============================================================
echo FIX V2 PATCH
echo ============================================================
echo.

"C:\Pythone\python.exe" fix_v2_patch.py

echo.
echo ============================================================
echo Now run scanner via _Start.bat
echo ============================================================
echo.
pause
