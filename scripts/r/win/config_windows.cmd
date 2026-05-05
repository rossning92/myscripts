@echo off

echo Remove Cortana icon from taskbar
reg add HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced /v ShowCortanaButton /t REG_DWORD /d 0 /f >NUL

echo Never combine taskbar icons
reg add HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced /v TaskbarGlomLevel /t REG_DWORD /d 2 /f >NUL

echo Remove pinned items from Taskbar
reg delete HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Taskband /f >NUL
reg add HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Taskband\AuxilliaryPins /v MailPin /t REG_DWORD /d 1 /f >NUL

echo Disable search bar from the Taskbar (Windows 11)
reg add HKCU\Software\Microsoft\Windows\CurrentVersion\Search /v SearchboxTaskbarMode /t REG_DWORD /d 0 /f >NUL

echo Hide Widgets on Taskbar
reg add HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced /v TaskbarDa /t REG_DWORD /d 0 /f >NUL

echo Show file extensions
reg add HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced /v HideFileExt /t REG_DWORD /d 0 /f >NUL

echo Show hidden files
reg add HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced /v Hidden /t REG_DWORD /d 1 /f >NUL

echo Disable explorer search history
reg add HKCU\Software\Policies\Microsoft\Windows\Explorer /v DisableSearchBoxSuggestions /t REG_DWORD /d 1 /f >NUL

echo Hide Task View Icon
reg add HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced /v ShowTaskViewButton /t REG_DWORD /d 0 /f >NUL

echo Hide People Icon
reg add HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced\People /v PeopleBand /t REG_DWORD /d 0 /f >NUL

echo Set File Explorer to "Open to This PC"
reg add HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced /v LaunchTo /t REG_DWORD /d 1 /f >NUL

echo Disable adding frequent folders in Quick access
reg add HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer /v ShowFrequent /t REG_DWORD /d 0 /f >NUL

echo Disable recent items
reg add HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced /v Start_TrackDocs /t REG_DWORD /d 0 /f >NUL
rd /s /q "%APPDATA%\Microsoft\Windows\Recent"

echo Disable Game Bar (Win+G)
reg add HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\GameDVR /v AppCaptureEnabled /t REG_DWORD /d 0 /f >NUL
reg add HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\GameDVR /v GameDVR_Enabled /t REG_DWORD /d 0 /f >NUL

echo Disable shake to minimize
reg add HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced /v DisallowShaking /t REG_DWORD /d 1 /f >NUL

echo Disable hibernation
powercfg /hibernate off

echo Disable UAC
CALL "%~dp0disable_UAC.cmd"

echo Disable animation
reg add "HKCU\Control Panel\Desktop\WindowMetrics" /v MinAnimate /t REG_DWORD /d 0 /f >NUL
reg add "HKCU\Control Panel\Desktop" /v UserPreferencesMask /t REG_BINARY /d 9012038010000000 /f >NUL
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" /v TaskbarAnimations /t REG_BINARY /d 0 /f >NUL

@REM Disable translucent selection rectangle
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" /v ListviewAlphaSelect /t REG_DWORD /d 0 /f >NUL
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" /v ListviewShadow /t REG_DWORD /d 0 /f >NUL

echo Apply "details" view on all folders
reg add HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Streams /v Settings /t REG_BINARY /d 08000000040000000100000000777e137335cf11ae6908002b2e1262040000000200000043000000 /f >NUL

echo Customize console window
CALL "%~dp0config_console_window.cmd"

echo Notification duration
reg add "HKCU\Control Panel\Accessibility" /v MessageDuration /t REG_DWORD /d 10 /f >NUL

echo Set wallpaper to solid black
reg add "HKCU\Control Panel\Desktop" /v Wallpaper /t REG_SZ /d "" /f >NUL
reg add "HKCU\Control Panel\Colors" /v Background /t REG_SZ /d "0 0 0" /f >NUL

echo Remove the Meet Now icon
reg add HKCU\Software\Microsoft\Windows\CurrentVersion\Policies\Explorer /t REG_DWORD /v HideSCAMeetNow /d 1 /f >NUL

echo Disable creation of Desktop.in
reg add HKCU\Software\Microsoft\Windows\CurrentVersion\Policies\Explorer /t REG_DWORD /v UseDesktopIniCache /d 0 /f >NUL

echo Config Microsoft Pinyin
reg add HKCU\SOFTWARE\Microsoft\InputMethod\Settings\CHS /t REG_DWORD /v "English Switch Key" /d 4 /f >NUL
reg add HKCU\SOFTWARE\Microsoft\InputMethod\Settings\CHS /t REG_DWORD /v EnableChineseEnglishPunctuationSwitch /d 0 /f >NUL
reg add HKCU\SOFTWARE\Microsoft\InputMethod\Settings\CHS /t REG_DWORD /v EnableSimplifiedTraditionalOutputSwitch /d 0 /f >NUL

@REM Windows 11 stuff:

echo Disable News and Interests
reg add HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Feeds /t REG_DWORD /v ShellFeedsTaskbarViewMode /d 2 /f >NUL

echo Disable search icon on the taskbar
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Search" /v SearchboxTaskbarMode /t REG_DWORD /d 0 /f

echo Align taskbar left
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" /v TaskbarAl /t REG_DWORD /d 0 /f

echo Disable transparency effect
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize" /v EnableTransparency /t REG_DWORD /d 0 /f

echo Disable CABC
reg add "HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers" /v DisableCABC /t REG_DWORD /d 1 /f
reg add "HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers" /v CABCOption /t REG_DWORD /d 0 /f

echo Disable SmartScreen
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer" /v SmartScreenEnabled /t REG_SZ /d Off /f >NUL

echo Disable Snap Bar at top of screen
reg add HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced /v EnableSnapBar /t REG_DWORD /d 0 /f >NUL

echo Disable Aero Snap (drag-to-edge window arrangement)
reg add "HKCU\Control Panel\Desktop" /v WindowArrangementActive /t REG_SZ /d 0 /f >NUL

echo Revert to the full right-click menu
reg add "HKCU\Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}\InprocServer32" /f /ve

taskkill /f /im explorer.exe >NUL
start explorer.exe

@REM echo Set default browser manually
@REM "%windir%\system32\control.exe" /name Microsoft.DefaultPrograms /page pageDefaultProgram\pageAdvancedSettings

echo Disable the standby timeout
powercfg /change standby-timeout-ac 0
powercfg /change standby-timeout-dc 0

run_script r/win/disable_auto_updates.cmd
run_script r/win/register_mpv_url_protocal.bat
run_script r/win/disable_windows_animation.ps1
