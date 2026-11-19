param(
  [string]$ShortcutDirectory = [Environment]::GetFolderPath("Desktop"),
  [ValidateRange(1024, 65535)]
  [int]$Port = 8765
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
$Launcher = Join-Path $ScriptDir "Start-Prospect.ps1"
$Icon = Join-Path $ScriptDir "prospect.ico"
$PowerShell = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"

if (!(Test-Path -LiteralPath $ShortcutDirectory -PathType Container)) {
  throw "Le dossier du raccourci n'existe pas : $ShortcutDirectory"
}

$shell = New-Object -ComObject WScript.Shell
$ShortcutPath = Join-Path $ShortcutDirectory "Prospect.lnk"
$shortcut = $shell.CreateShortcut($ShortcutPath)

if ((Test-Path -LiteralPath $ShortcutPath) -and $shortcut.Arguments -notlike "*$Launcher*") {
  throw "Un autre raccourci Prospect existe deja. Choisis un autre dossier."
}

$shortcut.TargetPath = $PowerShell
$shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Launcher`" -Port $Port"
$shortcut.WorkingDirectory = $Root
$shortcut.Description = "Prospect - outil personnel de prospection locale"
$shortcut.WindowStyle = 7
$shortcut.IconLocation = "$Icon,0"
$shortcut.Save()
Write-Host "Raccourci cree : $ShortcutPath"
