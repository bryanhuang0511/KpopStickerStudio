@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo [錯誤] 尚未建立 .venv 虛擬環境，請先依 README 安裝依賴。
    pause
    exit /b 1
)
".venv\Scripts\python.exe" run_studio.py
pause
