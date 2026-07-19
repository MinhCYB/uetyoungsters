[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet(
        "help", "start", "stop", "restart", "rebuild", "status", "logs",
        "crawl", "pipeline", "translate", "refresh-data", "publish", "test"
    )]
    [string]$Command = "help",

    [Parameter(Position = 1)]
    [ValidateSet("all", "backend-api", "ai-worker-service", "crawl-service", "frontend", "nginx", "db", "redis", "roadmap-service")]
    [string]$Service = "all"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

function Write-Step([string]$Message) {
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Invoke-Compose {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$ComposeArguments)
    & docker compose @ComposeArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose failed (exit code $LASTEXITCODE): docker compose $($ComposeArguments -join ' ')"
    }
}

function Invoke-ComposeLogged {
    param(
        [string]$StepName,
        [string[]]$ComposeArguments,
        [string]$LogPath
    )
    $startedAt = Get-Date
    Write-Host "    Running... details: $LogPath" -ForegroundColor DarkGray
    # Docker Compose writes normal container status messages to stderr.
    # PowerShell 5 turns redirected native stderr into ErrorRecord objects, so
    # temporarily relax error handling and trust Docker's actual exit code.
    $previousErrorPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & docker compose @ComposeArguments 2>&1 | Out-File -FilePath $LogPath -Append -Encoding utf8
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorPreference
    }
    $elapsed = (Get-Date) - $startedAt
    if ($exitCode -ne 0) {
        Write-Host "`nLast log lines:" -ForegroundColor Red
        Get-Content $LogPath -Tail 30 | Write-Host
        throw "$StepName failed after $([math]::Round($elapsed.TotalSeconds))s (exit code $exitCode). See $LogPath"
    }
    Write-Host "    Done in $([math]::Round($elapsed.TotalSeconds))s" -ForegroundColor Green
}

function Assert-Prerequisites {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker is not installed or is not available in PATH."
    }
    & docker info *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Desktop is not running. Start Docker Desktop and try again."
    }
    if (-not (Test-Path ".env")) {
        throw "Missing .env. Run: Copy-Item .env.example .env, then set GEMINI_API_KEY."
    }
}

function Start-System([switch]$Build) {
    Write-Step $(if ($Build) { "Build and start the whole system" } else { "Start the whole system" })
    if ($Build) {
        Invoke-Compose -ComposeArguments @("up", "-d", "--build")
    } else {
        Invoke-Compose -ComposeArguments @("up", "-d")
    }
    Invoke-Compose -ComposeArguments @("ps")
    Write-Host "`nApplication: http://localhost" -ForegroundColor Green
    Write-Host "Backend API: http://localhost:8000"
}

function Run-Pipeline {
    Write-Step "Normalize data and publish it to PostgreSQL"
    Invoke-Compose -ComposeArguments @("run", "--rm", "crawl-service", "pipeline")
}

function Show-Help {
    @"
Career Compass development helper

Usage:
  .\scripts\dev.ps1 <command> [service]

Commands:
  start                 Start existing containers
  rebuild               Build images and start the whole system
  restart [service]     Restart all services or one service
  stop                  Stop containers but retain PostgreSQL data
  status                Show container status and crawl-service status
  logs [service]        Follow logs for all services or one service
  crawl                 Collect Greenhouse, ViecOi and O*NET data
  pipeline              Normalize existing data and publish PostgreSQL
  translate             Translate changed O*NET career content with Gemini
  refresh-data          Full manual refresh: crawl, pipeline, translate, pipeline
  publish               Republish existing processed files to PostgreSQL
  test                  Run the local Python test suite
  help                  Show this help

Common workflows:
  .\scripts\dev.ps1 rebuild
  .\scripts\dev.ps1 refresh-data
  .\scripts\dev.ps1 logs ai-worker-service

The refresh-data command is intentionally scheduler-friendly, but this script
does not create or enable a recurring schedule.
"@ | Write-Host
}

if ($Command -eq "help") {
    Show-Help
    exit 0
}

Assert-Prerequisites

switch ($Command) {
    "start" {
        Start-System
    }
    "rebuild" {
        Start-System -Build
    }
    "restart" {
        Write-Step "Restart $Service"
        if ($Service -eq "all") { Invoke-Compose -ComposeArguments @("restart") } else { Invoke-Compose -ComposeArguments @("restart", $Service) }
    }
    "stop" {
        Write-Step "Stop the system (database volume is retained)"
        Invoke-Compose -ComposeArguments @("down")
    }
    "status" {
        Write-Step "Container status"
        Invoke-Compose -ComposeArguments @("ps")
        Write-Step "Crawl-service status"
        Invoke-Compose -ComposeArguments @("run", "--rm", "crawl-service", "status")
    }
    "logs" {
        Write-Step "Follow logs for $Service (Ctrl+C to exit)"
        if ($Service -eq "all") { Invoke-Compose -ComposeArguments @("logs", "-f", "--tail", "150") } else { Invoke-Compose -ComposeArguments @("logs", "-f", "--tail", "150", $Service) }
    }
    "crawl" {
        Write-Step "Collect Greenhouse, ViecOi and O*NET"
        Invoke-Compose -ComposeArguments @("run", "--rm", "crawl-service", "collect-all")
    }
    "pipeline" {
        Run-Pipeline
    }
    "translate" {
        Write-Step "Start AI worker"
        Invoke-Compose -ComposeArguments @("up", "-d", "ai-worker-service")
        Write-Step "Translate changed career content"
        Invoke-Compose -ComposeArguments @("run", "--rm", "crawl-service", "enrich-onet-vi")
    }
    "refresh-data" {
        $refreshLog = Join-Path $ProjectRoot "reports\refresh-data.log"
        New-Item -ItemType Directory -Path (Split-Path -Parent $refreshLog) -Force | Out-Null
        "Career Compass data refresh started at $((Get-Date).ToString('o'))" | Set-Content $refreshLog
        Write-Step "Collect all configured sources"
        Invoke-ComposeLogged -StepName "Collection" -ComposeArguments @("run", "--rm", "crawl-service", "collect-all") -LogPath $refreshLog
        Write-Step "Normalize data and publish it to PostgreSQL"
        Invoke-ComposeLogged -StepName "Pipeline" -ComposeArguments @("run", "--rm", "crawl-service", "pipeline") -LogPath $refreshLog
        Write-Step "Start AI worker"
        Invoke-ComposeLogged -StepName "AI worker startup" -ComposeArguments @("up", "-d", "ai-worker-service") -LogPath $refreshLog
        Write-Step "Translate only changed career content"
        Invoke-ComposeLogged -StepName "Translation" -ComposeArguments @("run", "--rm", "crawl-service", "enrich-onet-vi") -LogPath $refreshLog
        Write-Step "Publish translated profiles"
        Invoke-ComposeLogged -StepName "Final pipeline" -ComposeArguments @("run", "--rm", "crawl-service", "pipeline") -LogPath $refreshLog
        Write-Host "`nData refresh completed. This command has finished." -ForegroundColor Green
        Write-Host "Application services remain running intentionally. Use '.\scripts\dev.ps1 stop' to stop them."
        Write-Host "Full log: $refreshLog" -ForegroundColor DarkGray
    }
    "publish" {
        Write-Step "Republish processed data to PostgreSQL"
        Invoke-Compose -ComposeArguments @("run", "--rm", "crawl-service", "publish-db")
    }
    "test" {
        Write-Step "Run tests"
        & pytest -q
        if ($LASTEXITCODE -ne 0) { throw "Tests failed with exit code $LASTEXITCODE." }
    }
}

exit 0
