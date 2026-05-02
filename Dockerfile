FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg nodejs npm && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN mkdir -p /root/.pip && \
    echo "[global]" > /root/.pip/pip.conf && \
    echo "index-url = https://mirrors.aliyun.com/pypi/simple/" >> /root/.pip/pip.conf && \
    echo "trusted-host = mirrors.aliyun.com" >> /root/.pip/pip.conf

COPY requirements.txt .
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt

# Build frontend
COPY frontend/ ./frontend/
RUN cd frontend && npm install && npm run build

# 注意：app/ 目录通过 volume 映射，不再 COPY
# Dockerfile 中不复制 app/，运行时由 docker-compose volumes 挂载

RUN mkdir -p /app/data/audio

EXPOSE 8000

ENV DATA_DIR=/app/data
ENV TTS_API_BASE=http://host.docker.internal:8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]