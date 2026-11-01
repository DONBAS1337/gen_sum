# DON-GEN standalone installer for Everlasting Summer (Windows PowerShell 5.1+).
# Copies ONLY the don_gen directory. Never writes into any other mod.
param(
    [string]$GameDir = ""
)

$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Source = Join-Path $Here "don_gen"

if (-not (Test-Path (Join-Path $Source "don_gen.rpy"))) {
    throw "DON-GEN sources not found at: $Source"
}
if (-not $GameDir) {
    $GameDir = Read-Host "Path to Everlasting Summer root (or game subfolder)"
}
$InputDir = (Resolve-Path -LiteralPath $GameDir -ErrorAction Stop).Path
if ((Split-Path -Leaf $InputDir) -ieq "game") {
    $Game = $InputDir
} else {
    $Game = Join-Path $InputDir "game"
}
if (-not (Test-Path -LiteralPath (Join-Path $Game "archive.rpa"))) {
    throw "Everlasting Summer archive.rpa not found in: $Game"
}

$Mods = Join-Path $Game "mods"
if (-not (Test-Path -LiteralPath $Mods)) {
    New-Item -ItemType Directory -Path $Mods | Out-Null
}
$Dest = Join-Path $Mods "don_gen"
if (Test-Path -LiteralPath $Dest) {
    # Backups must be OUTSIDE game/, otherwise Ren'Py could load duplicate scripts.
    $Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $BackupRoot = Join-Path (Split-Path -Parent $Game) "DON-GEN-backups"
    New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
    $Backup = Join-Path $BackupRoot ("don_gen_" + $Stamp)
    Copy-Item -LiteralPath $Dest -Destination $Backup -Recurse -Force
    Write-Host "Existing DON-GEN backup: $Backup"
} else {
    New-Item -ItemType Directory -Path $Dest | Out-Null
}

Copy-Item -Path (Join-Path $Source "*") -Destination $Dest -Force -Recurse
# Remove only DON-GEN bytecode. Old Ren'Py bytecode can shadow updated .rpy/.py.
Get-ChildItem -LiteralPath $Dest -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Extension -in @(".rpyc", ".pyo", ".pyc") } |
    Remove-Item -Force

Write-Host ""
Write-Host "DON-GEN installed: $Dest"
Write-Host "The game menu should show: DON-GEN"
Write-Host "No Generative Summer Workshop files were changed."
Write-Host "For offline RPG play, ChatGPT, Python 3 and curl.exe are NOT needed."
Write-Host "AI requests still require ChatGPT sign-in, system Python 3 and curl.exe on Windows."
