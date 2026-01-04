@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion
title Bybit SHORT Scanner v3.0 — MODULAR

REM ==========================================
REM  MODULAR MODE — запуск main.py
REM  + Подхват ключей из .env (без хранения в репозитории)
REM
REM  Варианты расположения .env:
REM   1) .env в корне проекта (рядом с _Start.bat)
REM   2) keys\.env или secrets\.env в корне проекта
REM   3) Внешний .env по пути из файла _keys_path.txt (1 строка = полный путь)
REM      пример содержимого _keys_path.txt:
REM      C:\Pythone\secrets\LogShort.env
REM
REM  Формат .env:
REM    BYBIT_API_KEY=xxxx
REM    BYBIT_API_SECRET=yyyy
REM    TELEGRAM_TOKEN=zzzz
REM ==========================================

cd /d "%~dp0"

echo ==========================================
echo   Bybit SHORT Scanner v3.0
echo   Mode: MODULAR (main.py)
echo ==========================================
echo.

REM --- Detect .env file path ---
set "ENV_FILE="

if exist "_keys_path.txt" (
  for /f "usebackq delims=" %%A in ("_keys_path.txt") do (
    set "ENV_FILE=%%A"
    goto :ENV_FOUND
  )
)

:ENV_FOUND
if not defined ENV_FILE (
  if exist ".env" set "ENV_FILE=%CD%\.env"
  if not defined ENV_FILE if exist "keys\.env" set "ENV_FILE=%CD%\keys\.env"
  if not defined ENV_FILE if exist "secrets\.env" set "ENV_FILE=%CD%\secrets\.env"
)

REM --- Load KEY=VALUE pairs into environment (no printing of values) ---
if defined ENV_FILE (
  if exist "%ENV_FILE%" (
    echo [OK] Loading keys from: "%ENV_FILE%"
    for /f "usebackq tokens=1,* delims==" %%K in ("%ENV_FILE%") do (
      set "k=%%K"
      set "v=%%L"
      REM skip empty keys
      if not "!k!"=="" (
        REM skip comments
        if "!k:~0,1!" NEQ "#" (
          REM trim spaces
          for /f "tokens=* delims= " %%a in ("!k!") do set "k=%%a"
          for /f "tokens=* delims= " %%a in ("!v!") do set "v=%%a"
          REM remove surrounding quotes if present
          if defined v (
            if "!v:~0,1!"=="\"" if "!v:~-1!"=="\"" set "v=!v:~1,-1!"
          )
          set "!k!=!v!"
        )
      )
    )
  ) else (
    echo [WARN] ENV file path specified but not found: "%ENV_FILE%"
  )
) else (
  echo [WARN] Keys file (.env) not found.
  echo        Create .env in project root OR create _keys_path.txt with full path to .env
)

REM --- Optional: activate venv if you use it ---
if exist ".venv\Scripts\activate.bat" (
  call ".venv\Scripts\activate.bat" > nul 2> nul
)

python main.py

echo.
echo ==========================================
echo PROGRAM FINISHED
echo PRESS ANY KEY TO CLOSE
echo ==========================================
pause > nul
