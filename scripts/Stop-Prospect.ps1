param(
  [int]$Port = 8765
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
$BackendDir = (Resolve-Path (Join-Path $Root "backend")).Path

$connections = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
$processIds = @()
if ($connections) {
  $processIds = $connections | Select-Object -ExpandProperty OwningProcess -Unique
} else {
  $netstatLines = netstat -ano | Select-String -Pattern "127\.0\.0\.1:$Port\s+.*LISTENING\s+(\d+)"
  $processIds = $netstatLines | ForEach-Object { [int]$_.Matches[0].Groups[1].Value } | Select-Object -Unique
}

if (!$processIds) {
  Write-Host "Prospect n'est pas lance sur le port $Port."
  exit 0
}

foreach ($processId in $processIds) {
  $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
  if (!$process) {
    continue
  }

  $processPath = $process.Path
  $isBackendProcess = $processPath -and $processPath.StartsWith($BackendDir, [System.StringComparison]::OrdinalIgnoreCase)
  $isPythonServer = $process.ProcessName -in @("python", "pythonw")
  $isProspect = $false
  try {
    $session = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/session/" -TimeoutSec 2
    $isProspect = $session.desktop -eq $true
  } catch {
    $isProspect = $false
  }

  if ($isBackendProcess -or ($isPythonServer -and $isProspect)) {
    Stop-Process -Id $processId -Force
    Write-Host "Prospect arrete."
  } else {
    Write-Host "Port $Port occupe par un autre process ($processId), rien n'a ete arrete."
  }
}
