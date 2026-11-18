@echo off
rem WorkBuddy / CodeBuddy hook launcher for Windows: membrain-hook <event>. Never fails the host.
rem Without uvx on the path, uv runs the runtime with "uv tool run", the command uvx stands for. Without either, or
rem before the runtime can run, session-start tells the agent so, since the runtime that would say it is missing.
setlocal
if "%MEMBRAIN_PACKAGE%"=="" set "MEMBRAIN_PACKAGE=membrain-ai[embedded,semantic] @ https://github.com/chriswu727/membrain/archive/b465c4b773e97d2fcd09525d200397abd0754b37.zip"
set "RUN=uvx"
where uvx >nul 2>nul && goto found
set "RUN=uv tool run"
where uv >nul 2>nul && goto found
if "%~1"=="session-start" echo {"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"memBrain is installed but cannot run: uv was not found on this computer, so nothing is remembered or recalled. In your first reply, tell the user this once and ask them to install uv from https://docs.astral.sh/uv/ and then start a new session."}}
exit /b 0
:found
if "%~1"=="start" (
  where uv >nul 2>nul || exit /b 0
  start "" /b cmd /c "uv tool install --quiet --python 3.12 "%MEMBRAIN_PACKAGE%" >nul 2>nul & %RUN% --offline --python 3.12 --from membrain-ai membrain plugin start >nul 2>nul"
  exit /b 0
)
%RUN% --offline --python 3.12 --from membrain-ai membrain plugin hook %1 --host workbuddy 2>nul && exit /b 0
if "%~1"=="session-start" echo {"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"memBrain is installed but its runtime is not ready yet, so nothing is remembered or recalled in this session. It installs in the background when a session starts; the first time needs an internet connection and takes a few minutes. In your first reply, tell the user this once, and that if they see it again in a later session the installation is failing, for example without an internet connection."}}
exit /b 0
