@echo off
chcp 65001 >nul
title Saraphane - Testler
cd /d "%~dp0"

echo.
echo  Kalite kapilari calistiriliyor (ruff, mypy, pytest, TypeScript)...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\testler.ps1"

echo.
pause
