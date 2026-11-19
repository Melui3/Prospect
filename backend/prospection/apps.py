from django.apps import AppConfig


class ProspectionConfig(AppConfig):
    name = "prospection"

    def ready(self):
        from . import opposition  # Register suppression persistence on save and deletion.
