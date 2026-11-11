from django.contrib import admin
from django.conf import settings
from django.http import Http404
from django.urls import path, include
from django.urls import re_path
from django.views.static import serve


def desktop_frontend(request, path=""):
    frontend_dir = getattr(settings, "FRONTEND_DIST_DIR", None)
    if not getattr(settings, "SERVE_FRONTEND", False) or not frontend_dir:
        raise Http404("Frontend local indisponible.")

    requested = frontend_dir / path
    if path and requested.exists() and requested.is_file():
        return serve(request, path, document_root=frontend_dir)

    index = frontend_dir / "index.html"
    if index.exists():
        return serve(request, "index.html", document_root=frontend_dir)

    raise Http404("Build frontend local introuvable.")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("prospection.urls")),
]

if getattr(settings, "SERVE_FRONTEND", False):
    urlpatterns.append(re_path(r"^(?P<path>.*)$", desktop_frontend))
