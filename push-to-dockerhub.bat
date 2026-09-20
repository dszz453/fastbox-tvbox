@echo off
chcp 65001 >nul
title FastBox Docker Hub 镜像构建与上传 (用户: zhangxiaonan1986)

echo ============================================================
echo   🚀 FastBox Docker Hub 镜像一键构建与推送 (zhangxiaonan1986)
echo ============================================================
echo.

set DOCKER_USER=zhangxiaonan1986
set IMAGE_NAME=%DOCKER_USER%/fastbox-tvbox
set TAG=latest

docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 本地未检测到 Docker 环境，请先安装或启动 Docker Desktop！
    pause
    exit /b 1
)

echo 目标镜像: %IMAGE_NAME%:%TAG%
echo.

echo [1/3] 正在检查/登录 Docker Hub 账号 (zhangxiaonan1986)...
echo 如果尚未登录，请在下方提示时输入 Docker Hub 密码或 Access Token：
docker login -u %DOCKER_USER%
if %errorlevel% neq 0 (
    echo.
    echo [错误] Docker Hub 登录失败，请确认账号密码正确！
    pause
    exit /b 1
)

echo.
echo [2/3] 正在构建 Docker 镜像: %IMAGE_NAME%:%TAG% (请稍候)...
docker build -t %IMAGE_NAME%:%TAG% .
if %errorlevel% neq 0 (
    echo.
    echo [错误] 镜像构建失败！
    pause
    exit /b 1
)

echo.
echo [3/3] 正在推送镜像到 Docker Hub...
docker push %IMAGE_NAME%:%TAG%
if %errorlevel% equ 0 (
    echo.
    echo ============================================================
    echo [成功] 镜像已成功发布到 Docker Hub！
    echo 仓库地址: https://hub.docker.com/r/%IMAGE_NAME%
    echo ------------------------------------------------------------
    echo 以后在任何设备（群晖/极空间/软路由/VPS）上只需一行命令即可运行：
    echo.
    echo   docker run -d --name fastbox -p 8088:8088 --restart unless-stopped %IMAGE_NAME%:%TAG%
    echo.
    echo ============================================================
) else (
    echo.
    echo [失败] 镜像推送失败，请检查网络连接或仓库权限。
)

pause
