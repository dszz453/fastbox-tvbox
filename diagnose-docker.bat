@echo off
setlocal
cd /d "%~dp0"
title Docker / Virtualization Diagnostics - FastBox

echo ============================================================
echo   Docker ^& Virtualization Diagnostics
echo ============================================================
echo.

echo [1] Docker CLI version
docker --version 2>nul || echo     docker CLI NOT found in PATH
echo.

echo [2] Docker engine status
docker version --format "Server: {{.Server.Version}}" 2>nul || echo     Engine NOT running
echo.

echo [3] Is this a virtual machine?
powershell -NoProfile -Command "$cs=Get-CimInstance Win32_ComputerSystem; Write-Host ('    Manufacturer: '+$cs.Manufacturer); Write-Host ('    Model       : '+$cs.Model)"
echo.

echo [4] CPU virtualization flags
powershell -NoProfile -Command "$p=Get-CimInstance Win32_Processor; Write-Host ('    CPU  : '+$p.Name); Write-Host ('    VBS  : '+$p.VirtualizationFirmwareEnabled); Write-Host ('    SLAT : '+$p.SecondLevelAddressTranslationExtensions)"
echo.

echo [5] Hypervisor present (True = running inside a VM)
powershell -NoProfile -Command "$c=Get-ComputerInfo -Property HyperVisorPresent; Write-Host ('    HyperVisorPresent: '+$c.HyperVisorPresent)"
echo.

echo [6] Required Windows features
powershell -NoProfile -Command "Get-WindowsOptionalFeature -Online | Where-Object { $_.FeatureName -match 'Linux|VirtualMachinePlatform|Hyper-V' } | ForEach-Object { Write-Host ('    '+$_.FeatureName+' = '+$_.State) }"
echo.

echo [7] Docker Desktop engine error (last lines)
powershell -NoProfile -Command "$log=\"$env:LOCALAPPDATA\Docker\log\host\com.docker.backend.exe.log\"; if(Test-Path $log){ Get-Content $log -Tail 400 | Select-String -Pattern 'No virtualization available|failed to start|preconditions' | Select-Object -Last 3 | ForEach-Object { Write-Host ('    '+$_.Line) } } else { Write-Host '    log not found' }"
echo.

echo ============================================================
echo   Diagnosis summary:
echo     - If SLAT = False and HyperVisorPresent = True:
echo       This is a Hyper-V VM without nested virtualization.
echo       Docker Desktop CANNOT run here.
echo.
echo     Solutions (see DEPLOY-GUIDE.md):
echo       A) Enable nested virt on the HOST:
echo          Set-VMProcessor -VMName "VMName" -ExposeVirtualizationExtensions $true
echo       B) Use GitHub Actions cloud build (recommended, no local Docker):
echo          double-click push-source-to-github.bat
echo       C) Build on another device that has working Docker.
echo ============================================================
echo.
pause
