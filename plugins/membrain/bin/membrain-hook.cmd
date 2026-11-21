@echo off
rem WorkBuddy / CodeBuddy hook launcher for Windows: membrain-hook <event>. Never fails the host.
rem Without uvx on the path, uv runs the runtime with "uv tool run", the command uvx stands for. Without either, or
rem before the runtime can run, session-start tells the agent so, since the runtime that would say it is missing.
setlocal
if "%MEMBRAIN_PACKAGE%"=="" set "MEMBRAIN_PACKAGE=membrain-ai[embedded,semantic] @ https://github.com/chriswu727/membrain/archive/302c19d277cf775e5f355230d3192b2f2c3812fa.zip"
set "RUN=uvx"
where uvx >nul 2>nul && goto found
set "RUN=uv tool run"
where uv >nul 2>nul && goto found
if "%~1"=="session-start" echo {"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"memBrain is installed but cannot run: uv was not found on this computer, so nothing is remembered or recalled. In your first reply, tell the user this once and ask them to install uv from https://docs.astral.sh/uv/ and then start a new session."}}
exit /b 0
:found
if "%~1"=="start" (
  where uv >nul 2>nul || exit /b 0
  start "" /b cmd /c ""%~f0" _install"
  exit /b 0
)
rem Run by "start" in the background: the versions the tests ran (constraints.txt), or without them when that fails.
if "%~1"=="_install" (
  uv tool install --quiet --python 3.12 --constraints "%~dp0..\constraints.txt" "%MEMBRAIN_PACKAGE%" >nul 2>nul || uv tool install --quiet --python 3.12 "%MEMBRAIN_PACKAGE%" >nul 2>nul
  %RUN% --offline --python 3.12 --from membrain-ai membrain plugin start >nul 2>nul
  exit /b 0
)
rem A hook never waits on uv's tool lock: while uv installs or updates the runtime, it gives up after 2 seconds.
set "UV_LOCK_TIMEOUT=2"
%RUN% --offline --python 3.12 --from membrain-ai membrain plugin hook %1 --host workbuddy 2>nul && exit /b 0
if "%~1"=="session-start" echo {"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"memBrain is installed but its runtime is not ready yet, so nothing is remembered or recalled until it is. It installs in the background; the first time needs an internet connection and takes a few minutes. Memory then starts by itself; no new session is needed. In your first reply, tell the user this once, and that if they see it again in a later session the installation is failing, for example without an internet connection."}}
exit /b 0
