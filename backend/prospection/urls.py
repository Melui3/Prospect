from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import personal_api
from .views import (
    CampaignViewSet,
    ProspectViewSet,
    EmailTemplateViewSet,
    session_status,
    stats,
)

router = DefaultRouter()
router.register(r"campaigns", CampaignViewSet, basename="campaign")
router.register(r"prospects", ProspectViewSet, basename="prospect")
router.register(r"templates", EmailTemplateViewSet, basename="template")
personal_router = DefaultRouter()
personal_router.register("contacts", personal_api.ContactViewSet, basename="personal-contact")
personal_router.register("campaigns", personal_api.PersonalCampaignViewSet, basename="personal-campaign")
personal_router.register("jobs", personal_api.JobViewSet, basename="personal-job")

urlpatterns = [
    path("personal/", include(personal_router.urls)),
    path("personal/qualification/", personal_api.qualification_queue),
    path("personal/qualification/run/", personal_api.qualification_run),
    path("personal/qualification/<int:pk>/<str:decision>/", personal_api.qualification_decision),
    path("personal/today/", personal_api.today),
    path("personal/email-settings/", personal_api.email_settings),
    path("personal/delivery-sync/", personal_api.delivery_sync),
    path("personal/backups/", personal_api.backups),
    path("personal/restore/", personal_api.restore),
    path("", include(router.urls)),
    path("session/", session_status, name="session-status"),
    path("stats/", stats, name="stats"),
]
