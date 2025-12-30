$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$PWD\ADB Transfer Tool.lnk")
$Shortcut.TargetPath = "pythonw.exe"
$Shortcut.Arguments = """$PWD\src\main.py"""
$Shortcut.WorkingDirectory = "$PWD"
$Shortcut.IconLocation = "$PWD\app_icon.ico"
$Shortcut.Save()
Write-Host "Shortcut created: ADB Transfer Tool.lnk"
