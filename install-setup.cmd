@echo off
rem Install or update the shared setup into %USERPROFILE%\.claude. Safe to run again.
python "%~dp0install\install.py" %*
if errorlevel 1 pause
