param([string]$StatusPath, [int]$OwnerProcessId)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
try { $owner = [Diagnostics.Process]::GetProcessById($OwnerProcessId) } catch { exit }
$form = New-Object Windows.Forms.Form
$form.Text = 'Prospect - Demarrage'
$form.ClientSize = New-Object Drawing.Size(400, 130)
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.ControlBox = $false
$form.TopMost = $true
$form.BackColor = [Drawing.ColorTranslator]::FromHtml('#0D0D0D')
$form.ForeColor = [Drawing.ColorTranslator]::FromHtml('#EFE5D2')
$label = New-Object Windows.Forms.Label
$label.Location = New-Object Drawing.Point(22, 18)
$label.Size = New-Object Drawing.Size(356, 65)
$label.Font = New-Object Drawing.Font('Segoe UI', 11)
$label.Text = "Prospect demarre...`r`nPreparation de l'application."
$form.Controls.Add($label)
$bar = New-Object Windows.Forms.ProgressBar
$bar.Location = New-Object Drawing.Point(22, 94)
$bar.Size = New-Object Drawing.Size(356, 8)
$bar.Style = 'Marquee'
$form.Controls.Add($bar)
$timer = New-Object Windows.Forms.Timer
$timer.Interval = 200
$script:lastState = ''
$timer.Add_Tick({
  if ($owner.HasExited -or !(Test-Path -LiteralPath $StatusPath)) { $form.Close(); return }
  try {
    $state = [IO.File]::ReadAllText($StatusPath)
    if ($state -eq 'CLOSE') { $form.Close(); return }
    # PowerShell starts hidden; explicitly show the form after its first native show.
    if (!$script:lastState) { $form.Hide(); $form.Show() }
    if ($state -and $state -ne $script:lastState) {
      $script:lastState = $state
      $label.Text = "Prospect demarre...`r`n$state"
      $form.Activate()
    }
  } catch [IO.IOException] { }
})
$timer.Start()
try { [Windows.Forms.Application]::Run($form) }
finally { $timer.Stop(); $timer.Dispose(); $form.Dispose(); $owner.Dispose() }
