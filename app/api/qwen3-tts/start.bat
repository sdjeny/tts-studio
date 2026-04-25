@echo off
chcp 65001 >nul 2>&1
title Qwen3-TTS API Service
echo ============================================
echo   Qwen3-TTS API 服务启动器
echo ============================================
echo.

:: ── 检查 Python ──────────────────────────────────
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python，请先安装 Python 3.10+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python 已安装

:: ── 检查 pip ─────────────────────────────────────
pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 pip
    pause
    exit /b 1
)
echo [OK] pip 已安装

:: ── 读取 config.yaml 中的依赖列表 ─────────────────
:: 依赖：flask, pyyaml（requirements.txt 中声明）
echo.
echo [检查依赖] 正在安装缺失的 Python 包...
pip install flask pyyaml -q
if %errorlevel% neq 0 (
    echo [错误] 依赖安装失败，请检查网络后重试
    pause
    exit /b 1
)
echo [OK] 依赖检查完成

:: ── 检查 config.yaml 是否存在 ─────────────────────
if not exist "config.yaml" (
    echo [错误] config.yaml 不存在，请参照 config.example.yaml 创建
    pause
    exit /b 1
)
echo [OK] config.yaml 已找到

:: ── 启动服务 ─────────────────────────────────────
echo.
echo ════════════════════════════════════════════
echo   服务启动中... 请稍候
echo   看到 "Running on http://..." 即启动成功
echo   按 Ctrl+C 停止服务
echo ════════════════════════════════════════════
echo.
python server.py

:: 服务退出后暂停（方便查看错误）
echo.
echo [服务已退出]
pause
