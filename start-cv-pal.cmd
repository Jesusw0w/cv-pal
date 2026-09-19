@echo off
rem Double-click this to start CV Pal. See scripts\start-cv-pal.ps1 for what it does.
rem A .cmd rather than a .ps1 because Windows opens a double-clicked .ps1 in Notepad.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-cv-pal.ps1" %*
if errorlevel 1 pause
