"""
Redis cache management for multi-address notification system.

This module provides cache warming, invalidation, and retrieval functions
for notification endpoints and member overrides. All cache operations are
designed for wasmCloud access via Redis capability provider.

ARCHITECTURE NOTE:
Django populates and manages Redis cache. wasmCloud actors read cache
via Redis capability provider (NO direct Redis connections from actors).

Cache Schema:
--------------

User Endpoints:
    Key: user:notification:endpoints:{user_id}
    TTL: 3600 seconds (1 hour)
    Format: {
        'user_id': str,
        'endpoints': [
            {
                'id': str,
                'channel_type': str,
                'label': str,
                'config': dict,
                'enabled': bool,
                'verified': bool,
                'routing_mode': str,
                'priority_filters': list
            },
            ...
        ],
        'cached_at': str (ISO format)
    }

Team Endpoints:
    Key: team:notification:endpoints:{team_id}
    TTL: 3600 seconds (1 hour)
    Format: {
        'team_id': str,
        'endpoints': [
            {
                'id': str,
                'channel_type': str,
                'label': str,
                'config': dict,
                'enabled': bool,
                'verified': bool,
                'routing_mode': str,
                'priority_filters': list
            },
            ...
        ],
        'cached_at': str (ISO format)
    }

Member Overrides:
    Key: team:notification:override:{team_id}:{user_id}
    TTL: 3600 seconds (1 hour)
    Format: {
        'team_id': str,
        'member_id': str,
        'team_notifications_enabled': bool,
        'disabled_endpoints': [str, ...],  # List of endpoint UUIDs
        'disabled_priorities': [str, ...],  # List of priority levels
        'updated_at': str (ISO format)
    }

Team Member Cache (Bulk):
    Key: team:notification:members:{team_id}
    TTL: 3600 seconds (1 hour)
    Format: {
        'team_id': str,
        'members': {
            'user_id': {
                'team_notifications_enabled': bool,
                'disabled_endpoints': [str, ...],
                'disabled_priorities': [str, ...]
            },
            ...
        },
        'cached_at': str (ISO format)
    }
"""

import logging
from typing import Dict, Any, List, Optional
from django.core.cache import cache
from django.utils import timezone
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

logger = logging.getLogger(__name__)

# Cache TTL in seconds (1 hour)
CACHE_TTL = 3600


def get_user_endpoints_cache_key(user_id: str) -> str:
    """Generate cache key for user endpoints."""
    return f"user:notification:endpoints:{user_id}"


def get_team_endpoints_cache_key(team_id: str) -> str:
    """Generate cache key for team endpoints."""
    return f"team:notification:endpoints:{team_id}"


def get_member_override_cache_key(team_id: str, user_id: str) -> str:
    """Generate cache key for member override."""
    return f"team:notification:override:{team_id}:{user_id}"


def get_team_members_cache_key(team_id: str) -> str:
    """Generate cache key for all team member overrides."""
    return f"team:notification:members:{team_id}"


def warm_user_endpoint_cache(user_id: str) -> Dict[str, Any]:
    """
    Warm cache for user notification endpoints.

    Args:
        user_id: UUID of the user

    Returns:
        Cache data structure
    """
    from app.models.notifications import NotificationChannelEndpoint

    endpoints = NotificationChannelEndpoint.objects.filter(
        owner_type='user',
        owner_id=user_id
    ).order_by('-created_at')

    cache_data = {
        'user_id': str(user_id),
        'endpoints': [ep.to_cache_format() for ep in endpoints],
        'cached_at': timezone.now().isoformat()
    }

    cache_key = get_user_endpoints_cache_key(user_id)
    cache.set(cache_key, cache_data, CACHE_TTL)

    logger.debug(
        f"Warmed user endpoint cache: {cache_key} "
        f"({len(cache_data['endpoints'])} endpoints)"
    )

    return cache_data


def warm_team_endpoint_cache(team_id: str) -> Dict[str, Any]:
    """
    Warm cache for team notification endpoints.

    Args:
        team_id: UUID of the team

    Returns:
        Cache data structure
    """
    from app.models.notifications import NotificationChannelEndpoint

    endpoints = NotificationChannelEndpoint.objects.filter(
        owner_type='team',
        owner_id=team_id
    ).order_by('-created_at')

    cache_data = {
        'team_id': str(team_id),
        'endpoints': [ep.to_cache_format() for ep in endpoints],
        'cached_at': timezone.now().isoformat()
    }

    cache_key = get_team_endpoints_cache_key(team_id)
    cache.set(cache_key, cache_data, CACHE_TTL)

    logger.debug(
        f"Warmed team endpoint cache: {cache_key} "
        f"({len(cache_data['endpoints'])} endpoints)"
    )

    return cache_data


def warm_member_override_cache(team_id: str, user_id: str) -> Dict[str, Any]:
    """
    Warm cache for team member notification override.

    Args:
        team_id: UUID of the team
        user_id: UUID of the user

    Returns:
        Cache data structure
    """
    from app.models.notifications import TeamMemberNotificationOverride

    try:
        override = TeamMemberNotificationOverride.objects.get(
            team_id=team_id,
            member_id=user_id
        )
        cache_data = override.to_cache_format()
    except TeamMemberNotificationOverride.DoesNotExist:
        # Default: all notifications enabled
        cache_data = {
            'team_id': str(team_id),
            'member_id': str(user_id),
            'team_notifications_enabled': True,
            'disabled_endpoints': [],
            'disabled_priorities': [],
            'updated_at': timezone.now().isoformat()
        }

    cache_key = get_member_override_cache_key(team_id, user_id)
    cache.set(cache_key, cache_data, CACHE_TTL)

    logger.debug(f"Warmed member override cache: {cache_key}")

    return cache_data


def warm_team_members_cache(team_id: str) -> Dict[str, Any]:
    """
    Warm cache for all team member overrides (bulk operation).

    This is useful for wasmCloud actors that need to check overrides
    for all team members when routing team alerts.

    Args:
        team_id: UUID of the team

    Returns:
        Cache data structure with all member overrides
    """
    from app.models.notifications import TeamMemberNotificationOverride
    from organizations.models import TeamMember

    # Get all active team members
    team_members = TeamMember.objects.filter(
        team_id=team_id,
        is_active=True
    ).values_list('user_id', flat=True)

    # Get all overrides for this team
    overrides = TeamMemberNotificationOverride.objects.filter(
        team_id=team_id
    )

    # Build member override map
    override_map = {
        str(override.member_id): {
            'team_notifications_enabled': override.team_notifications_enabled,
            'disabled_endpoints': [str(ep_id) for ep_id in override.disabled_endpoints],
            'disabled_priorities': override.disabled_priorities
        }
        for override in overrides
    }

    # Add default overrides for members without explicit overrides
    for member_id in team_members:
        member_id_str = str(member_id)
        if member_id_str not in override_map:
            override_map[member_id_str] = {
                'team_notifications_enabled': True,
                'disabled_endpoints': [],
                'disabled_priorities': []
            }

    cache_data = {
        'team_id': str(team_id),
        'members': override_map,
        'cached_at': timezone.now().isoformat()
    }

    cache_key = get_team_members_cache_key(team_id)
    cache.set(cache_key, cache_data, CACHE_TTL)

    logger.debug(
        f"Warmed team members cache: {cache_key} "
        f"({len(override_map)} members)"
    )

    return cache_data


def invalidate_user_endpoint_cache(user_id: str) -> None:
    """Invalidate user endpoint cache."""
    cache_key = get_user_endpoints_cache_key(user_id)
    cache.delete(cache_key)
    logger.debug(f"Invalidated cache: {cache_key}")


def invalidate_team_endpoint_cache(team_id: str) -> None:
    """Invalidate team endpoint cache."""
    cache_key = get_team_endpoints_cache_key(team_id)
    cache.delete(cache_key)
    logger.debug(f"Invalidated cache: {cache_key}")


def invalidate_member_override_cache(team_id: str, user_id: str) -> None:
    """Invalidate member override cache."""
    cache_key = get_member_override_cache_key(team_id, user_id)
    cache.delete(cache_key)
    logger.debug(f"Invalidated cache: {cache_key}")


def invalidate_team_members_cache(team_id: str) -> None:
    """Invalidate team members bulk cache."""
    cache_key = get_team_members_cache_key(team_id)
    cache.delete(cache_key)
    logger.debug(f"Invalidated cache: {cache_key}")


def get_cached_user_endpoints(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve cached user endpoints.

    Returns None if cache miss, otherwise returns cache data.
    """
    cache_key = get_user_endpoints_cache_key(user_id)
    return cache.get(cache_key)


def get_cached_team_endpoints(team_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve cached team endpoints.

    Returns None if cache miss, otherwise returns cache data.
    """
    cache_key = get_team_endpoints_cache_key(team_id)
    return cache.get(cache_key)


def get_cached_member_override(team_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve cached member override.

    Returns None if cache miss, otherwise returns cache data.
    """
    cache_key = get_member_override_cache_key(team_id, user_id)
    return cache.get(cache_key)


def get_cached_team_members(team_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve cached team members overrides (bulk).

    Returns None if cache miss, otherwise returns cache data.
    """
    cache_key = get_team_members_cache_key(team_id)
    return cache.get(cache_key)


# Signal handlers for automatic cache warming
@receiver(post_save, sender='app.NotificationChannelEndpoint')
def warm_endpoint_cache_on_save(sender, instance, created, **kwargs):
    """Automatically warm cache when endpoint is created or updated."""
    if instance.owner_type == 'user':
        warm_user_endpoint_cache(instance.owner_id)
    elif instance.owner_type == 'team':
        warm_team_endpoint_cache(instance.owner_id)
        # Also invalidate team members bulk cache
        invalidate_team_members_cache(instance.owner_id)


@receiver(post_delete, sender='app.NotificationChannelEndpoint')
def invalidate_endpoint_cache_on_delete(sender, instance, **kwargs):
    """Invalidate cache when endpoint is deleted."""
    if instance.owner_type == 'user':
        invalidate_user_endpoint_cache(instance.owner_id)
    elif instance.owner_type == 'team':
        invalidate_team_endpoint_cache(instance.owner_id)
        # Also invalidate team members bulk cache
        invalidate_team_members_cache(instance.owner_id)


@receiver(post_save, sender='app.TeamMemberNotificationOverride')
def warm_override_cache_on_save(sender, instance, created, **kwargs):
    """Automatically warm cache when override is created or updated."""
    warm_member_override_cache(instance.team_id, instance.member_id)
    # Also invalidate team members bulk cache
    invalidate_team_members_cache(instance.team_id)


@receiver(post_delete, sender='app.TeamMemberNotificationOverride')
def invalidate_override_cache_on_delete(sender, instance, **kwargs):
    """Invalidate cache when override is deleted."""
    invalidate_member_override_cache(instance.team_id, instance.member_id)
    # Also invalidate team members bulk cache
    invalidate_team_members_cache(instance.team_id)
