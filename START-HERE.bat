@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo First run: creating the local Python environment...
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install.ps1" -WithImages
  if errorlevel 1 (
    echo.
    echo Installation failed. Nothing outside this folder was changed.
    pause
    exit /b 1
  )
)
".venv\Scripts\python.exe" -m assetforge doctor
echo.
echo Next steps:
echo   assetforge.cmd init .
echo   assetforge.cmd recipes
echo   assetforge.cmd providers
pause
