@echo off

cd /d "%~dp0"

call install\install_autohotkey.cmd

echo Find python executable...
python --version >nul 2>&1
if not %errorlevel%==0 (
    call install\install_python.cmd
    if errorlevel 1 exit /b 1
)

title myscriptsmgr

"%USERPROFILE%\.venv\myscripts\Scripts\python.exe" --version >nul 2>&1
if errorlevel 1 (
  echo Create or repair myscripts virtual environment...
  python -m venv "%USERPROFILE%\.venv\myscripts" --system-site-packages
  if errorlevel 1 exit /b 1
)
call "%USERPROFILE%\.venv\myscripts\Scripts\activate.bat"
if errorlevel 1 exit /b 1

echo Install packages...
python -m pip --disable-pip-version-check install -r requirements.txt >nul
if errorlevel 1 exit /b 1

python myscripts.py %*
