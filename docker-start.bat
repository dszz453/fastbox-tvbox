@echo off
chcp 65001 >nul
title FastBox TVBox 智能搜索服务 Docker 启动器

echo ============================================================
echo      🚀 FastBox TVBox 智能聚合搜索与源服务 (Docker 版)
echo ============================================================
echo.

docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Docker 环境！
    echo 请先安装并启动 Docker Desktop 或 Docker 服务。
    echo.
    pause
    exit /b 1
)

echo [1/2] 正在启动/构建 Docker 容器...
docker compose up -d --build

if %errorlevel% equ 0 (
    echo.
    echo ============================================================
    echo [成功] FastBox 容器已成功在后台启动！
    echo ------------------------------------------------------------
    echo * 本地 Web 控制台:  http://127.0.0.1:8088
    echo * TVBox 豆瓣首页订阅: http://你的局域网IP:8088/tvbox?home=douban
    echo * TVBox 全能离线订阅: http://你的局域网IP:8088/tvbox?home=full
    echo ============================================================
    echo.
    echo 提示: 浏览器打开 http://127.0.0.1:8088 可直接使用手机/电视扫码填入！
    echo.
) else (
    echo.
    echo [失败] 启动容器时出现错误，请检查 Docker 是否正常运行。
    echo.
)

pause
