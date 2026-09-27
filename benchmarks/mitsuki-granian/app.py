from mitsuki import Application, GetMapping, RestController


@RestController()
class HelloController:
    @GetMapping("/")
    async def hello(self):
        return {"message": "Hello, World!"}


@Application
class BenchmarkApp:
    pass


if __name__ == "__main__":
    BenchmarkApp.run(host="0.0.0.0")
