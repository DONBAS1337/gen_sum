param(
    [string]$ModDir = ""
)

$ErrorActionPreference = "Stop"

if (-not $ModDir) {
    $ModDir = Read-Host "Path to generative_summer mod folder"
}

$ModDir = (Resolve-Path $ModDir).Path
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Ready = Join-Path $Here "ready_replace"

foreach ($required in @("gs_backend.py", "gs_runtime.py", "gs_core.py", "generative_summer.rpy")) {
    if (-not (Test-Path (Join-Path $ModDir $required))) {
        throw "$required not found in $ModDir"
    }
}

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Backup = Join-Path $ModDir ("community_fix_backup_" + $Stamp)
New-Item -ItemType Directory -Path $Backup | Out-Null

$targets = @(
    "gs_backend.py", "gs_runtime.py", "gs_text_worker.py", "gs_core.py",
    "gs_source_7dl.py", "generative_summer.rpy",
    "gs_backend.pyo", "gs_runtime.pyo", "gs_core.pyo", "gs_source_7dl.pyo",
    "generative_summer.rpyc"
)

foreach ($name in $targets) {
    $path = Join-Path $ModDir $name
    if (Test-Path $path) {
        Copy-Item $path (Join-Path $Backup $name) -Force
    }
}

foreach ($name in @("gs_backend.py", "gs_runtime.py", "gs_text_worker.py", "gs_core.py", "gs_source_7dl.py", "generative_summer.rpy")) {
    Copy-Item (Join-Path $Ready $name) (Join-Path $ModDir $name) -Force
}

foreach ($name in @("gs_backend.pyo", "gs_runtime.pyo", "gs_core.pyo", "gs_source_7dl.pyo", "generative_summer.rpyc")) {
    $path = Join-Path $ModDir $name
    if (Test-Path $path) {
        Remove-Item $path -Force
    }
}

$curl = Get-Command curl.exe -ErrorAction SilentlyContinue
if ($curl) {
    Write-Host "curl.exe: OK -> $($curl.Source)"
} else {
    Write-Warning "curl.exe was not found. Text generation will not work with this patch."
}

$WorkshopGameDir = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $ModDir))
$SevenDays = Join-Path $WorkshopGameDir "3266357374"
if (Test-Path (Join-Path $SevenDays "scenario_alt")) {
    Write-Host "7DL Complete Edition: found -> $SevenDays"
} else {
    Write-Warning "7DL Complete Edition (Workshop 3266357374) was not found next to Generative Summer. Vanilla mode will still work."
}

Write-Host ""
Write-Host "Installed Generative Summer experimental 7DL + vanilla build."
Write-Host "Backup: $Backup"
Write-Host "If Steam Workshop updates the mod, re-apply this patch."
