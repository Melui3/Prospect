param(
  [switch]$Build,
  [ValidateRange(1024, 65535)]
  [int]$Port = 8765
)

$ErrorActionPreference = "Stop"

trap {
  $message = "Prospect n'a pas pu demarrer.`n$($_.Exception.Message)"
  Write-Host $message
  $shell = New-Object -ComObject WScript.Shell
  $shell.Popup($message, 0, "Prospect", 16) | Out-Null
  exit 1
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
$FrontendDir = Join-Path $Root "frontend"
$BackendDir = Join-Path $Root "backend"
$FrontendDist = Join-Path $BackendDir "desktop_static"
$ServerLog = Join-Path $BackendDir "desktop-server.log"
$Url = "http://127.0.0.1:$Port/"
$VenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"

function Test-PortOpen {
  $client = New-Object System.Net.Sockets.TcpClient
  try {
    $client.Connect("127.0.0.1", $Port)
    return $true
  } catch {
    return $false
  } finally {
    $client.Dispose()
  }
}

function Test-ProspectReady {
  try {
    $session = Invoke-RestMethod -Uri "${Url}api/session/" -TimeoutSec 2
    return $session.desktop -eq $true
  } catch {
    return $false
  }
}

if ($Build -or !(Test-Path (Join-Path $FrontendDist "index.html"))) {
  Set-Location $FrontendDir
  if (!(Test-Path "node_modules")) {
    npm.cmd install
    if ($LASTEXITCODE -ne 0) { throw "Installation frontend impossible." }
  }
  $env:VITE_API_URL = "/api"
  $env:VITE_BASE_PATH = "/"
  $env:VITE_STATIC_DEMO = "false"
  $env:VITE_DESKTOP_MODE = "true"
  npm.cmd run build -- --outDir "../backend/desktop_static" --emptyOutDir
  if ($LASTEXITCODE -ne 0) { throw "Construction frontend impossible." }
  Set-Location $Root
}

if (Test-PortOpen) {
  if (!(Test-ProspectReady)) {
    throw "Le port $Port est occupe par un autre service. Relance avec -Port 8767."
  }
} else {
  if (Test-Path $ServerLog) {
    Remove-Item -LiteralPath $ServerLog -Force
  }

  $serverScript = Join-Path $ScriptDir "run-desktop-server.ps1"
  Start-Process powershell.exe `
    -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$serverScript`"", "-Port", $Port `
    -WorkingDirectory $Root `
    -WindowStyle Hidden

  $ready = $false
  for ($i = 0; $i -lt 120; $i++) {
    Start-Sleep -Milliseconds 500
    if (Test-ProspectReady) {
      $ready = $true
      break
    }
  }

  if (!$ready) {
    Write-Host "Prospect n'a pas demarre. Regarde le log : $ServerLog"
    throw "Consulte le journal local : $ServerLog"
  }
}

$browserPaths = @(
  "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
  "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
  "$env:LOCALAPPDATA\Microsoft\Edge\Application\msedge.exe",
  "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
  "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
  "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)
$browser = $browserPaths | Where-Object { Test-Path $_ } | Select-Object -First 1

$env:DESKTOP_MODE = "True"
$env:DESKTOP_AUTO_AUTH = "True"
$env:DATABASE_URL = ""
Push-Location $BackendDir
try {
  $AccessToken = (& $VenvPython manage.py desktop_access).Trim()
  if ($LASTEXITCODE -ne 0 -or !$AccessToken) { throw "Acces Windows prive indisponible." }
} finally {
  Pop-Location
}
$Url = $Url + "#/?access=" + [Uri]::EscapeDataString($AccessToken)

if ($browser) {
  Start-Process $browser -ArgumentList "--app=$Url"
} else {
  Start-Process $Url
}
