FROM nvidia/cuda:11.7.1-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ANOMALYGPT_SERVICE_REPO_DIR=/opt/AnomalyGPT \
    ANOMALYGPT_SERVICE_HOST=0.0.0.0 \
    ANOMALYGPT_SERVICE_PORT=9001

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-dev \
    build-essential \
    git \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3 /usr/bin/python

WORKDIR /srv/anomalygpt-service

COPY requirements.txt requirements.txt
COPY requirements-official.txt requirements-official.txt
COPY app.py app.py
COPY __init__.py __init__.py

RUN python -m pip install --upgrade pip setuptools wheel
RUN python -m pip install \
    --extra-index-url https://download.pytorch.org/whl/cu117 \
    torch==1.13.1+cu117 \
    torchvision==0.14.1+cu117 \
    torchaudio==0.13.1+cu117
RUN python -m pip install -r requirements-official.txt -r requirements.txt

EXPOSE 9001

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "9001"]
