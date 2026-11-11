[CmdletBinding()]
param(
  [string]$RepoPath = (Split-Path -Parent $PSScriptRoot),
  [string]$PlanPath = "",
  [ValidateSet("Menu", "Preview", "Commit", "Push")]
  [string]$Action = "Menu"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2
$script:LogPath = Join-Path $env:LOCALAPPDATA "CodexGitFinalizer\operations.log"
$script:RepoRoot = ""
$script:PlanFile = ""

function Protect-Text([string]$Text) {
  if ($null -eq $Text) { return "" }
  $safe = [regex]::Replace($Text, '(?i)(https?://)[^/@\s]+@', '$1[identifiants masques]@')
  $safe = [regex]::Replace($safe, '\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16}|xox[baprs]-[A-Za-z0-9-]{16,}|sk_live_[A-Za-z0-9]{16,})\b', '[secret masque]')
  $safe = [regex]::Replace($safe, '(?i)\b(?:npm_[A-Za-z0-9]{30,}|Bearer\s+[A-Za-z0-9._=-]{20,}|(?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|password|passwd|secret[_-]?key)\b\s*[:=]\s*["'']?[A-Za-z0-9/+_.=-]{12,})', '[secret masque]')
  return [regex]::Replace($safe, '(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.(?!example\b|test\b|invalid\b|localhost\b)[A-Z]{2,}\b', '[email masque]')
}

function Add-LocalLog([string]$Kind, [string]$Command, [int]$ExitCode, [string]$Output) {
  try {
    $directory = Split-Path -Parent $script:LogPath
    if (!(Test-Path -LiteralPath $directory)) { New-Item -ItemType Directory -Path $directory -Force | Out-Null }
    $entry = @(
      "[$([DateTime]::Now.ToString('yyyy-MM-dd HH:mm:ss zzz'))] $Kind"
      "Repository: $script:RepoRoot"
      "Command: $(Protect-Text $Command)"
      "Exit code: $ExitCode"
      "Output:"
      (Protect-Text $Output)
      ""
    ) -join [Environment]::NewLine
    [IO.File]::AppendAllText($script:LogPath, $entry + [Environment]::NewLine, [Text.Encoding]::UTF8)
  } catch { Write-Host "Journal local indisponible : $($_.Exception.Message)" -ForegroundColor Yellow }
}

function Invoke-Git([string[]]$GitArguments, [switch]$AllowFailure) {
  $safeArguments = @("-c", ("safe.directory=" + $script:RepoRoot)) + $GitArguments
  $display = "git " + ($safeArguments -join " ")
  $previousPreference = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  try { $raw = @(& git @safeArguments 2>&1); $exitCode = $LASTEXITCODE }
  catch {
    Add-LocalLog "Git inaccessible" $display 9009 $_.Exception.Message
    throw "Git inaccessible : $($_.Exception.Message)"
  } finally {
    $ErrorActionPreference = $previousPreference
  }
  $output = ($raw | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
  if ($exitCode -ne 0 -and !$AllowFailure) {
    Add-LocalLog "Commande Git refusee" $display $exitCode $output
    throw ("Git a refuse la commande (code $exitCode). " + (Protect-Text $output) + [Environment]::NewLine + "Journal : $script:LogPath")
  }
  return [pscustomobject]@{ ExitCode = $exitCode; Output = $output }
}

function Initialize-Repository {
  if (!(Test-Path -LiteralPath $RepoPath -PathType Container)) { throw "Dossier projet introuvable : $RepoPath" }
  $cursor = (Resolve-Path -LiteralPath $RepoPath).Path
  while ($cursor -and !(Test-Path -LiteralPath (Join-Path $cursor ".git"))) {
    $parent = Split-Path -Parent $cursor
    if (!$parent -or $parent -eq $cursor) { $cursor = ""; break }
    $cursor = $parent
  }
  if (!$cursor) { throw "Aucun depot Git trouve dans $RepoPath ni dans ses parents." }
  $script:RepoRoot = $cursor
  Push-Location -LiteralPath $script:RepoRoot
  try {
    $rootResult = Invoke-Git @("rev-parse", "--show-toplevel")
    $reportedRoot = (Resolve-Path -LiteralPath $rootResult.Output.Trim()).Path
    if (![string]::Equals($reportedRoot, $script:RepoRoot, [StringComparison]::OrdinalIgnoreCase)) { throw "Le dossier Git detecte ne correspond pas a la racine calculee." }
  } finally { Pop-Location }
  if ($PlanPath) {
    if ([IO.Path]::IsPathRooted($PlanPath)) { $candidate = $PlanPath }
    else { $candidate = Join-Path $script:RepoRoot $PlanPath }
  } else { $candidate = Join-Path $script:RepoRoot ".git-finalizer-plan.json" }
  if (!(Test-Path -LiteralPath $candidate -PathType Leaf)) { throw "Manifeste introuvable : $candidate" }
  $script:PlanFile = (Resolve-Path -LiteralPath $candidate).Path
}

function Get-Plan {
  try { $plan = (Get-Content -LiteralPath $script:PlanFile -Raw -Encoding UTF8) | ConvertFrom-Json }
  catch { throw "Manifeste JSON invalide ou illisible : $($_.Exception.Message)" }
  $messageProperty = $plan.PSObject.Properties["commitMessage"]
  $validationProperty = $plan.PSObject.Properties["validation"]
  $filesProperty = $plan.PSObject.Properties["files"]
  if (!$messageProperty -or [string]::IsNullOrWhiteSpace([string]$messageProperty.Value) -or $messageProperty.Value.Length -gt 120 -or $messageProperty.Value -match '[\r\n]') {
    throw "commitMessage doit contenir 1 a 120 caracteres sur une seule ligne."
  }
  if (!$validationProperty -or [string]::IsNullOrWhiteSpace([string]$validationProperty.Value) -or $validationProperty.Value.Length -gt 2000) { throw "Le manifeste doit contenir les preuves de verification dans validation (maximum 2000 caracteres)." }
  if (!$filesProperty -or !$filesProperty.Value -or @($filesProperty.Value).Count -eq 0) { throw "Le manifeste doit contenir une liste files non vide." }
  $paths = New-Object System.Collections.Generic.List[string]
  $seen = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
  foreach ($rawPath in @($filesProperty.Value)) {
    if ($rawPath -isnot [string] -or [string]::IsNullOrWhiteSpace($rawPath)) { throw "Chaque chemin doit etre une chaine non vide." }
    $path = $rawPath.Replace('\', '/')
    if ([IO.Path]::IsPathRooted($rawPath) -or $path -match '(^|/)\.\.?(/|$)' -or $path -match '[*?\[\]]' -or $path -match '[\x00-\x1f]' -or $path.StartsWith('/') -or $path.StartsWith(':') -or $path -match '(^|/)\.git(/|$)') {
      throw "Chemin non autorise dans le manifeste : $rawPath"
    }
    $fullPath = [IO.Path]::GetFullPath((Join-Path $script:RepoRoot $path))
    $rootPrefix = $script:RepoRoot.TrimEnd('\') + '\'
    if (!$fullPath.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) { throw "Le chemin sort du depot : $rawPath" }
    if (!$seen.Add($path)) { throw "Chemin duplique dans le manifeste : $path" }
    $paths.Add($path)
  }
  return [pscustomobject]@{ Message = [string]$messageProperty.Value; Validation = [string]$validationProperty.Value; Files = @($paths.ToArray()) }
}

function Get-BranchName {
  $branch = Invoke-Git @("symbolic-ref", "--short", "-q", "HEAD") -AllowFailure
  if ($branch.ExitCode -ne 0 -or !$branch.Output.Trim()) { throw "HEAD detache : commit/push refuse." }
  return $branch.Output.Trim()
}

function Test-PathBlocked([string]$Path) {
  $normalized = $Path.Replace('\', '/').ToLowerInvariant()
  $leaf = [IO.Path]::GetFileName($normalized)
  if ($normalized -match '(^|/)(backups?|private|credentials?|secrets?)(/|$)') { return "dossier prive ou de sauvegarde" }
  if ($leaf -match '^\.env($|\.)' -and $leaf -notin @(".env.example", ".env.sample")) { return "fichier de configuration sensible" }
  if ($leaf -match '(^|[._-])(id_rsa|id_ed25519|private[-_]?key|credentials?|secret)([._-]|$)') { return "nom de fichier sensible" }
  if ($normalized -match '\.(sqlite3?|db|bak|backup|dump|p12|pfx|pem|key|csv|tsv|xlsx?|xls|log)$') { return "format de donnees privees, sauvegarde ou cle" }
  if ($leaf -match '(prospects?|customers?|clients?|contacts?)[._-].*\.(json|jsonl|txt)$') { return "fichier de donnees de contacts" }
  return ""
}

function Get-FileText([string]$Path) {
  $fullPath = Join-Path $script:RepoRoot $Path
  if (!(Test-Path -LiteralPath $fullPath -PathType Leaf)) { throw "Fichier absent ou suppression non prise en charge : $Path" }
  $item = Get-Item -LiteralPath $fullPath -Force
  if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Lien ou point de jonction refuse : $Path" }
  $cursor = $script:RepoRoot
  foreach ($part in $Path.Replace('\', '/').Split('/')) {
    $cursor = Join-Path $cursor $part
    $component = Get-Item -LiteralPath $cursor -Force
    if (($component.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Chemin passant par un lien ou une jonction refuse : $Path" }
  }
  if ($item.Length -gt 10485760) { throw "Fichier superieur a 10 Mo, bloque par prudence : $Path" }
  $bytes = [IO.File]::ReadAllBytes($fullPath)
  if ($bytes -contains 0) { throw "Fichier binaire refuse par prudence : $Path" }
  return [IO.File]::ReadAllText($fullPath, [Text.Encoding]::UTF8)
}

function Test-ContentBlocked([string]$Content) {
  $patterns = @(
    '-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----',
    '\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b',
    '\bAKIA[A-Z0-9]{16}\b', '\bxox[baprs]-[A-Za-z0-9-]{16,}\b',
    '\bsk_live_[A-Za-z0-9]{16,}\b', '\bsk-[A-Za-z0-9_-]{28,}\b',
    '\bnpm_[A-Za-z0-9]{30,}\b', '(?i)\bBearer\s+[A-Za-z0-9._=-]{20,}',
    '(?i)\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|password|passwd|secret[_-]?key)\b\s*[:=]\s*["'']?[A-Za-z0-9/+_.=-]{12,}'
  )
  foreach ($pattern in $patterns) { if ([regex]::IsMatch($Content, $pattern)) { return "motif de credential reconnu" } }
  if ([regex]::IsMatch($Content, '(?i)\b(?:tel(?:ephone)?|mobile|phone|portable)\s*[:=]?\s*\+?[0-9][0-9 .()/-]{7,}[0-9]\b')) {
    return "numero de telephone dans le contenu"
  }
  $emails = [regex]::Matches($Content, '(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b')
  foreach ($match in $emails) {
    $domain = $match.Value.Split('@')[-1].ToLowerInvariant()
    if ($domain -notmatch '(^|\.)(example|test|invalid|localhost)$' -and $domain -notin @("example.com", "example.org", "example.net")) {
      return "adresse email reelle ou non clairement fictive"
    }
  }
  return ""
}

function Test-ManifestFiles([object]$Plan, [switch]$RequireChanged) {
  $failures = New-Object System.Collections.Generic.List[string]
  foreach ($path in $Plan.Files) {
    $blocked = Test-PathBlocked $path
    if ($blocked) { $failures.Add("$path : $blocked"); continue }
    try { $content = Get-FileText $path } catch { $failures.Add($_.Exception.Message); continue }
    $contentBlock = Test-ContentBlocked $content
    if ($contentBlock) { $failures.Add("$path : $contentBlock"); continue }
    $ignored = Invoke-Git @("check-ignore", "-q", "--", $path) -AllowFailure
    if ($ignored.ExitCode -eq 0) { $failures.Add("$path : fichier ignore par Git"); continue }
    $status = Invoke-Git @("status", "--porcelain=v1", "--untracked-files=all", "--", $path)
    if ($RequireChanged -and !$status.Output.Trim()) { $failures.Add("$path : aucun changement a inclure") }
  }
  if ($failures.Count -gt 0) {
    Write-Host "Lot bloque par les controles de securite :" -ForegroundColor Red
    foreach ($failure in $failures) { Write-Host "  - $failure" -ForegroundColor Red }
    throw "Aucun commit/push autorise."
  }
}

function Show-Context([object]$Plan) {
  $branch = Get-BranchName
  $head = (Invoke-Git @("rev-parse", "--short", "HEAD")).Output.Trim()
  $upstream = Invoke-Git @("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}") -AllowFailure
  Write-Host ""
  Write-Host "Depot : $script:RepoRoot"
  Write-Host "Branche : $branch | HEAD : $head"
  if ($upstream.ExitCode -eq 0) { Write-Host "Amont : $($upstream.Output.Trim())" } else { Write-Host "Amont : non configure" -ForegroundColor Yellow }
  Write-Host "Changements du depot (hors manifeste = exclus) :"
  $status = (Invoke-Git @("status", "--short", "--untracked-files=all")).Output
  if ($status) { $status -split '\r?\n' | ForEach-Object { Write-Host "  $_" } } else { Write-Host "  aucun" }
  Write-Host "Fichiers exacts du manifeste :"
  foreach ($path in $Plan.Files) { Write-Host "  + $path" -ForegroundColor Cyan }
  Write-Host "Message : $($Plan.Message)"
  Write-Host "Verification declaree : $($Plan.Validation)"
}

function Show-CandidateDiff([object]$Plan) {
  foreach ($path in $Plan.Files) {
    $tracked = Invoke-Git @("ls-files", "--error-unmatch", "--", $path) -AllowFailure
    if ($tracked.ExitCode -eq 0) {
      $diff = Invoke-Git @("diff", "--no-ext-diff", "--no-color", "--binary", "--", $path) -AllowFailure
      Write-Host $diff.Output
    } else {
      Write-Host "--- nouveau fichier : $path"
      foreach ($line in ((Get-FileText $path) -split '\r?\n')) { Write-Host "+ $line" }
    }
  }
}

function Get-StagedPaths {
  $raw = (Invoke-Git @("diff", "--cached", "--name-only", "-z")).Output
  if (!$raw) { return @() }
  return @($raw.Split([char]0) | Where-Object { $_ })
}

function Assert-StagedSet([object]$Plan) {
  $staged = @(Get-StagedPaths | ForEach-Object { $_.Replace('\', '/') } | Sort-Object -Unique)
  $expected = @($Plan.Files | Sort-Object -Unique)
  if ($staged.Count -ne $expected.Count) { throw "Fichiers stages differents du manifeste." }
  for ($i = 0; $i -lt $staged.Count; $i++) {
    if (![string]::Equals($staged[$i], $expected[$i], [StringComparison]::OrdinalIgnoreCase)) { throw "Fichiers stages differents du manifeste." }
  }
}

function Start-Preview([object]$Plan) {
  $cached = Invoke-Git @("diff", "--cached", "--quiet") -AllowFailure
  if ($cached.ExitCode -ne 0) { throw "Index Git deja stage; l'apercu refuse de melanger le contenu stage au manifeste." }
  Test-ManifestFiles $Plan -RequireChanged
  Show-Context $Plan
  Write-Host "Apercu des fichiers du lot :"
  Show-CandidateDiff $Plan
  Write-Host "Aucun staging, commit ou push effectue."
}

function Start-Commit([object]$Plan) {
  $cached = Invoke-Git @("diff", "--cached", "--quiet") -AllowFailure
  if ($cached.ExitCode -ne 0) { throw "Index Git deja stage; termine ou annule ce lot avant de continuer." }
  Test-ManifestFiles $Plan -RequireChanged
  Show-Context $Plan
  Show-CandidateDiff $Plan
  if ((Read-Host "Taper STAGE pour preparer uniquement ces chemins") -cne "STAGE") { Write-Host "Annule; aucun fichier stage."; return }
  Invoke-Git (@("add", "--") + @($Plan.Files)) | Out-Null
  try {
    Assert-StagedSet $Plan
    Test-ManifestFiles $Plan
    $diff = Invoke-Git @("diff", "--cached", "--no-ext-diff", "--no-color", "--binary")
    $sensitiveDiff = Test-ContentBlocked $diff.Output
    if ($sensitiveDiff) { throw "Diff stage bloque : $sensitiveDiff." }
    Write-Host "Diff exact qui sera commis :"
    Write-Host $diff.Output
    if ((Read-Host "Pour creer ce commit local sur '$((Get-BranchName))', taper COMMIT") -cne "COMMIT") {
      Invoke-Git (@("reset", "--") + @($Plan.Files)) | Out-Null
      Write-Host "Annule; staging retire pour ces chemins."
      return
    }
    Invoke-Git @("commit", "-m", $Plan.Message) | Out-Null
    Write-Host "Commit local cree. Aucun push effectue."
  } catch {
    Add-LocalLog "Commit interrompu" "git commit (lot manifeste)" 1 $_.Exception.Message
    Write-Host "Les fichiers peuvent rester stages; inspecte-les avant toute nouvelle operation." -ForegroundColor Yellow
    throw
  }
}

function Start-Push([object]$Plan) {
  $status = (Invoke-Git @("status", "--porcelain", "--untracked-files=all")).Output
  if ((Invoke-Git @("diff", "--cached", "--quiet") -AllowFailure).ExitCode -ne 0) { throw "Index deja stage; push refuse." }
  if ($status.Trim()) {
    Write-Host "Changements locaux detectes (ils ne seront pas inclus dans le push) :"
    Write-Host $status
  }
  foreach ($path in $Plan.Files) {
    $pathStatus = (Invoke-Git @("status", "--porcelain", "--untracked-files=all", "--", $path)).Output
    if ($pathStatus.Trim()) { throw "Push refuse : un fichier du manifeste a change depuis le commit." }
  }
  $branch = Get-BranchName
  $upstream = Invoke-Git @("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}") -AllowFailure
  if ($upstream.ExitCode -ne 0) { throw "Branche sans upstream; push refuse." }
  $upstreamRef = $upstream.Output.Trim()
  $remoteResult = Invoke-Git @("config", "--get", "branch.$branch.remote") -AllowFailure
  $mergeResult = Invoke-Git @("config", "--get", "branch.$branch.merge") -AllowFailure
  if ($remoteResult.ExitCode -ne 0 -or $mergeResult.ExitCode -ne 0) { throw "Configuration upstream incomplete; push refuse." }
  $remote = $remoteResult.Output.Trim()
  $mergeRef = $mergeResult.Output.Trim()
  if ($mergeRef -notmatch '^refs/heads/[A-Za-z0-9._/-]+$' -or $mergeRef -match '\.\.') { throw "Branche distante invalide; push refuse." }
  $url = Protect-Text (Invoke-Git @("remote", "get-url", $remote)).Output.Trim()
  Write-Host "Branche : $branch | Destination : $remote / $mergeRef | URL : $url"
  if ((Read-Host "Taper FETCH pour actualiser l'amont avant l'aperçu") -cne "FETCH") { Write-Host "Annule; aucun fetch ni push."; return }
  Invoke-Git @("fetch", "--no-tags", $remote) | Out-Null
  $ahead = [int](Invoke-Git @("rev-list", "--count", "$upstreamRef..HEAD")).Output.Trim()
  if ($ahead -ne 1) { throw "Push bloque : $ahead commit(s) en avance; un seul lot est accepte." }
  $commits = Invoke-Git @("log", "--format=%h %s", "$upstreamRef..HEAD")
  Write-Host "Commit a publier :"
  Write-Host $commits.Output
  $paths = (Invoke-Git @("diff-tree", "--no-commit-id", "--name-only", "-r", "-z", "HEAD")).Output
  $actual = @($paths.Split([char]0) | Where-Object { $_ } | ForEach-Object { $_.Replace('\', '/') } | Sort-Object -Unique)
  $expected = @($Plan.Files | Sort-Object -Unique)
  if ($actual.Count -ne $expected.Count) { throw "Push bloque : fichiers du commit differents du manifeste." }
  for ($i = 0; $i -lt $actual.Count; $i++) {
    if (![string]::Equals($actual[$i], $expected[$i], [StringComparison]::OrdinalIgnoreCase)) { throw "Push bloque : fichiers du commit differents du manifeste." }
  }
  Write-Host "Les autres changements locaux restent exclus du commit a publier."
  Test-ManifestFiles $Plan
  $diff = Invoke-Git @("diff", "--no-ext-diff", "--no-color", "$upstreamRef..HEAD")
  Write-Host "Diff complet a publier :"
  Write-Host $diff.Output
  if ((Read-Host "Pour publier ce commit, taper PUSH") -cne "PUSH") { Write-Host "Annule; aucun push."; return }
  Invoke-Git @("push", "--porcelain", "--", $remote, "HEAD:$mergeRef") | Out-Null
  Write-Host "Push termine."
}

try {
  Initialize-Repository
  $plan = Get-Plan
  $selectedAction = $Action
  if ($selectedAction -eq 'Menu') {
    Write-Host ('Git Finalizer - ' + $script:RepoRoot)
    Write-Host '1. Apercu seulement'
    Write-Host '2. Preparer et confirmer un commit local'
    Write-Host '3. Examiner et confirmer un push'
    $choice = Read-Host 'Choisir 1, 2, 3 ou Q'
    if ($choice -eq '1') { $selectedAction = 'Preview' }
    elseif ($choice -eq '2') { $selectedAction = 'Commit' }
    elseif ($choice -eq '3') { $selectedAction = 'Push' }
    else { Write-Host 'Termine sans modifier Git.'; exit 0 }
  }
  Push-Location -LiteralPath $script:RepoRoot
  try {
    if ($selectedAction -eq 'Preview') { Start-Preview $plan }
    elseif ($selectedAction -eq 'Commit') { Start-Commit $plan }
    elseif ($selectedAction -eq 'Push') { Start-Push $plan }
  } finally { Pop-Location }
} catch {
  Write-Host ('ERREUR : ' + $_.Exception.Message) -ForegroundColor Red
  Add-LocalLog 'Action interrompue' ('Git Finalizer ' + $Action) 1 ($_.Exception.Message)
  exit 1
}
