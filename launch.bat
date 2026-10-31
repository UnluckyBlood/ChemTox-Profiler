@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist "python\pythonw.exe" ( echo Python не установлен. Запустите install.bat & pause & exit /b 1 )
if not exist "db\models\all" ( echo Модели не скачаны. Запустите install.bat & pause & exit /b 1 )
start "" "python\pythonw.exe" launcher.py
