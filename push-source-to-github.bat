@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title Push source to GitHub - FastBox

echo ========================================================
echo   FastBox - Push source code to GitHub
echo   (GitHub Actions will build ^& push the Docker image)
echo ========================================================
echo.

git --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Git not found. Please install Git for Windows first.
    pause
    exit /b 1
)

if "%1"=="" (
    set /p REPO_URL="Please enter your GitHub repo URL (e.g. https://github.com/zhangxiaonan1986/fastbox-tvbox.git): "
) else (
    set REPO_URL=%1
)

if "!REPO_URL!"=="" (
    echo [ERROR] Repo URL cannot be empty.
    pause
    exit /b 1
)

echo.
echo [1/4] Initializing git repository...
if not exist ".git" (
    git init
    git branch -M main
) else (
    echo       already initialized, skip.
)

echo.
echo [2/4] Configuring git identity (if missing)...
git config user.name  >nul 2>&1 || git config user.name  "zhangxiaonan1986"
git config user.email >nul 2>&1 || git config user.email "zhangxiaonan1986@users.noreply.github.com"

echo.
echo [3/4] Staging and committing files...
git add -A
git commit -m "feat: FastBox TVBox aggregator (douban home, multi-source search, pancheck)" 2>nul
if errorlevel 1 echo       nothing new to commit (or already committed).

echo.
echo [4/4] Pushing to GitHub: !REPO_URL!
git remote remove origin 2>nul
git remote add origin !REPO_URL!
git push -u origin main
if errorlevel 1 (
    echo.
    echo [ERROR] Push failed. Possible reasons:
    echo   - The repo does not exist yet. Create an empty repo on GitHub first.
    echo   - You have not logged in to GitHub. Run: git credential-manager github login
    pause
    exit /b 1
)

echo.
echo ========================================================
echo   [SUCCESS] Source pushed to GitHub!
echo.
echo   Next: GitHub Actions will automatically build the image.
echo   1) Open your repo ^> Actions tab ^> watch the workflow
echo   2) Add secret DOCKERHUB_TOKEN in:
echo      Settings ^> Secrets and variables ^> Actions ^> New repository secret
echo   3) After the workflow turns green, pull the image anywhere:
echo      docker run -d --name fastbox-tv -p 8088:8088 --restart unless-stopped zhangxiaonan1986/fastbox-tvbox:latest
echo ========================================================
echo.
pause
