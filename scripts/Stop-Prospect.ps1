param([switch]$QA)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Desktop-Instance.ps1")
$name = Get-ProspectInstanceName (Split-Path -Parent $PSScriptRoot) $QA
try {
  $stop = [Threading.EventWaitHandle]::OpenExisting("$name-stop")
} catch [Threading.WaitHandleCannotBeOpenedException] {
  Write-Host "Aucune instance geree par le lanceur Prospect."
  return
}
try {
  $null = $stop.Set()
  Write-Host "Arret demande. Prospect termine le traitement en cours."
} finally {
  $stop.Dispose()
}
