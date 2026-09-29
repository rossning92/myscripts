#SingleInstance, Force
#InstallKeybdHook
#include %A_ScriptDir%\..\..\..\ahk\ExplorerHelper.ahk
#include %A_ScriptDir%\..\..\..\ahk\ChromeHotkey.ahk
#include %A_ScriptDir%\..\..\..\ahk\VirtualDesktop.ahk
#include %A_ScriptDir%\..\..\..\ahk\Window.ahk
#include %A_ScriptDir%\..\..\..\ahk\WinDrag.ahk

SetCapsLockState, AlwaysOff

CurrentDesktop := 0
WindowDividor := 2/3
LastKeyPressTime := 0

CONSOLE_WINDOW = myscriptsmgr

SetTitleMatchMode, 2

SetTimer, CheckIfRShiftIsPressed, 100
SetTimer, AutoResizeVNC, 1000

return

*CapsLock::Send {LWin Down}{LCtrl Down}
*CapsLock Up::Send {LWin Up}{LCtrl Up}

~LButton & WheelUp::
    Suspend, Permit
    SoundSet +2
    SoundPlay *16
return

~LButton & WheelDown::
    Suspend, Permit
    SoundSet -2
    SoundPlay *16
return

#If not WinActive("ahk_exe tvnviewer.exe") and not WinActive("ahk_class vwr::CDesktopWin") and not WinActive("ahk_exe League of Legends.exe")
    #LButton::WindowMouseDragMove()

    #a::Run "C:\Program Files\Everything\Everything.exe" -toggle-window
    #!c::ActivateChrome(0)
    ^#!c::ActivateChrome(2)
    #!2::ActivateChrome(3)
    #m::ToggleMicrophone()

    !q::WinClose, A

    ^q::
        ; If explorer is active, copy file path to clipboard
        UpdateExplorerInfo()

        ; Activate script window
        if WinExist(CONSOLE_WINDOW)
        {
            if WinActive(CONSOLE_WINDOW)
                WinActivateBottom, %CONSOLE_WINDOW%
            else
                WinActivate
            return
        }
    return

    #F4::
        Suspend, Permit
        WinGet, pid, PID, A
        Process, Close, %pid%
        SoundPlay %BEEP_FILE%
    return

    $F1::
        Send ^{PrintScreen}
    return

    #Left::
        UpdateWindowPosition("left")
    return

    #Right::
        UpdateWindowPosition("right")
    return

    #u::
        KeyWait, LWin, U
        SendMessage,0x112,0xF170,2,,Program Manager
    return

    !`::
        CoordMode, ToolTip, Window
        WinGet, ExStyle, ExStyle, A
        If (ExStyle & 0x8) {
            SetAlwaysOnTop("A", False)
        } else {
            SetAlwaysOnTop("A", True)
            ToolTip, AlwaysOnTop=1, 0, 0
        }
        SetTimer, RemoveToolTip, -2000
    return

    #MButton::
        MouseGetPos,,, hwndUnderCursor
        WinGetPos, winX, winY, , , ahk_id %hwndUnderCursor%
        WinGet, ExStyle, ExStyle, ahk_id %hwndUnderCursor%
        CoordMode, ToolTip, Screen
        If (ExStyle & 0x8) {
            SetAlwaysOnTop("ahk_id " hwndUnderCursor, False)
            ToolTip, AlwaysOnTop=0, %winX%, %winY%
        } else {
            SetAlwaysOnTop("ahk_id " hwndUnderCursor, True)
            ToolTip, AlwaysOnTop=1, %winX%, %winY%
        }
        SetTimer, RemoveToolTip, -2000
    return

    #Up::
        WinMaximize, A
        WinSet, AlwaysOnTop, Off, A
        SetAlwaysOnTop("A", False)
    return

    ToggleWindowDivider() {
        global WindowDividor
        if (WindowDividor = 2/3) {
            WindowDividor := 1/2
        } else {
            WindowDividor := 2/3
        }
    }

    GetLastKeyPressTimeDelta() {
        global LastKeyPressTime

        time := (A_Hour*3600 + A_Min*60 + A_Sec)*1000 + A_MSec
        delta := time - LastKeyPressTime
        LastKeyPressTime := time
        return delta
    }

    $!1::
        if WinActive("ahk_exe FL64.exe") {
            SetWindowPosF("A", 0, 0, WindowDividor, 1, False, True)
            return
        }

        SetWindowPosF("A", 0, 0, WindowDividor, 1, False, True)
        SetAlwaysOnTop("A", False)
    return

    $!2::
        SetWindowPosF("A", WindowDividor, 0, 1-WindowDividor, 1)

        SetAlwaysOnTop("A", True)
        ToolTip, AlwaysOnTop=1, 0, 0
        SetTimer, RemoveToolTip, -2000
    return

    $!3::
        SetWindowPos("A", 0, 0, 1920, 1080, forceResize:=True)
        SetAlwaysOnTop("A", False)
    return

    $!4::
        SetWindowPos("A", 240, 135, 1440, 810)
        SetAlwaysOnTop("A", False)
    return

    $!5::
        SetWindowPos("A", 0, 0, 960, 540)
        SetAlwaysOnTop("A", False)
    return

    $!6::
        WinGetPos, , , w, h, A
        SetWindowPos("A", (1920 - w) / 2, (1080 - h) / 2)
        SetAlwaysOnTop("A", False)
    return

    #0::
        CurrentDesktop := 1 - CurrentDesktop
        SwitchDesktopByNumber(CurrentDesktop + 1)
        ToggleDesktopIcons(1 - CurrentDesktop)
    return

    !#d::
        ToggleDesktopIcons()
    return

    ^!+v::
        Send %Clipboard%
    return
#If

#If WinExist("ahk_exe tvnviewer.exe") or WinExist("ahk_class vwr::CDesktopWin")
    $XButton2::
        ToggleVNC()
    return
#If

RemoveToolTip:
    ToolTip
return

ArrayHasValue(array, needle) {
    if not IsObject(array) {
        return false
    }
    for k, v in array {
        if (needle = v) {
            return true
        }
    }
    return false
}

UpdateWindowPosition(pos) {
    global WindowList

    WinGet, curHwnd, ID, A

    prevPos := ""
    for p, hwnd in WindowList {
        if (hwnd = curHwnd) {
            prevPos := p
            break
        }
    }

    if (prevPos != "") {
        ; If current window already in WindowList
        WindowList[prevPos] := WindowList[pos]
    }
    WindowList[pos] := curHwnd

    WinGetPos,tx,ty,tw,th,ahk_class Shell_TrayWnd,,,
    RATIO := 2 / 3

    for pos, hwnd in WindowList {
        if (pos = "left") {
            x := 0
            w := Floor(A_ScreenWidth * RATIO)
        } else if (pos = "right")
        {
            x := Floor(A_ScreenWidth * RATIO)
            w := Floor(A_ScreenWidth * (1 - RATIO))
        }

        y := 0
        h := A_ScreenHeight - th

        WinRestore, ahk_id %hwnd%
        WinSet, Style, +0x40000, ahk_id %hwnd%
        WinSet, Style, +Resize, ahk_id %hwnd%

        WinSet, AlwaysOnTop, Off, ahk_id %hwnd%

        SetWindowPos("ahk_id " hwnd, x, y, w, h)
        if (hwnd != curHwnd) {
            WinActivate, ahk_id %hwnd%
        }
    }

    WinActivate, ahk_id %curHwnd%
}

ActivateChrome(index=0)
{
    chrome := GetChrome()

    if (index = 0)
    {
        condition := "NOT CommandLine LIKE '%--user-data-dir=%' AND NOT CommandLine LIKE '%--type=%'"
    }
    else
    {
        condition := "CommandLine LIKE '%ChromeData" index "%' AND NOT CommandLine LIKE '%--type=%'"
    }

    pid =
    for process in ComObjGet("winmgmts:").ExecQuery("SELECT * FROM Win32_Process WHERE Name='chrome.exe' AND " condition)
    {
        pid := process.ProcessID
        break
    }

    title := "- Google Chrome ahk_pid " pid
    if ( pid != "" and WinExist(title) )
    {
        ActivateWindowByTitle(title)
    }
    else
    {
        if (index = 0)
        {
            Run %chrome%
        }
        else
        {
            Run %chrome% --user-data-dir=%USERPROFILE%\ChromeData%index%
        }
    }
}

MouseIsOverAndActive(title) {
    MouseGetPos,,, id
    if not WinActive("ahk_id " id)
        return false

    WinGet, matched_win_id, ID, %title%
    if (id = matched_win_id)
        return true
    else
        return false
}

CenterActiveWindow(width:=1920, height:=1080) {
    x := (A_ScreenWidth / 2) - (width / 2)
    y := (A_ScreenHeight / 2) - (height / 2)
    ; x := 0, y := 0

    w := A_ScreenHeight * 16 / 9
    h := A_ScreenHeight
    x := (A_ScreenWidth - w) / 2
    y := 0
    SetWindowPos("A", x, y, w, h)
}

SetWindowPos3(wintitle, X := "", Y := "", W := "", H := "") {
    WinGet hwnd, ID, %wintitle% ; WinExist() sets the last found window

    If ((X . Y . W . H) = "")
        Return False
    If !WinExist("ahk_id " . hwnd)
        Return False
    VarSetCapacity(WI, 60, 0) ; WINDOWINFO structure
    NumPut(60, WI, "Uint")
    If !DllCall("GetWindowInfo", "Ptr", hwnd, "Ptr", &WI)
        Return False
    WX := NumGet(WI, 4, "Int") ; X coordinate of the window
    WY := NumGet(WI, 8, "Int") ; Y coordinate of the window
    WW := NumGet(WI, 12, "Int") - WX ; width of the window
    WH := NumGet(WI, 16, "Int") - WY ; height of the window
    BW := NumGet(WI, 48, "UInt") - 1 ; border width - 1
    BH := NumGet(WI, 52, "UInt") - 1 ; border height - 1
    X := X <> "" ? X - BW : WX
    Y := Y <> "" ? Y : WY
    W := W <> "" ? W + BW + BW : WW
    H := H <> "" ? H + BH : WH

    DllCall("MoveWindow", "Ptr", hwnd, "Int", X, "Int", Y, "Int", W, "Int", H, "UInt", 1)
    WinRestore ahk_id %hwnd%
}

ToggleVNC()
{
    VNC_VIEWER := "ahk_class vwr::CDesktopWin"

    if WinActive("ahk_exe tvnviewer.exe") {
        WinMinimize, ahk_exe tvnviewer.exe
    } else if WinActive(VNC_VIEWER) {
        WinMinimize, %VNC_VIEWER%
        WinSet, AlwaysOnTop, Off, %VNC_VIEWER%
    } else if WinExist("ahk_exe tvnviewer.exe") {
        WinActivate, ahk_exe tvnviewer.exe
    } else if WinExist(VNC_VIEWER) {
        WinActivate, %VNC_VIEWER%
    }
}

CheckIfRShiftIsPressed()
{
    global IsRShiftKeyHold
    if (GetKeyState("RShift", "P"))
    {
        if (not IsRShiftKeyHold) {
            ToggleVNC()
        }
        IsRShiftKeyHold := true
    } else {
        IsRShiftKeyHold := false
    }
}

ToggleMicrophone()
{
    global Muted
    if (Muted)
    {
        ToolTip
        Run powershell -NoProfile -ExecutionPolicy unrestricted audio/unmute_mic.ps1,, Hide
        Muted := false
    }
    else
    {
        ToolTip, [MUTED], 0, 0
        Run powershell -NoProfile -ExecutionPolicy unrestricted audio/mute_mic.ps1,, Hide
        Muted := true
    }
}

AutoResizeVNC() {
    Critical, On
    winTitle := "ahk_class vwr::CDesktopWin"
    if WinActive(winTitle) {
        SetWindowPos(winTitle, 0, 0, A_ScreenHeight*16/9, A_ScreenHeight, true)
        WinSet, AlwaysOnTop, On, %winTitle%
    }
    Critical, Off
}
