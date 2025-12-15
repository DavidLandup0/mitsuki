from mitsuki import Application, Value
from mitsuki.core.instrumentation import Instrumented


@Instrumented()  # Enable instrumentation for all components
@Application
class App:
    """
    Application entry point.

    The @Instrumented decorator on @Application automatically instruments:
    - All @Service classes (UserService, OrderService)
    - All @Repository classes (UserRepository, OrderRepository)
    - All @RestController classes (UserController, OrderController)

    No additional configuration needed!
    """

    port: int = Value("${server.port:8000}")


if __name__ == "__main__":
    App.run(host="0.0.0.0")
