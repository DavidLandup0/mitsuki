---
outline: deep
---

# Getting Started with Mitsuki

Welcome to Mitsuki! 

_Come with me, take the journey. ❀_

This guide will get you up and running with your first application in just a few minutes.

## 1. Installation

First, install Mitsuki from PyPI:

```bash
pip install mitsuki
```

## 2. Your First Application

Create a file named `app.py` and add the following code:

```python
from mitsuki import Application, RestController, GetMapping

@RestController # Or @Controller or @Router
class HelloController:
    @GetMapping("/hello/{name}") # Or @Get
    async def hello(self, name: str) -> dict:
        return {"message": f"Hello, {name}!"}

@Application
class MyApp:
    # Or add configs here
    pass

if __name__ == "__main__":
    MyApp.run()
```

::: tip What's happening here?
- `@Application` marks the entry point of our app.
- `@RestController` defines a class that handles HTTP requests.
- `@GetMapping` maps the `hello` method to the URL `/hello/{name}`.
- The `name` parameter is automatically extracted from the URL.
- The dictionary returned by the method is automatically converted to a JSON response.
:::

:::tip LEARN MORE
To learn more about configuration options - read _[Configuration](./06_configuration.md)_. 

Alternatively, you can also use the CLI for a standardized project structure, a set of starter domain objects and auto-working repositories with CRUD capabilities at no cost. 

For getting started with the CLI, hit `mitsuki init` or read _[CLI](./07_cli.md)_.
:::

## 3. Running the Application

Run your application from the terminal:

```bash
python app.py
```

Which shows you the startup logs:

```
2025-11-27 23:44:39,132 - mitsuki - INFO     - 
2025-11-27 23:44:39,132 - mitsuki - INFO     -     ♡ ｡ ₊°༺❤︎༻°₊ ｡ ♡
2025-11-27 23:44:39,132 - mitsuki - INFO     -               _ __             __   _
2025-11-27 23:44:39,132 - mitsuki - INFO     -    ____ ___  (_) /________  __/ /__(_)
2025-11-27 23:44:39,132 - mitsuki - INFO     -   / __ `__ \/ / __/ ___/ / / / //_/ /
2025-11-27 23:44:39,132 - mitsuki - INFO     -  / / / / / / / /_(__  ) /_/ / ,< / /
2025-11-27 23:44:39,132 - mitsuki - INFO     - /_/ /_/ /_/_/\__/____/\__,_/_/|_/_/
2025-11-27 23:44:39,132 - mitsuki - INFO     -     °❀˖ ° °❀⋆.ೃ࿔*:･  ° ❀˖°
2025-11-27 23:44:39,132 - mitsuki - INFO     - 
2025-11-27 23:44:39,132 - mitsuki - INFO     - :: Mitsuki ::                (v0.1.1)
2025-11-27 23:44:39,132 - mitsuki - INFO     - 
2025-11-27 23:44:39,132 - mitsuki - INFO     - Mitsuki application starting on http://0.0.0.0:8000
2025-11-27 23:44:39,133 - _granian - INFO     - Starting granian (main PID: 92829)
2025-11-27 23:44:39,139 - _granian - INFO     - Listening at: http://0.0.0.0:8000
2025-11-27 23:44:39,150 - _granian - INFO     - Spawning worker-1 with PID: 92836
2025-11-27 23:44:39,559 - _granian.workers - INFO     - Started worker-1
2025-11-27 23:44:39,559 - _granian.workers - INFO     - Started worker-1 runtime-1
```

## 4. Testing Your Endpoint

Open a new terminal and use `curl` to test your new endpoint:

```bash
curl http://localhost:8000/hello/world
```

You should get the following JSON response:

```json
{"message":"Hello, world!"}
```

:::tip LEARN MORE
To learn more about responses, requests and validation - read _[Response Entity](./09_response_entity.md)_ and _[Request/Response Validation](./10_request_response_validation.md)_.
:::

## 5. Automatic API Documentation

Mitsuki automatically generates OpenAPI documentation for your application. With your application still running, open your browser and go to:

[http://localhost:8000/docs](http://localhost:8000/docs)

You will see the Scalar documentation UI, where you can explore and interact with your API:

![](/doc_assets/mitsuki_hello.png)

You can switch between SwaggerUI, Redocly and Scalar or have them all at the same time. 

:::tip LEARN MORE
To learn more about OpenAPI support - read _[OpenAPI](./16_openapi.md)_.
:::

## Next Steps

Congratulations! You've built and run your first Mitsuki application.

Here are some topics to explore next:

-   **[Overview](./01_overview.md)**: Understand the core concepts of Mitsuki, such as dependency injection and the overall architecture.
-   **[Controllers](./04_controllers.md)**: Learn more about creating controllers and handling different types of requests.
-   **[Repositories & Data Layer](./03_repositories.md)**: Discover how to connect to a database and perform CRUD operations with zero boilerplate.
-   **[Configuration](./06_configuration.md)**: See how to configure your application using `application.yml`.
-   **[OpenAPI](./16_openapi.md)**: Customize your API documentation with tags, descriptions, and examples.
