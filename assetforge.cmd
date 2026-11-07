@echo off
setlocal
set "ROOT=%~dp0"
if exist "%ROOT%.venv\Scripts\python.exe" (
  "%ROOT%.venv\Scripts\python.exe" -m assetforge %*
) else (
  set "PYTHONPATH=%ROOT%src;%PYTHONPATH%"
  python -m assetforge %*
)
exit /b %ERRORLEVEL%
