#!/usr/bin/env bash
set -euo pipefail

export GRAD_SERVICE_REPO_DIR="${GRAD_SERVICE_REPO_DIR:-/root/autodl-tmp/gradcn}"
export GRAD_SERVICE_CONFIG="${GRAD_SERVICE_CONFIG:-$GRAD_SERVICE_REPO_DIR/experiments/config.yaml}"
export GRAD_SERVICE_CHECKPOINT="${GRAD_SERVICE_CHECKPOINT:-$GRAD_SERVICE_REPO_DIR/experiments/exp/GRAD/MVTecAD/checkpoints/ckpt_best.pth.tar}"
export GRAD_SERVICE_OUTPUT_DIR="${GRAD_SERVICE_OUTPUT_DIR:-$PWD/data/heatmaps/grad}"
export GRAD_SERVICE_THRESHOLD="${GRAD_SERVICE_THRESHOLD:-0.5}"

python -m uvicorn services.grad_local.app:app --host "${GRAD_SERVICE_HOST:-0.0.0.0}" --port "${GRAD_SERVICE_PORT:-9011}"
