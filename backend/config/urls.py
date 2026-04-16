from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView


@csrf_exempt
def debug_token(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    try:
        import json
        from django.contrib.auth import authenticate
        from rest_framework_simplejwt.tokens import RefreshToken
        body = json.loads(request.body)
        user = authenticate(username=body.get("username"), password=body.get("password"))
        if user is None:
            return JsonResponse({"error": "invalid credentials"}, status=401)
        refresh = RefreshToken.for_user(user)
        return JsonResponse({"access": str(refresh.access_token), "refresh": str(refresh)})
    except Exception as e:
        import traceback
        return JsonResponse({"error": str(e), "trace": traceback.format_exc()}, status=500)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/debug-token/", debug_token),
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/", include("prospection.urls")),
]
