# Mitsuki Application Configuration

server:
  host: 0.0.0.0
  port: 8000
  type: granian  # Options: uvicorn, granian
  workers: 1     # Number of worker processes (Currently supported on Granian only)
  access_log: true  # Enable/disable access logging
  ignore_trailing_slash: true
  # timeout: 60  # Request timeout in seconds (optional, uses server defaults if not set)
  # max_body_size: 10485760  # Max request body size in bytes (default: 10MB)
  # cors:
  #   enabled: false
  #   allowed_origins:
  #     - "*"

database:
  url: sqlite:///app.db
  adapter: sqlalchemy
  echo: false # SQLAlchemy logs
  pool:
    enabled: true
    size: 10
    max_overflow: 20
    timeout: 30
    recycle: 3600

logging:
  level: INFO
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  sqlalchemy: false

app:
  name: {{app_name}}
  debug: false
