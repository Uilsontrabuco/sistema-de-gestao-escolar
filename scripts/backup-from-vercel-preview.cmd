@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0backup-from-vercel-preview.ps1"
exit /b %errorlevel%
