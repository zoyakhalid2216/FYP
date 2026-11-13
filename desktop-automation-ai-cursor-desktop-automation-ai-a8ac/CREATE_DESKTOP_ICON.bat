@echo off
REM Creates Automate AI on YOUR Desktop (no reinstall needed)
setlocal EnableExtensions
cd /d "%~dp0"
title Automate AI - Create Desktop Icon

if not exist "%~dp0main.py" (
  echo ERROR: Put this file inside the Automate AI project folder, then run it.
  pause
  exit /b 1
)

REM Always refresh the launcher in the project folder
> "%~dp0Run Automate AI.bat" (
  echo @echo off
  echo cd /d "%~dp0"
  echo if not exist ".venv\Scripts\activate.bat" ^(
  echo   echo Run INSTALL_ON_YOUR_WINDOWS_PC.bat first.
  echo   pause
  echo   exit /b 1
  echo ^)
  echo call .venv\Scripts\activate.bat
  echo python main.py
  echo if errorlevel 1 pause
)

set "SRC=%~dp0Run Automate AI.bat"

REM Copy a visible .bat onto every common Desktop location
for %%D in (
  "%USERPROFILE%\Desktop"
  "%USERPROFILE%\OneDrive\Desktop"
  "%USERPROFILE%\OneDrive -*\Desktop"
  "%PUBLIC%\Desktop"
) do (
  if exist %%~D (
    copy /Y "%SRC%" "%%~D\Automate AI.bat" >nul 2>&1
    echo Copied launcher to: %%~D\Automate AI.bat
  )
)

REM Also create .lnk shortcuts via PowerShell
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='SilentlyContinue';" ^
  "$src = '%SRC%';" ^
  "$work = '%~dp0';" ^
  "$desks = @(" ^
  "  [Environment]::GetFolderPath('Desktop')," ^
  "  (Join-Path $env:USERPROFILE 'Desktop')," ^
  "  (Join-Path $env:USERPROFILE 'OneDrive\Desktop')," ^
  "  (Join-Path $env:PUBLIC 'Desktop')" ^
  ");" ^
  "Get-ChildItem -Path (Join-Path $env:USERPROFILE 'OneDrive*') -Directory -ErrorAction SilentlyContinue | ForEach-Object {" ^
  "  $d = Join-Path $_.FullName 'Desktop'; if (Test-Path $d) { $desks += $d }" ^
  "};" ^
  "$desks = $desks | Where-Object { $_ -and (Test-Path $_) } | Select-Object -Unique;" ^
  "$ws = New-Object -ComObject WScript.Shell;" ^
  "foreach ($desk in $desks) {" ^
  "  $lnkPath = Join-Path $desk 'Automate AI.lnk';" ^
  "  $sc = $ws.CreateShortcut($lnkPath);" ^
  "  $sc.TargetPath = $src;" ^
  "  $sc.WorkingDirectory = $work;" ^
  "  $sc.WindowStyle = 1;" ^
  "  $sc.Description = 'AI Desktop Automation';" ^
  "  $sc.Save();" ^
  "  Write-Host ('Created: ' + $lnkPath);" ^
  "  Copy-Item -Force $src (Join-Path $desk 'Automate AI.bat');" ^
  "}"

echo.
echo Done. Look on your Desktop for:
echo   - Automate AI
echo   - Automate AI.bat
echo.
echo If you still do not see it, press F5 on the Desktop, or open:
echo   %USERPROFILE%\Desktop
echo.
echo You can also start the app now from this folder:
echo   double-click  Run Automate AI.bat
echo.
start "" "%~dp0Run Automate AI.bat"
pause
