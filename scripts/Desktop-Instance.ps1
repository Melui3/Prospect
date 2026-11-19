function Get-ProspectInstanceName($Root, $QA) {
  $sha = [Security.Cryptography.SHA256]::Create()
  try {
    $pathBytes = [Text.Encoding]::UTF8.GetBytes($Root.ToUpperInvariant())
    $hash = [BitConverter]::ToString($sha.ComputeHash($pathBytes)).Replace("-", "")
    $user = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    return "Local\Prospect-$user-$hash-$([bool]$QA)"
  } finally {
    $sha.Dispose()
  }
}
