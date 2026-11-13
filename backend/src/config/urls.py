from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", include("apps.health.urls")),
    path("api/accounts/", include("apps.accounts.urls")),
    path("api/", include("apps.configuration.urls")),
    # SIGEDA: endpoints de CU-04 y lo que lo precede.
    path("api/sigeda/auth/", include("apps.accounts.sigeda_urls")),
    path("api/sigeda/abonados/", include("apps.abonados.urls")),
    path("api/sigeda/documentos/", include("apps.documents.sigeda_urls")),
    path("api/sigeda/catalogos/", include("apps.configuration.sigeda_urls")),
    path("api/sigeda/respaldos/", include("apps.respaldos.sigeda_urls")),
    path("api/sigeda/bitacora/", include("apps.bitacora.sigeda_urls")),
]