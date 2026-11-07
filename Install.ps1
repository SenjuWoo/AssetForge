#requires -Version 5.1
<#
Creates a repo-local virtual environment and verifies the CLI. It writes only
inside this folder, uses a .pth file instead of a network install, and keeps the
previous environment if the new one fails its doctor check.
#>
[CmdletBinding()]
param(
    [switch]$Force,
    [switch]$WithImages
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Version = (Get-Content -LiteralPath (Join-Path $Root 'VERSION') -Raw).Trim()
Write-Host "AssetForge $Version installer"
Write-Host "root: $Root"

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    throw 'Python 3.10+ is required and was not found on PATH.'
}
& python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)"
if ($LASTEXITCODE -ne 0) {
    throw 'Python 3.10 or newer is required.'
}

$venv = Join-Path $Root '.venv'
$stage = Join-Path $Root '.venv.new'
$previous = Join-Path $Root '.venv.prev'
if (Test-Path -LiteralPath $stage) {
    Remove-Item -LiteralPath $stage -Recurse -Force
}

& python -m venv $stage --system-site-packages
if ($LASTEXITCODE -ne 0) { throw 'Could not create the virtual environment.' }

$stagePython = Join-Path $stage 'Scripts\python.exe'
$pth = Join-Path $stage 'Lib\site-packages\assetforge-src.pth'
Set-Content -LiteralPath $pth -Value (Join-Path $Root 'src') -Encoding ASCII

if ($WithImages) {
    & $stagePython -m pip install --disable-pip-version-check "Pillow>=10"
    if ($LASTEXITCODE -ne 0) { throw 'Pillow installation failed.' }
}

$doctor = & $stagePython -m assetforge doctor --json
if ($LASTEXITCODE -ne 0) {
    Write-Host $doctor
    throw 'The staged environment failed doctor; the previous environment was kept.'
}
$pythonVersion = (& $stagePython -c "import sys; print(sys.version.split()[0])").Trim()

if (Test-Path -LiteralPath $venv) {
    if (Test-Path -LiteralPath $previous) {
        Remove-Item -LiteralPath $previous -Recurse -Force
    }
    Rename-Item -LiteralPath $venv -NewName '.venv.prev'
}
Rename-Item -LiteralPath $stage -NewName '.venv'

$state = [ordered]@{
    version     = $Version
    python      = $pythonVersion
    installed   = (Get-Date).ToString('o')
    with_images = [bool]$WithImages
}
$state | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Root 'INSTALLATION.json') -Encoding UTF8

Write-Host "Installed AssetForge $Version."
Write-Host "Run: $Root\assetforge.cmd doctor"
