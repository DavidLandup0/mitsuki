# {{APP_TITLE}}

Mitsuki application generated with the Mitsuki CLI.
{{DOMAIN_SECTION}}
## Getting Started

```bash
pip install mitsuki
MITSUKI_PROFILE=development python src/app.py
```

The server will start on http://127.0.0.1:8000

## Project Structure

```
{{app_name}}/
  src/
    domain/        # @Entity classes
    repository/    # @CrudRepository classes
    service/       # @Service classes
    controller/    # @RestController classes
  app.py
application.yml
application-dev.yml
application-stg.yml
application-prod.yml
```
