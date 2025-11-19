import uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route


async def hello(request):
    return JSONResponse({"message": "Hello, World!"})


app = Starlette(routes=[Route("/", hello)])

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="error", access_log=False)
