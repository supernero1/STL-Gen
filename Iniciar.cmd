@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Ejecuta primero instalar.ps1. Consulta README.md.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m app.launch
if errorlevel 1 pause
