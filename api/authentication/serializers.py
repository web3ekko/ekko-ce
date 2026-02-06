"""
Serializers for Passwordless Authentication System

Provides data validation and serialization for:
- Passwordless signup and login
- Email magic links
- Device management
- User profile data
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.core.validators import EmailValidator
from .models import UserDevice, EmailVerificationCode

User = get_user_model()


class SignupBeginSerializer(serializers.Serializer):
    """
    Serializer for beginning passwordless signup
    """
    email = serializers.EmailField(
        validators=[EmailValidator()],
        help_text="Email address for the new account"
    )
    device_info = serializers.JSONField(
        required=False,
        default=dict,
        help_text="Device capabilities and information"
    )
    
    def validate_email(self, value):
        """
        Validate email is not already registered
        """
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already registered")
        return value.lower()




class LoginSerializer(serializers.Serializer):
    """
    Serializer for passwordless login
    """
    email = serializers.EmailField(
        validators=[EmailValidator()],
        help_text="Email address for login"
    )
    auth_method = serializers.ChoiceField(
        choices=[
            ('auto', 'Auto-detect best method'),
            ('passkey', 'Passkey authentication'),
            ('email_code', 'Email verification code'),
        ],
        default='auto',
        help_text="Preferred authentication method"
    )
    device_info = serializers.JSONField(
        required=False,
        default=dict,
        help_text="Device capabilities and information"
    )
    
    def validate_email(self, value):
        """
        Validate email exists in system
        """
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Account not found")
        return value.lower()




class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for user profile data (Knox compatible)
    """
    full_name = serializers.ReadOnlyField()
    firebase_uid = serializers.CharField(read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name', 'firebase_uid',
            'preferred_auth_method', 'is_email_verified', 'has_passkey', 
            'has_2fa', 'created_at', 'last_login'
        ]
        read_only_fields = [
            'id', 'email', 'firebase_uid', 'is_email_verified', 'has_passkey', 
            'has_2fa', 'created_at', 'last_login'
        ]


class DeviceSerializer(serializers.ModelSerializer):
    """
    Serializer for user device information
    """
    is_trust_expired = serializers.ReadOnlyField()
    
    class Meta:
        model = UserDevice
        fields = [
            'id', 'device_name', 'device_type', 'supports_passkey',
            'supports_biometric', 'is_trusted', 'is_active',
            'trust_expires_at', 'last_used', 'created_at', 'is_trust_expired'
        ]
        read_only_fields = [
            'id', 'is_trusted', 'trust_expires_at', 'last_used', 
            'created_at', 'is_trust_expired'
        ]


class PasskeyRegistrationSerializer(serializers.Serializer):
    """
    Serializer for passkey registration
    """
    credential_data = serializers.JSONField(
        help_text="WebAuthn credential data from navigator.credentials.create()"
    )
    device_info = serializers.JSONField(
        required=False,
        default=dict,
        help_text="Device information for tracking"
    )
    
    def validate_credential_data(self, value):
        """
        Validate WebAuthn credential data structure
        """
        required_fields = ['id', 'rawId', 'response', 'type']
        for field in required_fields:
            if field not in value:
                raise serializers.ValidationError(f"Missing required field: {field}")
        
        if value.get('type') != 'public-key':
            raise serializers.ValidationError("Invalid credential type")
        
        # Validate response object has required fields for registration
        response = value.get('response', {})
        response_fields = ['attestationObject', 'clientDataJSON']
        for field in response_fields:
            if field not in response:
                raise serializers.ValidationError(f"Missing required response field: {field}")
        
        # For passkey registration, authenticatorData may contain user info
        # that will be used for passwordless authentication later
        
        return value


class PasskeyAuthenticationSerializer(serializers.Serializer):
    """
    Serializer for passkey authentication
    """
    credential_data = serializers.JSONField(
        help_text="WebAuthn credential data from navigator.credentials.get()"
    )
    device_info = serializers.JSONField(
        required=False,
        default=dict,
        help_text="Device information for tracking"
    )
    
    def validate_credential_data(self, value):
        """
        Validate WebAuthn credential data structure
        """
        required_fields = ['id', 'rawId', 'response', 'type']
        for field in required_fields:
            if field not in value:
                raise serializers.ValidationError(f"Missing required field: {field}")
        
        if value.get('type') != 'public-key':
            raise serializers.ValidationError("Invalid credential type")
        
        # Validate response object has required fields
        response = value.get('response', {})
        response_fields = ['authenticatorData', 'clientDataJSON', 'signature']
        for field in response_fields:
            if field not in response:
                raise serializers.ValidationError(f"Missing required response field: {field}")
        
        # userHandle is optional but important for passwordless authentication
        # It contains the user identifier set during credential creation
        if 'userHandle' in response and response['userHandle']:
            # Ensure userHandle is properly formatted if present
            # Django Allauth will use this to identify the user in passwordless flow
            pass
        
        return value


class TOTPSetupSerializer(serializers.Serializer):
    """
    Serializer for TOTP setup
    """
    verification_code = serializers.CharField(
        min_length=6,
        max_length=6,
        help_text="6-digit TOTP verification code"
    )
    
    def validate_verification_code(self, value):
        """
        Validate TOTP code format
        """
        if not value.isdigit():
            raise serializers.ValidationError("Verification code must be 6 digits")
        return value


class TOTPVerificationSerializer(serializers.Serializer):
    """
    Serializer for TOTP verification
    """
    totp_code = serializers.CharField(
        min_length=6,
        max_length=6,
        help_text="6-digit TOTP code"
    )
    session_token = serializers.CharField(
        required=False,
        help_text="2FA session token"
    )
    
    def validate_totp_code(self, value):
        """
        Validate TOTP code format
        """
        if not value.isdigit():
            raise serializers.ValidationError("TOTP code must be 6 digits")
        return value








# Knox-specific serializers
class VerifyEmailSerializer(serializers.Serializer):
    """Serializer for email verification endpoint"""
    verification_token = serializers.CharField(required=True)


class WebAuthnRegisterBeginSerializer(serializers.Serializer):
    """Serializer for WebAuthn registration begin endpoint"""
    email = serializers.EmailField(required=True)


class WebAuthnRegisterCompleteSerializer(serializers.Serializer):
    """Serializer for WebAuthn registration complete endpoint"""
    credential = serializers.DictField(required=True)
    challenge = serializers.CharField(required=True)


# Verification Code Serializers
class CheckAccountStatusSerializer(serializers.Serializer):
    """Check if account exists and is active"""
    email = serializers.EmailField(
        validators=[EmailValidator()],
        help_text="Email address to check"
    )


class SignupWithCodeSerializer(serializers.Serializer):
    """Begin signup with verification code"""
    email = serializers.EmailField(
        validators=[EmailValidator()],
        help_text="Email address for the new account"
    )
    
    def validate_email(self, value):
        """Check if active account already exists"""
        if User.objects.filter(email=value.lower(), is_active=True).exists():
            raise serializers.ValidationError("Account already exists. Please sign in.")
        return value.lower()


class VerifyCodeSerializer(serializers.Serializer):
    """Verify a 6-digit verification code"""
    email = serializers.EmailField(
        validators=[EmailValidator()],
        help_text="Email address"
    )
    code = serializers.CharField(
        min_length=6,
        max_length=6,
        help_text="6-digit verification code"
    )
    
    def validate_code(self, value):
        """Validate code is 6 digits"""
        if not value.isdigit():
            raise serializers.ValidationError("Code must be 6 digits")
        return value


class SigninEmailCodeSerializer(serializers.Serializer):
    """Request sign-in verification code"""
    email = serializers.EmailField(
        validators=[EmailValidator()],
        help_text="Email address"
    )
    
    def validate_email(self, value):
        """Check if active account exists"""
        if not User.objects.filter(email=value.lower(), is_active=True).exists():
            raise serializers.ValidationError("No account found")
        return value.lower()


class ResendCodeSerializer(serializers.Serializer):
    """Resend verification code"""
    email = serializers.EmailField(
        validators=[EmailValidator()],
        help_text="Email address"
    )
    purpose = serializers.ChoiceField(
        choices=['signup', 'signin', 'recovery'],
        help_text="Purpose of the code"
    )


class RecoveryRequestSerializer(serializers.Serializer):
    """Request account recovery"""
    email = serializers.EmailField(
        validators=[EmailValidator()],
        help_text="Email address for recovery"
    )


class PasskeyCompleteSerializer(serializers.Serializer):
    """Complete passkey registration after email verification"""
    email = serializers.EmailField(
        validators=[EmailValidator()],
        help_text="Email address"
    )
    credential = serializers.JSONField(
        help_text="WebAuthn credential data"
    )


class PasskeyAuthenticationBeginSerializer(serializers.Serializer):
    """
    Serializer for beginning passkey authentication
    """
    email = serializers.EmailField(
        required=False,
        allow_blank=True,
        validators=[EmailValidator()],
        help_text="Email address (optional for passwordless authentication)"
    )
    device_info = serializers.JSONField(
        required=False,
        default=dict,
        help_text="Device capabilities and information"
    )

    def validate_email(self, value):
        """
        Validate email if provided
        """
        if value:
            # Normalize email to lowercase
            return value.lower()
        return value


# ============================================================================
# Push Notification Token Serializers
# ============================================================================

class RegisterPushTokenSerializer(serializers.Serializer):
    """
    Serializer for registering a push notification token for a device.

    Used when mobile apps obtain FCM/APNs tokens and need to register them
    with the backend for push notification delivery.
    """
    device_token = serializers.CharField(
        max_length=512,
        help_text="FCM or APNs device token for push notifications"
    )
    token_type = serializers.ChoiceField(
        choices=[('fcm', 'FCM'), ('apns', 'APNs')],
        default='fcm',
        help_text="Push notification provider type"
    )
    device_id = serializers.CharField(
        max_length=255,
        required=False,
        help_text="Device ID to update. If not provided, uses current device from auth."
    )
    device_name = serializers.CharField(
        max_length=255,
        required=False,
        help_text="Human-readable device name (e.g., 'John's iPhone')"
    )
    device_type = serializers.ChoiceField(
        choices=[('ios', 'iOS'), ('android', 'Android'), ('web', 'Web Browser')],
        required=False,
        help_text="Device platform type"
    )

    def validate_device_token(self, value):
        """Validate token is not empty and has reasonable length."""
        if not value or len(value) < 32:
            raise serializers.ValidationError("Device token is too short")
        if len(value) > 512:
            raise serializers.ValidationError("Device token is too long")
        return value


class UpdatePushTokenSerializer(serializers.Serializer):
    """
    Serializer for refreshing/updating a push token for an existing device.

    FCM/APNs tokens can change, so apps need to update them periodically.
    """
    device_token = serializers.CharField(
        max_length=512,
        help_text="New FCM or APNs device token"
    )
    token_type = serializers.ChoiceField(
        choices=[('fcm', 'FCM'), ('apns', 'APNs')],
        required=False,
        help_text="Push notification provider type (optional, keeps existing if not provided)"
    )

    def validate_device_token(self, value):
        """Validate token is not empty and has reasonable length."""
        if not value or len(value) < 32:
            raise serializers.ValidationError("Device token is too short")
        return value


class PushEnabledSerializer(serializers.Serializer):
    """
    Serializer for toggling push notification status for a device.
    """
    enabled = serializers.BooleanField(
        help_text="Whether to enable or disable push notifications for this device"
    )


class PushDeviceSerializer(serializers.Serializer):
    """
    Serializer for returning push-enabled device information.

    Used when listing devices with push notification capability.
    """
    id = serializers.UUIDField(read_only=True)
    device_name = serializers.CharField(read_only=True)
    device_type = serializers.CharField(read_only=True)
    token_type = serializers.CharField(read_only=True, allow_null=True)
    push_enabled = serializers.BooleanField(read_only=True)
    token_updated_at = serializers.DateTimeField(read_only=True, allow_null=True)
    has_token = serializers.SerializerMethodField()

    def get_has_token(self, obj):
        """Check if device has a push token registered."""
        if hasattr(obj, 'device_token'):
            return bool(obj.device_token)
        return obj.get('device_token') is not None
