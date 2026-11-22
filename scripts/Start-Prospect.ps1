param(
  [switch]$Build,
  [ValidateRange(1024, 65535)]
  [int]$Port = 8765,
  [switch]$QA
)

$ErrorActionPreference = "Stop"

trap {
  $message = "Prospect n'a pas pu demarrer.`n$($_.Exception.Message)"
  Write-Host $message
  if ([Environment]::GetCommandLineArgs() -contains 'Hidden') {
    try {
      $shell = New-Object -ComObject WScript.Shell
      $null = $shell.Popup($message, 30, "Prospect", 16)
    } catch {
      # A shortcut may be launched in a session without a visible desktop.
    }
  }
  exit 1
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
$FrontendDir = Join-Path $Root "frontend"
$BackendDir = Join-Path $Root "backend"
$FrontendDist = Join-Path $BackendDir "desktop_static"
$RuntimeDir = Join-Path $BackendDir ".desktop"
if ($QA) { $RuntimeDir = Join-Path $BackendDir ".qa\launcher" }
$ServerLog = Join-Path $RuntimeDir "service.log"
. (Join-Path $ScriptDir "Desktop-Instance.ps1")
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
    return ($session.desktop -eq $true -and $session.auth_required -eq $true -and $session.mode -eq "locked")
  } catch {
    return $false
  }
}

function Test-DesktopBuildCurrent {
  $index = Get-Item -LiteralPath (Join-Path $FrontendDist "index.html") -ErrorAction SilentlyContinue
  if (!$index) { return $false }
  $inputs = Get-ChildItem -LiteralPath $FrontendDir -File -Force |
    Where-Object { $_.Name -match '^(index\.html|package(?:-lock)?\.json|(?:vite|tailwind|postcss)\.config\..+|\.env(?:\..+)?)$' }
  $sourceFiles = Get-ChildItem -LiteralPath (Join-Path $FrontendDir "src"), (Join-Path $FrontendDir "public") -File -Recurse
  $newer = @($inputs) + @($sourceFiles) |
    Where-Object { $_.LastWriteTimeUtc -gt $index.LastWriteTimeUtc } |
    Select-Object -First 1
  return !$newer
}

$instanceName = Get-ProspectInstanceName $Root $QA
$mutex = New-Object Threading.Mutex($false, "$instanceName-owner")
$activate = New-Object Threading.EventWaitHandle($false, 'AutoReset', "$instanceName-activate")
$stop = New-Object Threading.EventWaitHandle($false, 'ManualReset', "$instanceName-stop")
$ownsInstance = $false
$service = $null
$browserProcess = $null
$profile = $null
$window = [IntPtr]::Zero
$startupProcess = $null
$startupPath = $null
function Set-StartupStatus([string]$Message) {
  if ($startupPath) {
    try { [IO.File]::WriteAllText($startupPath, $Message) } catch [IO.IOException] { }
  }
}
function Close-StartupStatus {
  if ($startupPath) {
    Set-StartupStatus 'CLOSE'
    if ($startupProcess) { $null = $startupProcess.WaitForExit(3000) }
    Remove-Item -LiteralPath $startupPath -Force -ErrorAction SilentlyContinue
    if ($startupProcess) { $startupProcess.Dispose(); $script:startupProcess = $null }
    $script:startupPath = $null
  }
}
try {
  try { $ownsInstance = $mutex.WaitOne(0) }
  catch [Threading.AbandonedMutexException] { $ownsInstance = $true }
  if (!$ownsInstance) {
    $null = $activate.Set()
    return
  }
  $null = $stop.Reset()
  New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
  $startupPath = Join-Path $RuntimeDir ("startup-" + [Guid]::NewGuid().ToString('N') + '.txt')
  Set-StartupStatus "Preparation de l'application."
  try {
    $statusHelper = Join-Path $ScriptDir 'Startup-Status.ps1'
    $startupProcess = Start-Process "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -WindowStyle Hidden -PassThru -ArgumentList @(
      '-NoProfile', '-STA', '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden',
      '-File', "`"$statusHelper`"", '-StatusPath', "`"$startupPath`"", '-OwnerProcessId', $PID)
  } catch {
    # Feedback is optional: preserve the functional application launcher.
    Remove-Item -LiteralPath $startupPath -Force -ErrorAction SilentlyContinue
    $startupPath = $null
  }
  if (Test-PortOpen) {
    throw "Le port $Port est deja utilise. Ferme le service qui l'utilise ou choisis un autre port libre."
  }
  New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null

  if ($Build -or !(Test-DesktopBuildCurrent)) {
    Set-StartupStatus "Mise a jour de l’interface NateOS..."
    $buildBackup = Join-Path $BackendDir ("backups\desktop-build-" + [Guid]::NewGuid().ToString("N"))
    $staging = Join-Path $buildBackup "staging"
    $previous = Join-Path $buildBackup "previous"
    Push-Location $FrontendDir
    try {
      if (!(Test-Path "node_modules")) {
        npm.cmd install
        if ($LASTEXITCODE -ne 0) { throw "Installation frontend impossible." }
      }
      $env:VITE_API_URL = "/api"
      $env:VITE_BASE_PATH = "/"
      $env:VITE_STATIC_DEMO = "false"
      $env:VITE_DESKTOP_MODE = "true"
      npm.cmd run build -- --outDir $staging
      if ($LASTEXITCODE -ne 0 -or !(Test-Path -LiteralPath (Join-Path $staging "index.html"))) {
        throw "Construction frontend impossible."
      }
      if (Test-Path -LiteralPath $FrontendDist) {
        [IO.Directory]::Move($FrontendDist, $previous)
      }
      try {
        [IO.Directory]::Move($staging, $FrontendDist)
      } catch {
        if (!(Test-Path -LiteralPath $FrontendDist) -and (Test-Path -LiteralPath $previous)) {
          [IO.Directory]::Move($previous, $FrontendDist)
        }
        throw
      }
    } finally {
      Pop-Location
    }
  }

  Set-StartupStatus "Verification de l’acces prive..."
  $env:DESKTOP_MODE = "True"
  $env:DESKTOP_AUTO_AUTH = "True"
  $env:DATABASE_URL = ""
  $env:DEBUG = "False"
  $env:SERVE_FRONTEND = "True"
  $env:REQUIRE_OWNER_TOKEN = "False"
  $env:DEMO_MODE = "False"
  $env:ALLOWED_HOSTS = "127.0.0.1,localhost"
  $env:CORS_ALLOWED_ORIGINS = "http://127.0.0.1:$Port,http://localhost:$Port"
  $env:FRONTEND_DIST_DIR = $FrontendDist
  $env:DJANGO_SETTINGS_MODULE = "config.settings"
  $env:PROSPECT_DESKTOP_QA = ""
  if ($QA) { $env:PROSPECT_DESKTOP_QA = $RuntimeDir; $env:DJANGO_SETTINGS_MODULE = "config.desktop_qa" }
  if (!(Test-Path -LiteralPath $VenvPython)) {
    throw "Python est introuvable dans backend\.venv. L'environnement local de Prospect doit etre repare."
  }
  Push-Location $BackendDir
  try {
    try {
      # Windows PowerShell 5.1 treats redirected native stderr as error records.
      $ErrorActionPreference = "Continue"
      $LASTEXITCODE = -1
      $accessOutput = @(& $VenvPython manage.py desktop_access --existing 2>&1)
      $accessExitCode = $LASTEXITCODE
    } catch {
      throw "Impossible de lancer Python pour lire les reglages proteges. Aucun serveur n'a ete demarre. Verifie l'environnement local du projet."
    } finally {
      $ErrorActionPreference = "Stop"
    }
    if ($accessExitCode -ne 0) {
      $accessError = $accessOutput | ForEach-Object { [string]$_ } | Where-Object { $_ -match '^CommandError: DPAPI ' } | Select-Object -First 1
      if ($accessError) { throw ($accessError -replace '^CommandError: ', '') }
      throw "Impossible de verifier l'acces prive. Aucun nouveau serveur n'a ete demarre. Verifie Python et la configuration de Prospect."
    }
    $AccessToken = ($accessOutput | Out-String).Trim()
    if (!$AccessToken) { throw "Aucun jeton d'acces local n'a ete retourne. Aucun serveur n'a ete demarre." }
  } finally {
    Pop-Location
  }

  Set-StartupStatus "Demarrage du serveur et du worker..."
  $info = New-Object Diagnostics.ProcessStartInfo
  $info.FileName = $env:ComSpec
  $info.Arguments = '/d /s /c ""{0}" -u manage.py desktop_run {1} > "{2}" 2>&1"' -f $VenvPython, $Port, $ServerLog
  $info.WorkingDirectory = $BackendDir
  $info.UseShellExecute = $false
  $info.CreateNoWindow = $true
  $info.RedirectStandardInput = $true
  $service = [Diagnostics.Process]::Start($info)

  $ready = $false
  $deadline = [DateTime]::UtcNow.AddSeconds(60)
  while (!$service.HasExited -and [DateTime]::UtcNow -lt $deadline) {
    if ($stop.WaitOne(300)) { return }
    if ($activate.WaitOne(0)) { Set-StartupStatus "Demarrage en cours ; ouverture automatique des que Prospect est pret." }
    if (Test-ProspectReady) {
      $ready = $true
      break
    }
  }
  if (!$ready) { throw "Le serveur ou le worker a echoue. Consulte le journal local : $ServerLog" }

  Set-StartupStatus "Prospect est pret. Ouverture de la fenetre..."
  $browserPaths = @(
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
    "$env:LOCALAPPDATA\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
  )
  $browser = $browserPaths | Where-Object { Test-Path $_ } | Select-Object -First 1

  # A new build must load fresh HTML even if the app window cached the old entry page.
  $indexBytes = [IO.File]::ReadAllBytes((Join-Path $FrontendDist "index.html"))
  $sha = [Security.Cryptography.SHA256]::Create()
  try {
    $buildVersion = [BitConverter]::ToString($sha.ComputeHash($indexBytes)).Replace("-", "")
  } finally {
    $sha.Dispose()
  }
  $Url = $Url + "?build=$buildVersion#/?access=" + [Uri]::EscapeDataString($AccessToken)

  if (!$browser) { throw "Microsoft Edge ou Google Chrome est requis pour ouvrir la fenetre Prospect." }

  # A separate browser profile keeps Prospect independent of other browser windows.
  Add-Type @"
  using System;
  using System.Runtime.InteropServices;
  public static class ProspectWindow {
      [DllImport("user32.dll")] public static extern bool IsWindow(IntPtr window);
      [DllImport("user32.dll")] public static extern bool ShowWindowAsync(IntPtr window, int command);
      [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr window, uint message, IntPtr wParam, IntPtr lParam);
  }
"@
  $profile = Join-Path $RuntimeDir "browser"
  if ($stop.WaitOne(0)) { return }
  $browserProcess = Start-Process $browser -ArgumentList "--user-data-dir=""$profile""", "--no-first-run", "--disable-extensions", "--disable-background-mode", "--app=$Url" -PassThru
  $deadline = [DateTime]::UtcNow.AddSeconds(30)
  while ($window -eq [IntPtr]::Zero -and [DateTime]::UtcNow -lt $deadline) {
    if ($stop.WaitOne(200)) { return }
    if ($window -eq [IntPtr]::Zero -and $activate.WaitOne(0)) { Set-StartupStatus "Ouverture de la fenetre Prospect en cours..." }
    if ($service.HasExited) { throw "Le service Prospect s'est arrete. Consulte $ServerLog." }
    $browserProcess.Refresh()
    if (!$browserProcess.HasExited) { $window = $browserProcess.MainWindowHandle }
  }
  if ($window -eq [IntPtr]::Zero) { throw "La fenetre Prospect n'a pas pu s'ouvrir." }

  Close-StartupStatus
  while ([ProspectWindow]::IsWindow($window)) {
    if ($stop.WaitOne(200)) { return }
    if ($service.HasExited) { throw "Le service Prospect s'est arrete. Consulte $ServerLog." }
    if ($activate.WaitOne(0)) {
      $null = [ProspectWindow]::ShowWindowAsync($window, 9)
      $shell = New-Object -ComObject WScript.Shell
      $null = $shell.AppActivate($browserProcess.Id)
    }
  }
} finally {
  Close-StartupStatus
  # An explicit stop can arrive after Edge starts but before its handle is recorded.
  # Only this newly launched browser and its dedicated profile may be cleaned up.
  if ($window -eq [IntPtr]::Zero -and $browserProcess -and !$browserProcess.HasExited) {
    $ownedBrowser = Get-CimInstance Win32_Process -Filter ("ProcessId = {0}" -f $browserProcess.Id) -ErrorAction SilentlyContinue
    if ($ownedBrowser -and $ownedBrowser.ExecutablePath -eq $browser -and $profile -and $ownedBrowser.CommandLine.Contains($profile)) {
      $null = $browserProcess.CloseMainWindow()
      if (!$browserProcess.WaitForExit(2000)) {
        # Its root process was verified above; /T closes only that application's children.
        & "$env:SystemRoot\System32\taskkill.exe" /PID $browserProcess.Id /T /F 2>$null | Out-Null
      }
    }
  }
  if ($window -ne [IntPtr]::Zero -and [ProspectWindow]::IsWindow($window)) {
    $null = [ProspectWindow]::PostMessage($window, 0x10, [IntPtr]::Zero, [IntPtr]::Zero)
  }
  if ($service) {
    try { $service.StandardInput.Close() } catch [IO.IOException] {}
    $service.WaitForExit()
    $service.Dispose()
  }
  if ($ownsInstance) { $mutex.ReleaseMutex() }
  $stop.Dispose()
  $activate.Dispose()
  $mutex.Dispose()
}
