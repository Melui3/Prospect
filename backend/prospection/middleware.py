import threading
from django.conf import settings

api_lock = threading.RLock()


class DesktopDatabaseGate:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Serialize desktop API requests so a restore cannot race an edit or send.
        if settings.DESKTOP_MODE and request.path.startswith("/api/"):
            with api_lock:
                return self.get_response(request)
        return self.get_response(request)
