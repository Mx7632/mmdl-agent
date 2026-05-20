param(
    [string]$RepoDir = "/root/autodl-tmp/gradcn",
    [string]$Config = "",
    [string]$Checkpoint = "",
    [int]$Port = 9011,
    [string]$HostName = "127.0.0.1"
)

$env:GRAD_SERVICE_REPO_DIR = $RepoDir
$env:GRAD_SERVICE_CONFIG = if ($Config) { $Config } else { Join-Path $RepoDir "experiments/config.yaml" }
$env:GRAD_SERVICE_CHECKPOINT = if ($Checkpoint) { $Checkpoint } else { Join-Path $RepoDir "experiments/exp/GRAD/MVTecAD/checkpoints/ckpt_best.pth.tar" }
$env:GRAD_SERVICE_OUTPUT_DIR = if ($env:GRAD_SERVICE_OUTPUT_DIR) { $env:GRAD_SERVICE_OUTPUT_DIR } else { "data/heatmaps/grad" }
$env:GRAD_SERVICE_THRESHOLD = if ($env:GRAD_SERVICE_THRESHOLD) { $env:GRAD_SERVICE_THRESHOLD } else { "0.5" }

python -m uvicorn services.grad_local.app:app --host $HostName --port $Port
