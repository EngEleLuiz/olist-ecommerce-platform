FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY data_loader.py .
COPY ml/            ml/

# Artifacts directory — ECS task mounts an EFS volume here in prod
# so trained models persist across container restarts
RUN mkdir -p ml/artifacts

ENV PYTHONUNBUFFERED=1 \
    USE_DUCKDB=false

# Default: train all three models. Override via Step Functions command.
CMD ["python", "-m", "ml.train_all"]
