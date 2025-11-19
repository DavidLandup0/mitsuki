from dataclasses import dataclass

from mitsuki import Application, GetMapping, PostMapping, RestController


@dataclass
class Message:
    text: str
    priority: int = 1


@RestController("/api")
class SimpleController:
    @GetMapping("/hello")
    async def hello(self) -> dict:
        return {"message": "Hello, World!"}

    @PostMapping("/message")
    async def create_message(self, body: Message) -> Message:
        return body


@Application
class MultiUIApp:
    pass


if __name__ == "__main__":
    MultiUIApp.run()
