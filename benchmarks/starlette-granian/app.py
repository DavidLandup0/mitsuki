from granian import Granian
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route


async def hello(request):
    return JSONResponse({"message": "Hello, World!"})


app = Starlette(routes=[Route("/", hello)])


if __name__ == "__main__":
    server = Granian(
        "app:app",
        address="0.0.0.0",
        port=8000,
        interface="asgi",
        workers=1,
        log_access=False,
    )
    server.serve()
