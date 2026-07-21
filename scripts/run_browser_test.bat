@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1
C:\Users\LiShuai\Desktop\Agents\starmap\backend\.venv-new\starmap-backend-oeaMSS_T-py3.12\Scripts\python.exe C:\Users\LiShuai\Desktop\Agents\starmap\scripts\browser_e2e_test.py
exit /b %errorlevel%
