@echo off
chcp 65001 >nul
title Akilli Saraphane Yonetim Sistemi
cd /d "%~dp0"

echo.
echo  ============================================================
echo    AKILLI SARAPHANE YONETIM SISTEMI
echo  ============================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo  Kurulum bulunamadi. Ilk kurulum baslatiliyor...
    echo  Bu islem birkac dakika surebilir.
    echo.
    powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\kurulum.ps1"
    if errorlevel 1 (
        echo.
        echo  KURULUM BASARISIZ. Yukaridaki hatayi inceleyin.
        pause
        exit /b 1
    )
)

echo  Servisler baslatiliyor...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\baslat.ps1"

echo.
echo  Backend ve arayuz ayri pencerelerde acildi.
echo  Bu pencereyi kapatabilirsiniz.
echo.
timeout /t 8 >nul
