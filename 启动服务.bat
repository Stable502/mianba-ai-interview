@echo off
chcp 65001 >nul
title 一键启动前端后端服务
echo ============================================
echo        一键启动前端后端服务
echo ============================================
echo.

REM 获取脚本所在目录
set "ROOT=%~dp0"

echo [1/2] 启动后端服务 (FastAPI, 端口 8000)...
start "后端 - FastAPI (8000)" cmd /k "cd /d %ROOT%backend && call .venv\Scripts\activate.bat && python run.py"

echo [2/2] 启动前端服务 (Vite, 端口 5173)...
start "前端 - Vite (5173)" cmd /k "cd /d %ROOT%frontend && npm run dev"

echo.
echo ============================================
echo  服务启动中：
echo   - 后端: http://127.0.0.1:8000
echo   - 前端: http://localhost:5173
echo ============================================
echo.
echo 两个窗口已分别打开，关闭对应窗口即可停止服务。
echo 此窗口将在 3 秒后自动关闭...
timeout /t 3 /nobreak >nul
exit
