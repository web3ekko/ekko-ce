"""
Profile Serializers for User Profile Management API
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()


class ProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile data"""

    full_name = serializers.CharField(read_only=True)
    has_passkey = serializers.BooleanField(read_only=True)
    has_2fa = serializers.BooleanField(read_only=True)
    is_email_verified = serializers.BooleanField(read_only=True)
    member_since = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name',
            'preferred_auth_method', 'is_email_verified', 'has_passkey',
            'has_2fa', 'last_login_method', 'member_since',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'email', 'full_name', 'is_email_verified',
            'has_passkey', 'has_2fa', 'last_login_method',
            'created_at', 'updated_at', 'member_since'
        ]


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile"""

    class Meta:
        model = User
        fields = ['first_name', 'last_name']


class PreferencesSerializer(serializers.Serializer):
    """Serializer for user preferences"""

    preferred_auth_method = serializers.ChoiceField(
        choices=[('passkey', 'Passkey'), ('email', 'Email Magic Link')],
        required=False
    )
    notification_preferences = serializers.DictField(required=False, default=dict)
    theme = serializers.ChoiceField(
        choices=[('light', 'Light'), ('dark', 'Dark'), ('system', 'System')],
        required=False,
        default='system'
    )
    timezone = serializers.CharField(required=False, max_length=50, default='UTC')
    language = serializers.CharField(required=False, max_length=10, default='en')


class ConnectedServiceSerializer(serializers.Serializer):
    """Serializer for connected services/devices"""

    id = serializers.UUIDField(read_only=True)
    service_type = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)
    connected_at = serializers.DateTimeField(read_only=True)
    last_used = serializers.DateTimeField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)


class SessionSerializer(serializers.Serializer):
    """Serializer for user sessions (Knox tokens)"""

    id = serializers.CharField(read_only=True)  # Token digest
    device_info = serializers.CharField(read_only=True)
    ip_address = serializers.IPAddressField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    last_used = serializers.DateTimeField(read_only=True)
    expires_at = serializers.DateTimeField(read_only=True)
    is_current = serializers.BooleanField(read_only=True)


class ExportRequestSerializer(serializers.Serializer):
    """Serializer for data export request"""

    format = serializers.ChoiceField(
        choices=[('json', 'JSON'), ('csv', 'CSV')],
        default='json'
    )
    include_alerts = serializers.BooleanField(default=True)
    include_wallets = serializers.BooleanField(default=True)
    include_transactions = serializers.BooleanField(default=True)
    include_activity = serializers.BooleanField(default=True)


class ExportResponseSerializer(serializers.Serializer):
    """Serializer for data export response"""

    export_id = serializers.UUIDField(read_only=True)
    status = serializers.CharField(read_only=True)
    download_url = serializers.URLField(read_only=True)
    expires_at = serializers.DateTimeField(read_only=True)
    message = serializers.CharField(read_only=True)


class DeleteAccountSerializer(serializers.Serializer):
    """Serializer for account deletion confirmation"""

    confirmation = serializers.CharField(required=True)

    def validate_confirmation(self, value):
        """Verify the user typed 'DELETE' to confirm"""
        if value != 'DELETE':
            raise serializers.ValidationError(
                "Please type 'DELETE' to confirm account deletion"
            )
        return value
