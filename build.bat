@echo off
chcp 65001 >nul
title ChemTox Profiler Builder
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0build.ps1"
pause
