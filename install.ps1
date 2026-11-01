# DON-GEN standalone installer for Everlasting Summer.
# Compatible with Windows PowerShell 5.1 and PowerShell 7+.
# Writes ONLY to game/mods/don_gen. Existing mods remain untouched.
param(
    [string]$GameDir = "",
    [string]$AssetsDir = ""
)

$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Source = Join-Path $Here "don_gen"

if (-not (Test-Path -LiteralPath (Join-Path $Source "don_gen.rpy") -PathType Leaf)) {
    throw "DON-GEN sources not found: $Source"
}
if (-not $GameDir) {
    $GameDir = Read-Host "Path to Everlasting Summer (root or game folder)"
}
$InputDir = (Resolve-Path -LiteralPath $GameDir -ErrorAction Stop).Path
if ((Split-Path -Leaf $InputDir) -ieq "game") {
    $Game = $InputDir
} else {
    $Game = Join-Path $InputDir "game"
}
if (-not (Test-Path -LiteralPath (Join-Path $Game "archive.rpa") -PathType Leaf)) {
    throw "Everlasting Summer game/archive.rpa was not found in: $Game"
}

# Validate the optional local asset pack BEFORE touching the installed game.
$Maps = $null
$AssetsRoot = $null
if ($AssetsDir) {
    $AssetInput = (Resolve-Path -LiteralPath $AssetsDir -ErrorAction Stop).Path
    if ((Split-Path -Leaf $AssetInput) -ieq "maps") {
        $Maps = $AssetInput
        $AssetsRoot = Split-Path -Parent $AssetInput
    } else {
        $AssetsRoot = $AssetInput
        $Maps = Join-Path $AssetsRoot "maps"
    }
    if (-not (Test-Path -LiteralPath (Join-Path $Maps "map_default.png") -PathType Leaf)) {
        throw "Missing map_default.png in assets pack: $Maps"
    }
}

$Mods = Join-Path $Game "mods"
New-Item -ItemType Directory -Force -Path $Mods | Out-Null
$Dest = Join-Path $Mods "don_gen"

if (Test-Path -LiteralPath $Dest) {
    # Keep backups OUTSIDE game/, where Ren'Py must never load stale .rpy files.
    $BackupRoot = Join-Path (Split-Path -Parent $Game) "DON-GEN-backups"
    New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null
    $Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $Backup = Join-Path $BackupRoot ("don_gen_" + $Stamp + "_" + [guid]::NewGuid().ToString("N").Substring(0, 6))
    Copy-Item -LiteralPath $Dest -Destination $Backup -Force -Recurse
    Write-Host "DON-GEN backup: $Backup"
} else {
    New-Item -ItemType Directory -Force -Path $Dest | Out-Null
}

# Overlay new scripts/assets but preserve user-supplied workflow JSON and
# optional private images already installed inside the DON-GEN folder.
Copy-Item -Path (Join-Path $Source "*") -Destination $Dest -Force -Recurse

if ($Maps) {
    $AssetsOut = Join-Path (Join-Path $Dest "images") "gen_assets"
    New-Item -ItemType Directory -Force -Path $AssetsOut | Out-Null

    foreach ($Name in @("map_default.png", "map_bg.jpg", "7dl_bg.jpg", "map_selected.png", "map_available.png")) {
        $File = Join-Path $Maps $Name
        if (Test-Path -LiteralPath $File -PathType Leaf) {
            Copy-Item -LiteralPath $File -Destination $AssetsOut -Force
        }
    }
    Get-ChildItem -LiteralPath $Maps -File -Filter "map_icon_*.png" |
        Copy-Item -Destination $AssetsOut -Force

    # Optional curated CGs. Import only filenames listed in cg_index.json;
    # do not copy the full private CG library. No GitHub credentials needed.
    $IndexPath = Join-Path $AssetsRoot "cg_index.json"
    if (Test-Path -LiteralPath $IndexPath -PathType Leaf) {
        $Manifest = Get-Content -LiteralPath $IndexPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($null -eq $Manifest -or $Manifest -isnot [pscustomobject]) {
            throw "cg_index.json must be an object mapping scene IDs to paths"
        }
        $CGSource = Join-Path $AssetsRoot "cg"
        $CGOut = Join-Path $AssetsOut "cg"
        New-Item -ItemType Directory -Force -Path $CGOut | Out-Null

        foreach ($Entry in $Manifest.PSObject.Properties) {
            $Relative = [string]$Entry.Value
            if ($Relative -match '^mods/don_gen/images/gen_assets/cg/([A-Za-z0-9_-]+\.(png|jpg|jpeg))$') {
                $FileName = $Matches[1]
                $File = Join-Path $CGSource $FileName
                if (Test-Path -LiteralPath $File -PathType Leaf) {
                    Copy-Item -LiteralPath $File -Destination $CGOut -Force
                } else {
                    Write-Warning "Curated CG file not found: $File"
                }
            } else {
                Write-Warning "Skipped invalid CG mapping: $Relative"
            }
        }
        Copy-Item -LiteralPath $IndexPath -Destination (Join-Path $AssetsOut "cg_index.json") -Force
        Write-Host "Curated CG import completed."
    }
    Write-Host "Map and character icons imported from: $Maps"
}

# Clean ONLY compiled DON-GEN scripts, not other mods or save data.
Get-ChildItem -LiteralPath $Dest -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Extension -in @(".rpyc", ".pyo", ".pyc") } |
    Remove-Item -Force

Write-Host ""
Write-Host "DON-GEN installed: $Dest"
Write-Host "No other mods were modified."
Write-Host "Offline RPG features do not require ChatGPT or ComfyUI."
Write-Host "Local image generation requires a running ComfyUI at 127.0.0.1:8188."
