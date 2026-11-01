@echo off
rem WorkBuddy / CodeBuddy hook launcher for Windows: membrain-hook <event>. Never fails the host.
setlocal
if "%MEMBRAIN_PACKAGE%"=="" set "MEMBRAIN_PACKAGE=membrain-ai[embedded,semantic] @ https://github.com/chriswu727/membrain/archive/d0d7a0379f7ac5f1b81dad04504601bb6606f1b0.zip"
where uvx >nul 2>nul || exit /b 0
if "%~1"=="start" (
  start "" /b cmd /c "uv tool install --quiet --python 3.12 "%MEMBRAIN_PACKAGE%" >nul 2>nul & uvx --offline --python 3.12 --from membrain-ai membrain plugin start >nul 2>nul"
  exit /b 0
)
uvx --offline --python 3.12 --from membrain-ai membrain plugin hook %1 --host workbuddy 2>nul
exit /b 0
