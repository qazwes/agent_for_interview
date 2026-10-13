FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 MODELSCOPE_CACHE=/models
WORKDIR /service
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*
# CPU 版 PyTorch，避免下载 CUDA 运行库；与主后端的 Python 环境隔离。
RUN pip install --no-cache-dir torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cpu
COPY docker/asr/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
ENV HF_HOME=/models/hf-cache HF_HUB_DISABLE_XET=1
COPY docker/asr/server.py docker/asr/download_models.py ./
EXPOSE 8000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
