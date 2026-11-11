param(
  [int]$Port = 8765
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
$BackendDir = Join-Path $Root "backend"
$VenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
$LogPath = Join-Path $BackendDir "desktop-server.log"
$WorkerLog = Join-Path $BackendDir "desktop-worker.log"
$WorkerError = Join-Path $BackendDir "desktop-worker-error.log"

Set-Location $BackendDir

if (!(Test-Path $VenvPython)) {
  py -3.13 -m venv .venv
  if ($LASTEXITCODE -ne 0) { throw "Python 3.13 est requis pour creer l'environnement local." }
}

function Test-DjangoAvailable {
  try {
    & $VenvPython -c "import django" > $null 2>&1
    return $LASTEXITCODE -eq 0
  } catch {
    return $false
  }
}

if (!(Test-DjangoAvailable)) {
  py -3.13 -m venv .venv
  if ($LASTEXITCODE -ne 0) { throw "Impossible de reparer l'environnement Python local." }
}

if (!(Test-DjangoAvailable)) {
  & $VenvPython -m pip install -r requirements.txt
  if ($LASTEXITCODE -ne 0) { throw "Installation backend impossible." }
}

$env:DESKTOP_MODE = "True"
$env:DESKTOP_AUTO_AUTH = "True"
$env:SERVE_FRONTEND = "True"
$env:DEBUG = "False"
$env:DATABASE_URL = ""
$env:REQUIRE_OWNER_TOKEN = "False"
$env:DEMO_MODE = "False"
$env:ALLOWED_HOSTS = "127.0.0.1,localhost"
$env:CORS_ALLOWED_ORIGINS = "http://127.0.0.1:$Port,http://localhost:$Port"
$env:FRONTEND_DIST_DIR = Join-Path $BackendDir "desktop_static"

New-Item -ItemType Directory -Force -Path (Join-Path $BackendDir "staticfiles") | Out-Null

$QuotedPython = '"' + $VenvPython + '"'
$QuotedLog = '"' + $LogPath + '"'

if (Test-Path (Join-Path $BackendDir "db.sqlite3")) {
  & $VenvPython manage.py migrate --check > $null 2>&1
  if ($LASTEXITCODE -ne 0) {
    cmd.exe /c "$QuotedPython manage.py backup_data --reason before-upgrade >> $QuotedLog 2>&1"
    if ($LASTEXITCODE -ne 0) { throw "Sauvegarde impossible. Demarrage annule pour proteger la base." }
  }
}
cmd.exe /c "$QuotedPython manage.py migrate --noinput >> $QuotedLog 2>&1"
if ($LASTEXITCODE -ne 0) { throw "Migration impossible. Consulte $LogPath." }
$Worker = Start-Process -FilePath $VenvPython -ArgumentList "manage.py", "run_jobs" -WorkingDirectory $BackendDir -WindowStyle Hidden -RedirectStandardOutput $WorkerLog -RedirectStandardError $WorkerError -PassThru
try {
  cmd.exe /c "$QuotedPython manage.py runserver 127.0.0.1:$Port --noreload >> $QuotedLog 2>&1"
} finally {
  if (!$Worker.HasExited) { Stop-Process -Id $Worker.Id -Force -ErrorAction SilentlyContinue }
}
