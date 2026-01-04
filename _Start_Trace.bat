@echo off
chcp 65001 > nul
title SHORT PROJECT — TRACE MODE

REM ==========================================
REM  TRACE / DEBUG MODE
REM ==========================================

set DEBUG_TRACE=1
set TRACE_LEVEL=5

cd /d %~dp0

echo ==========================================
echo START SHORT PROJECT
echo MODE: TRACE
echo DEBUG_TRACE=1
echo TRACE_LEVEL=5
echo ==========================================

python auto-short_v095_with_trainer_bridge.py

echo.
echo ==========================================
echo PROGRAM STOPPED OR ERROR OCCURRED
echo CHECK logs\trace.log AND errors.txt
echo PRESS ANY KEY TO CLOSE
echo ==========================================
pause > nul
