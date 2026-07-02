param(
    [int]$Port = 8000
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Existing = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($Existing) {
    Write-Host "web_dashboard_already_running port=$Port"
    exit 0
}

New-Item -ItemType Directory -Force -Path (Join-Path $RepoRoot "logs") | Out-Null
$LogPath = Join-Path $RepoRoot "logs\web_dashboard_server.log"

python -m apps.cli.web_dashboard_server --host 127.0.0.1 --port $Port *>&1 |
    Tee-Object -FilePath $LogPath -Append

exit $LASTEXITCODE
