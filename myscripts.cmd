@echo off

cd /d "%~dp0"

call install\install_choco.cmd
call install\install_autohotkey.cmd

echo Find python executable...
python --version >nul 2>&1
if not %errorlevel%==0 (
    call install\install_python.cmd
)

title myscriptsmgr

if not exist "%USERPROFILE%\.venv\myscripts" (
  python -m venv "%USERPROFILE%\.venv\myscripts" --system-site-packages
)
call "%USERPROFILE%\.venv\myscripts\Scripts\activate.bat"

echo Install packages...
pip --disable-pip-version-check install -r requirements.txt >nul

python myscripts.py %*
