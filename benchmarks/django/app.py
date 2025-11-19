import django
from django.conf import settings
from django.core.asgi import get_asgi_application
from django.http import JsonResponse
from django.urls import path

settings.configure(
    DEBUG=False,
    SECRET_KEY="benchmark",
    ROOT_URLCONF=__name__,
    ALLOWED_HOSTS=["*"],
    MIDDLEWARE=[],
    LOGGING={"version": 1, "disable_existing_loggers": True},
)

django.setup()


def hello(request):
    return JsonResponse({"message": "Hello, World!"})


urlpatterns = [path("", hello)]

application = get_asgi_application()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        application,
        host="0.0.0.0",
        port=8000,
        log_level="critical",
        access_log=False,
    )
