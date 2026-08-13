param(
    [switch]$ShowBrowser
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$logDirectory = Join-Path $projectRoot "data\logs"
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null

$mutex = New-Object System.Threading.Mutex($false, "Local\CSFlipperHourlyScrape")
if (-not $mutex.WaitOne(0)) {
    Write-Output "scrape_schedule=skipped reason=already_running"
    exit 0
}

try {
    Set-Location $projectRoot
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $logPath = Join-Path $logDirectory "hourly_scrape_$timestamp.log"
    $arguments = @(
        "-u",
        "-m",
        "apps.cli.auto_scrape_loop",
        "25",
        "--all-profiles",
        "--once",
        "--stale-minutes",
        "120",
        "--refresh-limit",
        "25",
        "--persist",
        "--steam"
    )
    $arguments += "--no-buff", "--no-refresh-buff"
    if ($ShowBrowser) {
        $arguments += "--show-browser"
    }

    "scrape_schedule=started at=$(Get-Date -Format o) source=steam" | Tee-Object -FilePath $logPath
    & python @arguments 2>&1 | Tee-Object -FilePath $logPath -Append
    exit $LASTEXITCODE
}
finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
