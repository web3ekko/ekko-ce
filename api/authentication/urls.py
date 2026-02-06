"""
URL Configuration for Authentication App

Implements passwordless authentication endpoints:
- Signup flow: email → passkey → optional TOTP
- Login flow: passkey → email fallback → optional TOTP
- Account recovery
- Device management
"""

from django.urls import path, include
from . import views, views_firebase, views_verification

app_name = 'authentication'

urlpatterns = [
    # Test endpoint
    path('test-drf/', views.test_drf, name='test_drf'),
    
    # Account Status Check
    path('check-account-status/', views_verification.check_account_status, name='check_account_status'),
    
    # Passwordless Signup with Verification Codes
    path('signup/', views.signup_begin, name='signup_begin'),
    path('signup/verify-code/', views_verification.signup_verify_code, name='signup_verify_code'),
    path('signup/passkey/register/', views.signup_passkey_register, name='signup_passkey_register'),
    path('signup/passkey/skip/', views.signup_skip_passkey, name='signup_skip_passkey'),
    path('signup/complete-dev/', views_verification.signup_complete_dev, name='signup_complete_dev'),  # Development mode
    
    # Passwordless Login Options
    path('options/', views.auth_options, name='auth_options'),
    
    # Passkey Sign-in (Primary)
    path('signin/passkey/begin/', views_verification.signin_passkey_begin, name='signin_passkey_begin'),
    path('signin/passkey/complete/', views_verification.signin_passkey_complete, name='signin_passkey_complete'),
    
    # Email Code Sign-in (Fallback)
    path('signin/email/send-code/', views_verification.signin_email_send_code, name='signin_email_send_code'),
    path('signin/email/verify-code/', views_verification.signin_email_verify_code, name='signin_email_verify_code'),
    
    # Resend Verification Code
    path('resend-code/', views_verification.resend_code, name='resend_code'),
    
    # Account Recovery with Verification Codes
    path('recovery/request/', views_verification.recovery_request, name='recovery_request'),
    path('recovery/verify-code/', views_verification.recovery_verify_code, name='recovery_verify_code'),
    path('recovery/complete/', views.account_recovery_complete, name='account_recovery_complete'),
    
    # Logout
    path('logout/', views.logout_user, name='logout'),

    # Token Management
    # path('token/refresh/', views.refresh_token, name='refresh_token'),  # Not implemented
    path('firebase-token/', views.get_firebase_token, name='get_firebase_token'),
    
    # Token Validation
    path('validate-token/', views_verification.validate_token, name='validate_token'),

    # Knox Token Management
    path('knox/token-info/', views.knox_token_info, name='knox_token_info'),
    path('knox/refresh/', views.knox_auto_refresh, name='knox_auto_refresh'),
    path('knox/logout/', views.knox_logout, name='knox_logout'),
    path('knox/tokens/', views.knox_list_tokens, name='knox_list_tokens'),

    # Firebase Integration
    path('firebase/token-exchange/', views_firebase.firebase_token_exchange, name='firebase_token_exchange'),
    path('firebase/custom-token/', views_firebase.firebase_custom_token, name='firebase_custom_token'),
    path('firebase/config/', views_firebase.firebase_config, name='firebase_config'),
    path('firebase/status/', views.firebase_status, name='firebase_status'),
    
    # Email Verification
    path('verify-email/', views.verify_email, name='verify_email'),
    
    # User Profile
    path('profile/', views.user_profile, name='user_profile'),
    
    # Configuration Status Endpoints
    path('user-model/check/', views.user_model_check, name='user_model_check'),
    path('webauthn/status/', views.webauthn_status, name='webauthn_status'),
    
    # Passkey Management
    path('passkey/register/', views.register_passkey, name='register_passkey'),
    path('passkey/authenticate/', views.authenticate_passkey, name='authenticate_passkey'),
    path('passkey/list/', views.list_passkeys, name='list_passkeys'),
    path('passkey/<int:passkey_id>/delete/', views.delete_passkey, name='delete_passkey'),
    
    # WebAuthn Registration (Django Allauth integration)
    path('webauthn/register/begin/', views.webauthn_register_begin, name='webauthn_register_begin'),
    path('webauthn/register/complete/', views.webauthn_register_complete, name='webauthn_register_complete'),
    
    # TOTP Management (to be implemented)
    # path('totp/setup/', views.setup_totp, name='setup_totp'),
    # path('totp/verify/', views.verify_totp, name='verify_totp'),
    # path('totp/disable/', views.disable_totp, name='disable_totp'),
    
    # Push Notification Token Management
    path('devices/register-push/', views.register_push_token, name='register_push_token'),
    path('devices/push-enabled/', views.list_push_enabled_devices, name='list_push_enabled_devices'),
    path('devices/<uuid:device_id>/push-token/', views.update_device_push_token, name='update_device_push_token'),
    path('devices/<uuid:device_id>/push-token/revoke/', views.revoke_device_push_token, name='revoke_device_push_token'),
    path('devices/<uuid:device_id>/push-enabled/', views.toggle_device_push, name='toggle_device_push'),

    # Device Management (to be implemented)
    # path('devices/', views.list_devices, name='list_devices'),
    # path('devices/<uuid:device_id>/', views.device_detail, name='device_detail'),
    # path('devices/<uuid:device_id>/trust/', views.trust_device, name='trust_device'),
    # path('devices/<uuid:device_id>/revoke/', views.revoke_device, name='revoke_device'),
    
    # Cross-Device Authentication (to be implemented)
    # path('cross-device/initiate/', views.initiate_cross_device, name='initiate_cross_device'),
    # path('cross-device/approve/', views.approve_cross_device, name='approve_cross_device'),
    # path('cross-device/status/<str:session_id>/', views.cross_device_status, name='cross_device_status'),
    
    # Recovery Codes (to be implemented)
    # path('recovery-codes/', views.list_recovery_codes, name='list_recovery_codes'),
    # path('recovery-codes/regenerate/', views.regenerate_recovery_codes, name='regenerate_recovery_codes'),
    
    # User Profile (to be implemented)
    # path('profile/', views.user_profile, name='user_profile'),
    # path('profile/update/', views.update_profile, name='update_profile'),
    
    # Authentication Status (to be implemented)
    # path('status/', views.auth_status, name='auth_status'),
    # path('methods/', views.available_methods, name='available_methods'),
    
    # The verification code endpoints are already defined above, remove duplicates
]
