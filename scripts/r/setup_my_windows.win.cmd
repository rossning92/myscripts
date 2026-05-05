@echo off
cd "%~dp0"

run_script r/win/config_windows.cmd
run_script r/win/add_cn_lang.ps1
run_script r/dev/choco/install_package.py @ross
run_script r/vscode/config_vscode.py
