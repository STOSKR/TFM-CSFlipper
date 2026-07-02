param(
    [int]$WaitSeconds = 180
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$StatePath = Join-Path $RepoRoot "data\browser-state\buff163_storage_state.json"
if (Test-Path $StatePath) {
    $Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $BackupPath = Join-Path $RepoRoot "data\browser-state\buff163_storage_state_$Stamp.bak.json"
    Move-Item -LiteralPath $StatePath -Destination $BackupPath
    Write-Host "buff_state_backup=$BackupPath"
}

python -m apps.cli.scrape_candidate_platforms `
    --login-only `
    --no-steam `
    --buff `
    --show-browser `
    --login-wait $WaitSeconds

exit $LASTEXITCODE
