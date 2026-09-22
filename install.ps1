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

if (-not (Test-Path (Join-Path $ModDir "gs_backend.py"))) {
    throw "gs_backend.py not found in $ModDir"
}
if (-not (Test-Path (Join-Path $ModDir "gs_runtime.py"))) {
    throw "gs_runtime.py not found in $ModDir"
}

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Backup = Join-Path $ModDir ("community_fix_backup_" + $Stamp)
New-Item -ItemType Directory -Path $Backup | Out-Null

$targets = @("gs_backend.py", "gs_runtime.py", "gs_text_worker.py",
             "gs_backend.pyo", "gs_runtime.pyo")

foreach ($name in $targets) {
    $path = Join-Path $ModDir $name
    if (Test-Path $path) {
        Copy-Item $path (Join-Path $Backup $name) -Force
    }
}

Copy-Item (Join-Path $Ready "gs_backend.py") (Join-Path $ModDir "gs_backend.py") -Force
Copy-Item (Join-Path $Ready "gs_runtime.py") (Join-Path $ModDir "gs_runtime.py") -Force
Copy-Item (Join-Path $Ready "gs_text_worker.py") (Join-Path $ModDir "gs_text_worker.py") -Force

foreach ($name in @("gs_backend.pyo", "gs_runtime.pyo")) {
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

Write-Host ""
Write-Host "Installed Generative Summer community fix."
Write-Host "Backup: $Backup"
Write-Host "Keep gs_core.py unchanged."
Write-Host "If Steam Workshop updates the mod, re-apply this patch."
