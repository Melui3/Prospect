from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CampaignViewSet, ProspectViewSet, EmailTemplateViewSet, stats

router = DefaultRouter()
router.register(r"campaigns", CampaignViewSet, basename="campaign")
router.register(r"prospects", ProspectViewSet, basename="prospect")
router.register(r"templates", EmailTemplateViewSet, basename="template")

urlpatterns = [
    path("", include(router.urls)),
    path("stats/", stats, name="stats"),
]
