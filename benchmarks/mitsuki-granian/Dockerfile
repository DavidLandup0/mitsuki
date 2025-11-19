FROM python:3.10-slim

WORKDIR /build

# Copy Mitsuki source (context is parent directory)
COPY mitsuki ./mitsuki
COPY requirements.txt ./requirements.txt
COPY pyproject.toml ./pyproject.toml
COPY README.md ./README.md

# Install Mitsuki
RUN pip install --no-cache-dir .

# Copy benchmark app
WORKDIR /app
COPY benchmarks/mitsuki-granian/app.py .
COPY benchmarks/mitsuki-granian/application.yml .

CMD ["python3", "app.py"]
