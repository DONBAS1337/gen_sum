# DON-GEN standalone installer for Everlasting Summer (Windows PowerShell 5.1+).
# Copies ONLY the don_gen directory. Never writes into any other mod.
param(
    [string]$GameDir = "",
    [string]$AssetsDir = ""
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

# Private gen_assets repository: import ONLY map + character-pin files from an
# explicit local checkout. Never download using a token and never copy large CGs.
if ($AssetsDir) {
    $Root = (Resolve-Path -LiteralPath $AssetsDir -ErrorAction Stop).Path
    $Maps = Join-Path $Root "maps"
    if ((Split-Path -Leaf $Root) -ieq "maps") { $Maps = $Root }
    if (-not (Test-Path -LiteralPath (Join-Path $Maps "map_default.png"))) {
        throw "No maps/map_default.png in AssetsDir: $Root"
    }
    $AssetsOut = Join-Path (Join-Path $Dest "images") "gen_assets"
    New-Item -ItemType Directory -Force -Path $AssetsOut | Out-Null
    $MapNames = @("map_default.png", "map_bg.jpg", "7dl_bg.jpg",
                  "map_selected.png", "map_available.png")
    foreach ($Name in $MapNames) {
        $File = Join-Path $Maps $Name
        if (Test-Path -LiteralPath $File) {
            Copy-Item -LiteralPath $File -Destination $AssetsOut -Force
        }
    }
    Get-ChildItem -LiteralPath $Maps -File -Filter "map_icon_*.png" |
        Copy-Item -Destination $AssetsOut -Force
    # Optional explicit CG mapping. Only referenced files are copied,
    # never the whole potentially huge CG library.
    $IndexPath = Join-Path $Root "cg_index.json"
    if (Test-Path -LiteralPath $IndexPath) {
        $Manifest = Get-Content -LiteralPath $IndexPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $CGSource = Join-Path $Root "cg"
        $CGOut = Join-Path $AssetsOut "cg"
        New-Item -ItemType Directory -Force -Path $CGOut | Out-Null
        foreach ($Entry in $Manifest.PSObject.Properties) {
            $Relative = [string]$Entry.Value
            if ($Relative -match '^mods/don_gen/images/gen_assets/cg/([A-Za-z0-9_-]+\.(png|jpg|jpeg))
}
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
) {
                $FileName = $Matches[1]
                $File = Join-Path $CGSource $FileName
                if (Test-Path -LiteralPath $File) {
                    Copy-Item -LiteralPath $File -Destination $CGOut -Force
                }
            }
        }
        Copy-Item -LiteralPath $IndexPath -Destination (Join-Path $AssetsOut "cg_index.json") -Force
        Write-Host "Curated CG index imported. Missing CGs remain available for on-demand generation."
    }
    Write-Host "gen_assets maps imported from: $Maps"
}
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
