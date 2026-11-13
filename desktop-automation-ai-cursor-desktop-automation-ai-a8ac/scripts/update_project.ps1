# Updates this Automate AI folder from git, a Downloads ZIP, or GitHub.
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

function Write-Log([string]$msg) {
    Write-Host $msg
    $logDir = Join-Path $Root "data\logs"
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
    Add-Content -Path (Join-Path $logDir "last_update.txt") -Value ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $msg)
}

function Find-DownloadedZip {
    $places = @(
        (Join-Path $env:USERPROFILE "Downloads"),
        [Environment]::GetFolderPath("Desktop"),
        (Join-Path $env:USERPROFILE "Desktop"),
        (Join-Path $env:USERPROFILE "OneDrive\Desktop")
    )
    $hits = @()
    foreach ($place in $places) {
        if (-not (Test-Path $place)) { continue }
        $hits += Get-ChildItem -Path $place -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match "desktop-automation-ai.*\.zip$" }
    }
    if (-not $hits) { return $null }
    return $hits | Sort-Object LastWriteTime -Descending | Select-Object -First 1
}

function Install-FromZip([string]$zipPath) {
    Write-Log "Using ZIP: $zipPath"
    $tmp = Join-Path $env:TEMP "automate-ai-update-src"
    if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
    Expand-Archive -Path $zipPath -DestinationPath $tmp -Force
    $src = Get-ChildItem $tmp -Directory | Select-Object -First 1
    if (-not $src) { throw "ZIP did not contain a project folder." }
    Write-Log "Copying files from $($src.Name) ..."
    Get-ChildItem -Path $src.FullName -Force | ForEach-Object {
        if ($_.Name -in @(".venv", "data", ".git")) { return }
        Copy-Item -Path $_.FullName -Destination (Join-Path $Root $_.Name) -Recurse -Force
    }
    Write-Log "Files copied."
}

Write-Host ""
Write-Host "========================================================"
Write-Host " Automate AI updater"
Write-Host " Folder: $Root"
Write-Host "========================================================"
Write-Host ""

if (-not (Test-Path (Join-Path $Root "main.py"))) {
    throw "This updater is not inside the Automate AI project folder (main.py missing)."
}

$updated = $false
$git = Get-Command git -ErrorAction SilentlyContinue
if ($git -and (Test-Path (Join-Path $Root ".git"))) {
    Write-Log "[1] Git folder found — fetching cursor/desktop-automation-ai-a8ac ..."
    $env:GIT_TERMINAL_PROMPT = "0"
    try {
        & git -c credential.helper= fetch --depth 1 origin cursor/desktop-automation-ai-a8ac
        if ($LASTEXITCODE -eq 0) {
            & git checkout -B cursor/desktop-automation-ai-a8ac origin/cursor/desktop-automation-ai-a8ac
            if ($LASTEXITCODE -eq 0) { $updated = $true }
        }
    } catch {
        Write-Log "Git fetch failed (normal for a private repo without login)."
    }
}

if (-not $updated) {
    $zip = Find-DownloadedZip
    if ($zip) {
        Write-Log "[1] Found a downloaded ZIP dated $($zip.LastWriteTime)"
        Install-FromZip $zip.FullName
        $updated = $true
    }
}

if (-not $updated) {
    Write-Host ""
    Write-Host "Could not pull from GitHub automatically."
    Write-Host "The repo is PRIVATE, so double-click update cannot download it."
    Write-Host ""
    Write-Host "Do this now (takes one minute):"
    Write-Host "  1. Chrome must be logged into GitHub"
    Write-Host "  2. A browser tab will open on the correct branch"
    Write-Host "  3. Click the green Code button -> Download ZIP"
    Write-Host "  4. Wait for the download to finish"
    Write-Host "  5. Come back to THIS window and press Enter"
    Write-Host ""
    $branchUrl = "https://github.com/muneeb-267/desktop-automation-ai/tree/cursor/desktop-automation-ai-a8ac"
    Start-Process $branchUrl
    Read-Host "Press Enter after the ZIP has finished downloading"
    $zip = Find-DownloadedZip
    if (-not $zip) {
        throw "No desktop-automation-ai ZIP found in Downloads or Desktop. Download it while logged into GitHub, then run this again."
    }
    Install-FromZip $zip.FullName
    $updated = $true
}

$cfg = Join-Path $Root "config\default.yaml"
if (Test-Path $cfg) {
    $ver = Select-String -Path $cfg -Pattern 'version:\s*"([^"]+)"' | Select-Object -First 1
    if ($ver) { Write-Log ("Now running version: " + $ver.Matches[0].Groups[1].Value) }
}

Write-Log "Update step finished."
exit 0
