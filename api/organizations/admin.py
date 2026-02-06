"""
Django Admin Configuration for Organization Models
"""

from django.contrib import admin
from .models import Organization, Team, TeamMember, UserSettings


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'max_teams', 'max_users_per_team', 'passkey_required', 'created_at']
    list_filter = ['passkey_required', 'created_at']
    search_fields = ['name', 'slug', 'description']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['name']


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ['name', 'organization', 'slug', 'is_active', 'max_members', 'created_at']
    list_filter = ['organization', 'is_active', 'created_at']
    search_fields = ['name', 'slug', 'description', 'organization__name']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['organization__name', 'name']


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ['user', 'team', 'role', 'is_active', 'joined_at']
    list_filter = ['role', 'is_active', 'joined_at', 'team__organization']
    search_fields = ['user__email', 'team__name', 'team__organization__name']
    ordering = ['-joined_at']


@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    list_display = ['user', 'mute', 'created_at']
    list_filter = ['mute', 'created_at']
    search_fields = ['user__email']
    ordering = ['user__email']
