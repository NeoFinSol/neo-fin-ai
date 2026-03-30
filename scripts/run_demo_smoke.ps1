param(
    [string]$ApiBaseUrl = "http://localhost",
    [string]$ApiPrefix = "/api",
    [string]$ApiKey = "",
    [string]$ManifestPath = "tests/data/demo_manifest.json",
    [switch]$NoBuild,
    [switch]$SkipHistoryCheck
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ApiKey)) {
    $ApiKey = $env:API_KEY
}

if ([string]::IsNullOrWhiteSpace($ApiKey)) {
    throw "API key is required. Pass -ApiKey or set API_KEY environment variable."
}

if (-not $NoBuild) {
    docker compose up -d --build
} else {
    docker compose up -d
}

$args = @(
    "scripts/demo_smoke.py",
    "--base-url", $ApiBaseUrl,
    "--api-prefix", $ApiPrefix,
    "--api-key", $ApiKey,
    "--manifest", $ManifestPath
)

if ($SkipHistoryCheck) {
    $args += "--skip-history-check"
}

python @args
