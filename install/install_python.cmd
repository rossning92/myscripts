@echo off
where winget >nul 2>&1
if errorlevel 1 (
    echo WinGet is required to install Python. Install App Installer and try again.
    exit /b 1
)

echo Install Python 3.12...
winget install --id Python.Python.3.12 --exact --source winget --scope user --silent --accept-source-agreements --accept-package-agreements
if errorlevel 1 exit /b 1

rem Make Python available to the calling launcher without restarting the terminal.
set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%PATH%"
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not available after installation. Restart your terminal and try again.
    exit /b 1
)
exit /b 0
