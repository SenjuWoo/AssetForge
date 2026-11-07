#requires -Version 5.1
<#
Updates a Git checkout with --ff-only only. A dirty or diverged tree stops the
update before anything is changed; the working environment is then rebuilt by
Install.ps1 with its own rollback.
#>
[CmdletBinding()]
param([switch]$Check)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not (Test-Path -LiteralPath (Join-Path $Root '.git'))) {
    throw 'This is not a Git checkout. Download a release archive instead.'
}
$git = Get-Command git -ErrorAction SilentlyContinue
if (-not $git) { throw 'git is required to update a checkout.' }

& git -C $Root fetch --all --tags --prune
if ($LASTEXITCODE -ne 0) { throw 'git fetch failed; nothing was changed.' }

if ($Check) {
    & git -C $Root status -sb
    Write-Host 'Checked only. Re-run without -Check to update.'
    exit 0
}

& git -C $Root pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'Update was not fast-forward; the working tree was left unchanged.' }

& (Join-Path $Root 'Install.ps1')
