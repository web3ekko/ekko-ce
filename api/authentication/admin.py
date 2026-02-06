"""
Django Admin Configuration for Authentication Models

Provides admin interface for managing:
- Users and authentication settings
- Devices and trust management
- Authentication logs and security monitoring
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone

from .models import User, UserDevice, AuthenticationLog, EmailVerificationCode


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Admin interface for User model
    """
    list_display = [
        'email', 'full_name', 'preferred_auth_method', 'has_passkey',
        'has_2fa', 'is_email_verified', 'is_active', 'created_at'
    ]
    list_filter = [
        'preferred_auth_method', 'has_passkey', 'has_2fa',
        'is_email_verified', 'is_active', 'created_at'
    ]
    search_fields = ['email', 'first_name', 'last_name']
    ordering = ['-created_at']

    fieldsets = (
        (None, {
            'fields': ('email', 'password')
        }),
        ('Personal info', {
            'fields': ('first_name', 'last_name')
        }),
        ('Authentication', {
            'fields': (
                'preferred_auth_method', 'has_passkey', 'has_2fa',
                'is_email_verified', 'last_login_method'
            )
        }),
        ('Permissions', {
            'fields': (
                'is_active', 'is_staff', 'is_superuser',
                'groups', 'user_permissions'
            ),
        }),
        ('Important dates', {
            'fields': ('last_login', 'date_joined', 'created_at', 'updated_at')
        }),
    )

    readonly_fields = ['created_at', 'updated_at', 'last_login_method']

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'password1', 'password2'),
        }),
    )


@admin.register(UserDevice)
class UserDeviceAdmin(admin.ModelAdmin):
    """
    Admin interface for UserDevice model
    """
    list_display = [
        'device_name', 'user_email', 'device_type', 'supports_passkey',
        'is_trusted', 'is_active', 'last_used', 'trust_status'
    ]
    list_filter = [
        'device_type', 'supports_passkey', 'supports_biometric',
        'is_trusted', 'is_active', 'created_at'
    ]
    search_fields = ['device_name', 'user__email', 'device_id']
    ordering = ['-last_used']

    readonly_fields = ['device_fingerprint', 'created_at', 'last_used', 'trust_status']

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User Email'

    def trust_status(self, obj):
        if not obj.is_trusted:
            return format_html('<span style="color: gray;">Not Trusted</span>')
        elif obj.is_trust_expired:
            return format_html('<span style="color: red;">Trust Expired</span>')
        else:
            return format_html('<span style="color: green;">Trusted</span>')
    trust_status.short_description = 'Trust Status'


@admin.register(EmailVerificationCode)
class EmailVerificationCodeAdmin(admin.ModelAdmin):
    """
    Admin interface for EmailVerificationCode model
    """
    list_display = ['code_masked', 'email', 'purpose', 'is_used', 'is_expired', 'created_at', 'expires_at']
    list_filter = ['purpose', 'used_at', 'created_at', 'expires_at']
    search_fields = ['email', 'user__email']
    ordering = ['-created_at']

    readonly_fields = ['code', 'used_at', 'created_at', 'expires_at']

    def code_masked(self, obj):
        """Show masked verification code for security"""
        if obj.code:
            return f"{obj.code[:2]}****"
        return "N/A"
    code_masked.short_description = 'Verification Code'
    
    def is_used(self, obj):
        return obj.is_used
    is_used.boolean = True
    is_used.short_description = 'Used'


@admin.register(AuthenticationLog)
class AuthenticationLogAdmin(admin.ModelAdmin):
    """
    Admin interface for AuthenticationLog model
    """
    list_display = [
        'timestamp', 'user_email', 'method', 'success_status',
        'ip_address', 'device_type'
    ]
    list_filter = ['method', 'success', 'timestamp']
    search_fields = ['user__email', 'ip_address', 'user_agent']
    ordering = ['-timestamp']

    readonly_fields = [
        'user', 'method', 'success', 'failure_reason',
        'ip_address', 'user_agent', 'device_info', 'timestamp'
    ]

    def user_email(self, obj):
        return obj.user.email if obj.user else 'Unknown'
    user_email.short_description = 'User Email'

    def success_status(self, obj):
        if obj.success:
            return format_html('<span style="color: green;">✓ Success</span>')
        else:
            return format_html('<span style="color: red;">✗ Failed</span>')
    success_status.short_description = 'Status'

    def device_type(self, obj):
        return obj.device_info.get('device_type', 'Unknown') if obj.device_info else 'Unknown'
    device_type.short_description = 'Device Type'



# Customize admin site
admin.site.site_header = "Ekko API Administration"
admin.site.site_title = "Ekko API Admin"
admin.site.index_title = "Passwordless Authentication System"
