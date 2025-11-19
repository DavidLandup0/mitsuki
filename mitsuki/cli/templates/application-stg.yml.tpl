# Staging Configuration

database:
  url: postgresql://localhost/{{app_name}}_staging
  echo: false
  pool:
    enabled: true
    size: 10
    max_overflow: 20

logging:
  level: INFO
  sqlalchemy: false

app:
  debug: false
