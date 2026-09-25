@echo off
title MySqlAutoBkps - Iniciando...
cd /d "%~dp0"
echo ========================================================
echo   Iniciando MySqlAutoBkps...
echo ========================================================
python main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Ocurrio un error al ejecutar la aplicacion.
    pause
)
