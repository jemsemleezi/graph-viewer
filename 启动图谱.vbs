' Double-click to launch graph-viewer tray (no console window)
Dim objShell
Set objShell = CreateObject("WScript.Shell")
scriptDir = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
objShell.Run "cmd /c cd /d """ & scriptDir & """ && uv run python tray.py", 0, False
Set objShell = Nothing
