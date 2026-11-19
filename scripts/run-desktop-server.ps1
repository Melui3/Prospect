param(
  [ValidateRange(1024, 65535)]
  [int]$Port = 8765
)

# Keep the old entry point on the same window and service lifecycle.
& (Join-Path $PSScriptRoot "Start-Prospect.ps1") -Port $Port
