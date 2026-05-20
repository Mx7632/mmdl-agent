# GRAD local service

This sidecar wraps the trained GRAD repository as an HTTP detector so the main project can select it with `tool_type=grad`.

## AutoDL startup

Run these commands in the same Python environment that can already train/evaluate GRAD:

```bash
cd /root/autodl-tmp/mmdl-agent
pip install -r services/grad_local/requirements.txt

export GRAD_SERVICE_REPO_DIR=/root/autodl-tmp/gradcn
export GRAD_SERVICE_CONFIG=/root/autodl-tmp/gradcn/experiments/config.yaml
export GRAD_SERVICE_CHECKPOINT=/root/autodl-tmp/gradcn/experiments/exp/GRAD/MVTecAD/checkpoints/ckpt_best.pth.tar
export GRAD_SERVICE_OUTPUT_DIR=/root/autodl-tmp/mmdl-agent/data/heatmaps/grad
export GRAD_SERVICE_THRESHOLD=0.5

python -m uvicorn services.grad_local.app:app --host 0.0.0.0 --port 9011
```

Health check:

```bash
curl http://127.0.0.1:9011/health
```

## Main project config

In the main project `.env`:

```env
APP_GRAD_DETECTOR_URL=http://127.0.0.1:9011/detect
APP_GRAD_DETECTOR_TIMEOUT=60
APP_GRAD_DETECTOR_ALIASES=grad,bi_grid,bi-grid
```

To make GRAD the default image backend:

```env
APP_VISION_DETECTOR_BACKEND=grad
```

Or keep another default and select GRAD per request:

```json
{"tool_type":"grad","detector_params":{"category":"bottle","threshold":0.5}}
```

## Endpoint

`POST /detect`

```json
{
  "task_id": "grad-demo",
  "image_base64": "<base64>",
  "image_mime": "image/png",
  "detector_params": {
    "category": "bottle",
    "threshold": 0.5
  }
}
```

The response follows the main project's `DetectionResult` shape: `status`, `answer`, `summary`, `anomalies`, and `metadata` with heatmap paths.
