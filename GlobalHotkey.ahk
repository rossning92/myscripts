#SingleInstance, Force
#InstallKeybdHook
SetTitleMatchMode, RegEx ; Match window title using regular expressions
#include ahk/ExplorerHelper.ahk
#include ahk/WaitKey.ahk

Menu, Tray, Icon, Shell32.dll, 42 ; Tree icon

LastScript := ""
MatchClipboard := {{MATCH_CLIPBOARD}}
OnClipboardChange("ClipChanged")
return

{{HOTKEYS}}

#enter::RestartLastScript()

StartScript(scriptTitle, scriptPath, restartInstance)
{
    global LastScript

    titlePattern := "^" . scriptTitle . "|" . scriptTitle . "$"
    if WinExist(titlePattern) and not restartInstance
    {
        if WinActive(titlePattern)
            WinActivateBottom, %titlePattern%
        else
            WinActivate
        return
    }

    UpdateExplorerInfo()
    now := A_TickCount
    options := ""
    Run "{{PYTHON_EXEC}}" "{{START_SCRIPT}}" --restart-instance %restartInstance% "%scriptPath%",, Hide

    LastScript := scriptPath
}

SelectScript(scripts)
{
    message := "Select script:`n"
    maxItems := scripts.Length() < 9 ? scripts.Length() : 9
    Loop, %maxItems%
        message .= "[" . A_Index . "] " . scripts[A_Index][1] . "`n"

    if (scripts.Length() > 9)
        message .= "Only the first 9 scripts are shown.`n"

    key := WaitKey(message)
    if key is not digit
        return

    index := key + 0
    if (index < 1 or index > maxItems)
        return

    selected := scripts[index]
    StartScript(selected[2], selected[3], selected[4])
}

RestartLastScript()
{
    global LastScript
    if (LastScript <> "") {
        Run "{{PYTHON_EXEC}}" "{{START_SCRIPT}}" --restart-instance true %LastScript%,, Hide
    }
}

ClipChanged(type) {
    global MatchClipboard

    ; Early return if control key is not pressed down.
    Sleep 500
    if !GetKeyState("Control") {
        return
    }

    if WinActive("ahk_exe vncviewer.exe") {
        return
    }

    if (type = 1) { ; clipboard has text
        text := Clipboard
        matchedScript := []
        matchedText := []
        message := ""

        ; Find all matched scripts
        for _index, item in MatchClipboard
        {
            regex := item[1]
            scriptName := item[2]
            if (RegExMatch(text, regex, match)) {
                message .= "[" (matchedScript.Length() + 1) "] " scriptName " | " match "`n"
                matchedScript.Push(item)
                matchedText.Push(match)
            }
        }

        if (matchedScript.Length() > 0) {
            key := WaitKey(message)
            if ( key <> "" and InStr("0123456789", key) ) {
                index := Ord(key) - Ord("0")
                scriptPath := matchedScript[index][3]
                match := matchedText[index]
                Run, "{{PYTHON_EXEC}}" "{{START_SCRIPT}}" "%scriptPath%" "%match%"
            }
        }
    }
}
