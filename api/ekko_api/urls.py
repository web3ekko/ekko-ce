"""
URL configuration for ekko_api project.

Passwordless Authentication API with Django REST Framework
"""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.conf import settings
from django.conf.urls.static import static
from .health import health_check, health_detailed, readiness_check, liveness_check, metrics

def api_root(request):
    """API root endpoint"""
    return JsonResponse({
        'message': 'Ekko API - Passwordless Authentication System',
        'version': '1.0.0',
        'authentication': 'Passkeys → Email Magic Links → Optional TOTP',
        'endpoints': {
            'auth': '/api/auth/',
            'admin': '/admin/',
            'docs': '/api/docs/',
            'health': '/health/',
            'metrics': '/metrics/'
        }
    })

urlpatterns = [
    # API Root
    path('', api_root, name='api_root'),
    path('api/', api_root, name='api_root_alt'),

    # Health check endpoints
    path('health/', health_check, name='health_check'),
    path('health/detailed/', health_detailed, name='health_detailed'),
    path('ready/', readiness_check, name='readiness_check'),
    path('live/', liveness_check, name='liveness_check'),
    path('metrics/', metrics, name='metrics'),

    # Authentication
    path('api/auth/', include('authentication.urls')),

    # Passkeys (new implementation)
    path('api/passkeys/', include('passkeys.urls')),

    # Alert System (templates, alerts, notifications)
    path('api/', include('app.urls')),

    # Django Admin
    path('admin/', admin.site.urls),

    # Django Allauth (for WebAuthn/passkey support)
    path('accounts/', include('allauth.urls')),
]

# Serve static files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
