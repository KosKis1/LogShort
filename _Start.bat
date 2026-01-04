@echo off
chcp 65001 > nul
title Bybit SHORT Scanner v3.0 — MODULAR

REM ==========================================
REM  MODULAR MODE — запуск main.py
REM ==========================================

cd /d %~dp0

echo ==========================================
echo   Bybit SHORT Scanner v3.0
echo   Mode: MODULAR (main.py)
echo ==========================================
echo.

python main.py

echo.
echo ==========================================
echo PROGRAM FINISHED
echo PRESS ANY KEY TO CLOSE
echo ==========================================
pause > nul
