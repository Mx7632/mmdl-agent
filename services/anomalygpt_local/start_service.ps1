param(
    [string]$RepoDir,
    [string]$Host = "127.0.0.1",
    [int]$Port = 9001
)

if (-not $RepoDir) {
    Write-Error "Please provide -RepoDir pointing to your local AnomalyGPT repository."
    exit 1
}

$env:ANOMALYGPT_SERVICE_REPO_DIR = $RepoDir
$env:ANOMALYGPT_SERVICE_HOST = $Host
$env:ANOMALYGPT_SERVICE_PORT = "$Port"

python -m uvicorn services.anomalygpt_local.app:app --host $Host --port $Port
