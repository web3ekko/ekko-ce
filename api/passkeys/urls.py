from django.urls import path
from . import views

app_name = 'passkeys'

urlpatterns = [
    # Registration endpoints
    path('register/', views.passkey_register_begin, name='register_begin'),
    path('register/complete/', views.passkey_register_complete, name='register_complete'),
    
    # Authentication endpoints
    path('authenticate/', views.passkey_authenticate_begin, name='authenticate_begin'),
    path('authenticate/complete/', views.passkey_authenticate_complete, name='authenticate_complete'),
    
    # Device management endpoints
    path('devices/', views.list_passkey_devices, name='list_devices'),
    path('devices/<uuid:device_id>/', views.update_passkey_device, name='update_device'),
    path('devices/<uuid:device_id>/delete/', views.delete_passkey_device, name='delete_device'),
]