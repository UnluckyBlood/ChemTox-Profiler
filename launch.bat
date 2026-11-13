@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist "python\pythonw.exe" goto needinstall
if not exist "db\models\all" goto needinstall
start "" "python\pythonw.exe" launcher.py
exit /b 0

:needinstall
echo Установка не завершена или не хватает моделей - запускаю install.bat
call "%~dp0install.bat"