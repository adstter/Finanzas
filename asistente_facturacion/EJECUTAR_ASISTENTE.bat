@echo off
chcp 65001 >nul
title Asistente de Facturacion ADSTTER
cd /d "%~dp0"
echo.
echo ========================================
echo   ASISTENTE DE FACTURACION ADSTTER
echo   Certificacion FEL con INFILE
echo ========================================
echo.
python asistente_facturacion.py
pause
