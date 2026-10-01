# Production Configuration

database:
  url: {{DATABASE_URL}}
  echo: false
  pool:
    enabled: true
    size: 50
    max_overflow: 100

logging:
  level: WARNING
  sqlalchemy: false

app:
  debug: false
