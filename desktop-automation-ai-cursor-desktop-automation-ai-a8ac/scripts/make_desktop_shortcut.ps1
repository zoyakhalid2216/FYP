param(
  [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = "SilentlyContinue"
$ProjectRoot = (Resolve-Path $ProjectRoot).Path
$src = Join-Path $ProjectRoot "Run Automate AI.bat"

if (-not (Test-Path $src)) {
  Write-Host "Missing launcher: $src"
  exit 1
}

$desks = New-Object System.Collections.Generic.List[string]
foreach ($d in @(
  [Environment]::GetFolderPath("Desktop"),
  (Join-Path $env:USERPROFILE "Desktop"),
  (Join-Path $env:USERPROFILE "OneDrive\Desktop"),
  (Join-Path $env:PUBLIC "Desktop")
)) {
  if ($d -and (Test-Path $d)) { [void]$desks.Add($d) }
}

Get-ChildItem -Path (Join-Path $env:USERPROFILE "OneDrive*") -Directory -ErrorAction SilentlyContinue | ForEach-Object {
  $candidate = Join-Path $_.FullName "Desktop"
  if (Test-Path $candidate) { [void]$desks.Add($candidate) }
}

$desks = $desks | Select-Object -Unique
$ws = New-Object -ComObject WScript.Shell

foreach ($desk in $desks) {
  $lnkPath = Join-Path $desk "Automate AI.lnk"
  $sc = $ws.CreateShortcut($lnkPath)
  $sc.TargetPath = $src
  $sc.WorkingDirectory = $ProjectRoot
  $sc.WindowStyle = 1
  $sc.Description = "AI Desktop Automation"
  $sc.Save()
  Copy-Item -Force $src (Join-Path $desk "Automate AI.bat")
  Write-Host "Created: $lnkPath"
  Write-Host "Created: $(Join-Path $desk 'Automate AI.bat')"
}

if ($desks.Count -eq 0) {
  Write-Host "No Desktop folder found."
  exit 1
}
