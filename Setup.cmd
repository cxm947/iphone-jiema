@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File "%~dp0scripts\show-setup.ps1"
if errorlevel 1 pause
