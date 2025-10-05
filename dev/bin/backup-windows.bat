@echo off
REM Palimpsest backup via WSL

REM Change to your WSL distro name
set WSL_DISTRO=Ubuntu

REM Run backup in WSL
wsl -d %WSL_DISTRO% bash -c "cd ~/Documnets/palimpsest && ./dev/bin/run-backup.sh"

if %ERRORLEVEL% EQU 0 (
    echo Backup completed successfully
) else (
    echo Backup failed with error %ERRORLEVEL%
)
