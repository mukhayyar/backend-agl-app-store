# Build stage
FROM python:3.12-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Runtime stage
FROM python:3.12-slim
WORKDIR /app

# System tools required by rest_api.py subprocess calls
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    flatpak \
    ostree \
    gpg \
    gpg-agent \
    curl \
    clamav \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local
COPY . .

# Run as root — required for flatpak build-update-repo and ostree refs --delete
# which write to the mounted /srv/flatpak-repo volume
EXPOSE 8000 50051 8002
CMD ["python", "app.py"]
