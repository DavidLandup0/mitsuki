FROM python:3.11-slim

WORKDIR /usr/src/app

COPY . .
# Install mitsuki in editable mode (until a release is made)
RUN pip install -e .
WORKDIR /usr/src/app/examples/instrumentation_demo
EXPOSE 8000
CMD ["python", "app.py"]
