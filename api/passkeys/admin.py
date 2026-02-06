from django.contrib import admin
from .models import PasskeyDevice, PasskeyChallenge


@admin.register(PasskeyDevice)
class PasskeyDeviceAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'created_at', 'last_used_at', 'is_active']
    list_filter = ['is_active', 'backup_eligible', 'backup_state', 'created_at']
    search_fields = ['user__email', 'name', 'aaguid', 'credential_id']
    readonly_fields = ['id', 'credential_id', 'public_key', 'aaguid', 'sign_count', 
                      'backup_eligible', 'backup_state', 'created_at', 'last_used_at']
    
    fieldsets = (
        ('Device Information', {
            'fields': ('id', 'user', 'name', 'is_active')
        }),
        ('Credential Details', {
            'fields': ('credential_id', 'public_key', 'aaguid', 'sign_count'),
            'classes': ('collapse',)
        }),
        ('Security Features', {
            'fields': ('backup_eligible', 'backup_state')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'last_used_at')
        })
    )
    
    def has_add_permission(self, request):
        # Passkeys should only be created through the WebAuthn flow
        return False


@admin.register(PasskeyChallenge)
class PasskeyChallengeAdmin(admin.ModelAdmin):
    list_display = ['challenge', 'user', 'operation', 'created_at', 'expires_at', 'is_valid']
    list_filter = ['operation', 'created_at', 'expires_at']
    search_fields = ['challenge', 'user__email']
    readonly_fields = ['id', 'challenge', 'user', 'operation', 'data', 'created_at', 'expires_at']
    
    def is_valid(self, obj):
        return obj.is_valid()
    is_valid.boolean = True
    is_valid.short_description = 'Valid'
    
    def has_add_permission(self, request):
        # Challenges should only be created through the WebAuthn flow
        return False
    
    def has_change_permission(self, request, obj=None):
        # Challenges should not be edited
        return False