from mitsuki import Application, Instrumented, Value


@Instrumented()
@Application
class App:
    """
    Application entry point.

    @Instrumented() on the application instruments every @RestController,
    @Service, @Repository and @CrudRepository. It takes effect when
    instrumentation.enabled and metrics.enabled are set in application.yml.
    """

    port: int = Value("${server.port:8000}")


if __name__ == "__main__":
    App.run(host="0.0.0.0")
