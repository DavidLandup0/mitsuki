# Socketify has support for x64, not ARMx64.
FROM --platform=linux/amd64 python:3.10-slim

WORKDIR /build

# Install socketify runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libuv1t64 \
    && rm -rf /var/lib/apt/lists/*

# Copy Mitsuki source (context is parent directory)
COPY mitsuki ./mitsuki
COPY requirements.txt ./requirements.txt
COPY pyproject.toml ./pyproject.toml
COPY README.md ./README.md

# Install Mitsuki with socketify for x86_64
RUN pip install --no-cache-dir .

# Copy benchmark app
WORKDIR /app
COPY benchmarks/mitsuki-socketify/app.py .
COPY benchmarks/mitsuki-socketify/application.yml .

CMD ["python3", "app.py"]
