Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

New-Item -ItemType Directory -Force -Path (Join-Path $RepoRoot "logs") | Out-Null
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogPath = Join-Path $RepoRoot "logs\local_stream_scrape_$Stamp.log"

python -m apps.cli.render_stream_scrape --refresh *>&1 | Tee-Object -FilePath $LogPath
$ScrapeExitCode = $LASTEXITCODE
if ($ScrapeExitCode -ne 0) {
    exit $ScrapeExitCode
}

python -m apps.cli.score_live_opportunities *>&1 | Tee-Object -FilePath $LogPath -Append
exit $LASTEXITCODE
