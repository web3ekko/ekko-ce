"""
Example Django signals integration with NotificationCacheManager.

Shows how to automatically invalidate caches when models are saved/deleted.
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from blockchain.models_wallet_nicknames import WalletNickname
from app.models.notifications import UserNotificationSettings
from app.services.notification_cache import NotificationCacheManager


# ===================================================================
# Example 1: Auto-invalidate wallet nicknames cache on save/delete
# ===================================================================

@receiver(post_save, sender=WalletNickname)
def invalidate_wallet_nickname_cache_on_save(sender, instance, **kwargs):
    """
    Invalidate wallet nicknames cache when a nickname is created or updated.

    This ensures the Redis cache stays in sync with PostgreSQL.
    """
    cache_manager = NotificationCacheManager()
    cache_manager.invalidate_wallet_nicknames(str(instance.user_id))


@receiver(post_delete, sender=WalletNickname)
def invalidate_wallet_nickname_cache_on_delete(sender, instance, **kwargs):
    """
    Invalidate wallet nicknames cache when a nickname is deleted.
    """
    cache_manager = NotificationCacheManager()
    cache_manager.invalidate_wallet_nicknames(str(instance.user_id))


# ===================================================================
# Example 2: Auto-invalidate user settings cache on save/delete
# ===================================================================

@receiver(post_save, sender=UserNotificationSettings)
def invalidate_user_settings_cache_on_save(sender, instance, **kwargs):
    """
    Invalidate user notification settings cache when settings are updated.

    Note: UserNotificationSettings model already has invalidate_cache() in its
    save() method, so this signal is redundant but shown for completeness.
    """
    cache_manager = NotificationCacheManager()
    cache_manager.invalidate_user_cache(str(instance.user_id))


@receiver(post_delete, sender=UserNotificationSettings)
def invalidate_user_settings_cache_on_delete(sender, instance, **kwargs):
    """
    Invalidate user notification settings cache when settings are deleted.
    """
    cache_manager = NotificationCacheManager()
    cache_manager.invalidate_user_cache(str(instance.user_id))


# ===================================================================
# Example 3: Proactive cache warming on user login
# ===================================================================

from django.contrib.auth.signals import user_logged_in

@receiver(user_logged_in)
def warm_cache_on_login(sender, request, user, **kwargs):
    """
    Pre-warm caches when a user logs in for better performance.

    This ensures their wallet nicknames and notification settings
    are already in Redis when they start using the app.
    """
    cache_manager = NotificationCacheManager()

    # Cache wallet nicknames
    cache_manager.cache_wallet_nicknames(str(user.id))

    # Cache notification settings
    cache_manager.cache_user_settings(str(user.id))


# ===================================================================
# Example 4: Alert subscription management
# ===================================================================

# In your AlertInstance or AlertTemplate model:

"""
from django.db import models
from app.services.notification_cache import NotificationCacheManager

class AlertInstance(models.Model):
    # ... your fields ...

    def add_subscriber(self, user_id: str):
        '''Add a user to this alert's subscriber list'''
        # Add to database
        # ... your database logic ...

        # Update Redis cache
        cache_manager = NotificationCacheManager()
        cache_manager.add_subscriber_to_template(str(self.template_id), user_id)

    def remove_subscriber(self, user_id: str):
        '''Remove a user from this alert's subscriber list'''
        # Remove from database
        # ... your database logic ...

        # Update Redis cache
        cache_manager = NotificationCacheManager()
        cache_manager.remove_subscriber_from_template(str(self.template_id), user_id)
"""


# ===================================================================
# Example 5: Management command for cache warming
# ===================================================================

"""
Create this file: app/management/commands/warm_notification_cache.py

from django.core.management.base import BaseCommand
from app.services.notification_cache import NotificationCacheManager


class Command(BaseCommand):
    help = 'Warm notification caches for active users'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=1000,
            help='Maximum number of users to cache (default: 1000)'
        )

    def handle(self, *args, **options):
        limit = options['limit']
        cache_manager = NotificationCacheManager()

        self.stdout.write('Warming notification caches...')
        cached_count = cache_manager.warm_cache_for_active_users(limit=limit)

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully cached data for {cached_count} users'
            )
        )

# Usage:
# python manage.py warm_notification_cache --limit 5000
"""


# ===================================================================
# Example 6: Health check endpoint
# ===================================================================

"""
Add to your views.py:

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from app.services.notification_cache import NotificationCacheManager


@api_view(['GET'])
@permission_classes([IsAdminUser])
def notification_cache_health(request):
    '''Health check endpoint for notification cache system'''
    cache_manager = NotificationCacheManager()
    health_status = cache_manager.health_check()

    status_code = 200 if health_status['status'] == 'healthy' else 503

    return Response(health_status, status=status_code)

# URL pattern:
# path('admin/health/notification-cache/', notification_cache_health, name='notification-cache-health'),
"""


# ===================================================================
# Example 7: Periodic cache refresh with Celery
# ===================================================================

"""
Create this file: app/tasks.py (if using Celery)

from celery import shared_task
from app.services.notification_cache import NotificationCacheManager
import logging

logger = logging.getLogger(__name__)


@shared_task
def warm_notification_cache_periodic():
    '''
    Periodic task to warm notification caches.

    Schedule this task to run every few hours to keep caches fresh.
    '''
    cache_manager = NotificationCacheManager()
    cached_count = cache_manager.warm_cache_for_active_users(limit=2000)

    logger.info(f'Periodic cache warming completed: {cached_count} users cached')
    return cached_count


# In celery.py or settings.py, add to CELERY_BEAT_SCHEDULE:
CELERY_BEAT_SCHEDULE = {
    'warm-notification-cache': {
        'task': 'app.tasks.warm_notification_cache_periodic',
        'schedule': 3600.0,  # Run every hour
    },
}
"""
