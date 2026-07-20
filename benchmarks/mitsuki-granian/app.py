from mitsuki import Application, GetMapping, RestController, Instrumented


@RestController()
class HelloController:
    @GetMapping("/")
    async def hello(self):
        return {"message": "Hello, World!"}


@Application
@Instrumented()
class BenchmarkApp:
    pass


if __name__ == "__main__":
    BenchmarkApp.run(host="0.0.0.0")
