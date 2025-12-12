' run_organizer.vbs
Option Explicit
Dim WSH, ScriptFolder, exePath, i, cmd
Set WSH = CreateObject("WScript.Shell")
ScriptFolder = Left(WScript.ScriptFullName, Len(WScript.ScriptFullName) - Len(WScript.ScriptName))
exePath = ScriptFolder & "organizer.exe"

cmd = """" & exePath & """"
For i = 0 To WScript.Arguments.Count - 1
    cmd = cmd & " """ & WScript.Arguments(i) & """"
Next

' Run hidden, non-blocking
WSH.Run cmd, 0, False
