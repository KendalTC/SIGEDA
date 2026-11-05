from django.conf import settings
from django.http import JsonResponse


def health_check(request):
    return JsonResponse(
        {
            "status": "healthy",
            "service": "SIGEDA",
            "version": settings.APP_VERSION,
        }
    )
