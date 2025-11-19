# Socketify has support for x64, not ARMx64.
FROM --platform=linux/amd64 python:3.10-slim

WORKDIR /app

# Install socketify runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libuv1t64 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY application.yml .

CMD ["python3", "app.py"]
