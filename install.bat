@echo off
chcp 65001 >nul
cd /d "%~dp0"
title ChemTox Profiler - установка
set PYTHONIOENCODING=utf-8

echo ==========================================
echo  ChemTox Profiler - установка и запуск
echo ==========================================
echo.

rem --- Шаг A: основная установка (как раньше) ---
if exist "setup.ps1" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
) else (
    echo [!!] setup.ps1 не найден, пропускаю основную установку.
)

if not exist "python\python.exe" (
    echo.
    echo [XX] Портативный Python не найден в папке python\ - установка не завершена.
    echo      Повторите install.bat или переустановите программу.
    pause
    exit /b 1
)

rem --- Шаг B: проверка всего, докачка недостающего, запуск ---
"python\python.exe" check_install.py --launch
if errorlevel 1 (
    echo.
    echo [XX] Остались проблемы, см. список выше.
    echo      Исправьте их ^(например, проверьте интернет^) и запустите install.bat снова.
    pause
    exit /b 1
)
exit /b 0