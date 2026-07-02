param(
    [int]$ScrapeEveryHours = 8,
    [string]$ScrapeStartTime = "09:00",
    [int]$WebPort = 8000
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$PowerShell = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$ScrapeScript = Join-Path $RepoRoot "scripts\local_stream_scrape.ps1"
$WebScript = Join-Path $RepoRoot "scripts\start_web_dashboard.ps1"

$ScrapeTask = "CSFlipper Local Scrape"
$WebTask = "CSFlipper Web Dashboard"

$ScrapeArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$ScrapeScript`""
$WebArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$WebScript`" -Port $WebPort"

schtasks /Create /F /TN $ScrapeTask /SC HOURLY /MO $ScrapeEveryHours /ST $ScrapeStartTime /TR "`"$PowerShell`" $ScrapeArgs" | Out-Host
schtasks /Create /F /TN $WebTask /SC ONLOGON /TR "`"$PowerShell`" $WebArgs" | Out-Host

Write-Host "automation_installed=true"
Write-Host "scrape_task=$ScrapeTask every_hours=$ScrapeEveryHours start_time=$ScrapeStartTime"
Write-Host "web_task=$WebTask url=http://localhost:$WebPort"
