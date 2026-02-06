"""
Unit tests for Multi-Address Notification System models
Tests NotificationChannelEndpoint, TeamMemberNotificationOverride, and NotificationChannelVerification models
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta

from app.models.notifications import (
    NotificationChannelEndpoint,
    NotificationChannelPreferences,
    TeamMemberNotificationOverride,
    NotificationChannelVerification,
)
from organizations.models import Organization, Team, TeamMember, TeamMemberRole

User = get_user_model()


class TestNotificationChannelPreferencesModel(TestCase):
    """Test NotificationChannelPreferences model functionality"""

    def setUp(self):
        """Set up test data before each test method"""
        self.user = User.objects.create_user(
            email="preferences@example.com",
            first_name="Preferences",
            last_name="User"
        )

    def test_preference_creation(self):
        """Test creating a channel preference"""
        preference = NotificationChannelPreferences.objects.create(
            user=self.user,
            channel='email',
            enabled=True,
            priority_filter=['critical', 'high']
        )

        self.assertEqual(preference.user, self.user)
        self.assertEqual(preference.channel, 'email')
        self.assertTrue(preference.enabled)
        self.assertEqual(preference.priority_filter, ['critical', 'high'])

    def test_preference_default_values(self):
        """Test default values for channel preferences"""
        preference = NotificationChannelPreferences.objects.create(
            user=self.user,
            channel='slack'
        )

        self.assertTrue(preference.enabled)
        self.assertEqual(preference.priority_filter, [])

    def test_all_channel_types(self):
        """Test creating preferences for all supported channel types"""
        channels = ['email', 'slack', 'telegram', 'discord', 'webhook',
                    'websocket', 'sms', 'push', 'whatsapp']

        for channel in channels:
            preference = NotificationChannelPreferences.objects.create(
                user=self.user,
                channel=channel,
                enabled=True
            )
            self.assertEqual(preference.channel, channel)

    def test_unique_together_constraint(self):
        """Test that user + channel must be unique"""
        NotificationChannelPreferences.objects.create(
            user=self.user,
            channel='email',
            enabled=True
        )

        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            NotificationChannelPreferences.objects.create(
                user=self.user,
                channel='email',
                enabled=False
            )

    def test_disable_channel(self):
        """Test disabling a channel preference"""
        preference = NotificationChannelPreferences.objects.create(
            user=self.user,
            channel='push',
            enabled=True
        )

        preference.enabled = False
        preference.save()

        preference.refresh_from_db()
        self.assertFalse(preference.enabled)

    def test_priority_filter_update(self):
        """Test updating priority filter"""
        preference = NotificationChannelPreferences.objects.create(
            user=self.user,
            channel='telegram',
            enabled=True,
            priority_filter=[]
        )

        preference.priority_filter = ['critical']
        preference.save()

        preference.refresh_from_db()
        self.assertEqual(preference.priority_filter, ['critical'])

    def test_get_cached_preferences(self):
        """Test getting cached preferences for a user"""
        # Create multiple preferences
        NotificationChannelPreferences.objects.create(
            user=self.user,
            channel='email',
            enabled=True
        )
        NotificationChannelPreferences.objects.create(
            user=self.user,
            channel='slack',
            enabled=False
        )
        NotificationChannelPreferences.objects.create(
            user=self.user,
            channel='push',
            enabled=True,
            priority_filter=['critical']
        )

        cached = NotificationChannelPreferences.get_cached_preferences(self.user.id)

        self.assertEqual(cached['user_id'], str(self.user.id))
        self.assertEqual(len(cached['preferences']), 3)
        self.assertIn('cached_at', cached)

    def test_is_channel_enabled(self):
        """Test checking if a channel is enabled"""
        # Create enabled preference
        NotificationChannelPreferences.objects.create(
            user=self.user,
            channel='email',
            enabled=True
        )
        # Create disabled preference
        NotificationChannelPreferences.objects.create(
            user=self.user,
            channel='slack',
            enabled=False
        )

        self.assertTrue(
            NotificationChannelPreferences.is_channel_enabled(self.user.id, 'email')
        )
        self.assertFalse(
            NotificationChannelPreferences.is_channel_enabled(self.user.id, 'slack')
        )
        # Non-existent preference defaults to True
        self.assertTrue(
            NotificationChannelPreferences.is_channel_enabled(self.user.id, 'push')
        )

    def test_to_cache_format(self):
        """Test serialization to cache format"""
        preference = NotificationChannelPreferences.objects.create(
            user=self.user,
            channel='discord',
            enabled=True,
            priority_filter=['critical', 'high']
        )

        cache_data = preference.to_cache_format()

        self.assertEqual(cache_data['id'], str(preference.id))
        self.assertEqual(cache_data['channel'], 'discord')
        self.assertTrue(cache_data['enabled'])
        self.assertEqual(cache_data['priority_filter'], ['critical', 'high'])
        self.assertIn('updated_at', cache_data)


class TestNotificationChannelEndpointModel(TestCase):
    """Test NotificationChannelEndpoint model functionality"""

    def setUp(self):
        """Set up test data before each test method"""
        self.user = User.objects.create_user(
            email="endpoint@example.com",
            first_name="Endpoint",
            last_name="User"
        )
        self.organization = Organization.objects.create(
            name="Test Org",
            slug="test-org"
        )
        self.team = Team.objects.create(
            organization=self.organization,
            name="Test Team",
            slug="test-team"
        )
        TeamMember.objects.create(
            team=self.team,
            user=self.user,
            role=TeamMemberRole.OWNER
        )

    def test_user_endpoint_creation(self):
        """Test creating a user-owned notification endpoint"""
        endpoint = NotificationChannelEndpoint.objects.create(
            owner_type='user',
            owner_id=self.user.id,
            channel_type='email',
            label='Personal Gmail',
            config={'address': 'user@gmail.com'},
            enabled=True,
            verified=True,
            routing_mode='all_enabled',
            priority_filters=[],
            created_by=self.user
        )

        self.assertEqual(endpoint.owner_type, 'user')
        self.assertEqual(endpoint.owner_id, self.user.id)
        self.assertEqual(endpoint.channel_type, 'email')
        self.assertEqual(endpoint.label, 'Personal Gmail')
        self.assertTrue(endpoint.enabled)
        self.assertTrue(endpoint.verified)
        self.assertEqual(endpoint.routing_mode, 'all_enabled')
        self.assertEqual(endpoint.priority_filters, [])

    def test_team_endpoint_creation(self):
        """Test creating a team-owned notification endpoint"""
        endpoint = NotificationChannelEndpoint.objects.create(
            owner_type='team',
            owner_id=self.team.id,
            channel_type='slack',
            label='Team Channel',
            config={'webhook_url': 'https://hooks.slack.com/services/...'},
            enabled=True,
            verified=True,
            routing_mode='priority_based',
            priority_filters=['critical', 'high'],
            created_by=self.user
        )

        self.assertEqual(endpoint.owner_type, 'team')
        self.assertEqual(endpoint.owner_id, self.team.id)
        self.assertEqual(endpoint.channel_type, 'slack')
        self.assertEqual(endpoint.routing_mode, 'priority_based')
        self.assertEqual(endpoint.priority_filters, ['critical', 'high'])

    def test_multiple_endpoints_same_channel(self):
        """Test creating multiple endpoints of the same channel type for one user"""
        # Create first email endpoint
        email1 = NotificationChannelEndpoint.objects.create(
            owner_type='user',
            owner_id=self.user.id,
            channel_type='email',
            label='Personal Gmail',
            config={'address': 'personal@gmail.com'},
            created_by=self.user
        )

        # Create second email endpoint
        email2 = NotificationChannelEndpoint.objects.create(
            owner_type='user',
            owner_id=self.user.id,
            channel_type='email',
            label='Work Email',
            config={'address': 'work@company.com'},
            created_by=self.user
        )

        # Both should exist
        user_endpoints = NotificationChannelEndpoint.objects.filter(
            owner_type='user',
            owner_id=self.user.id
        )
        self.assertEqual(user_endpoints.count(), 2)
        self.assertIn(email1, user_endpoints)
        self.assertIn(email2, user_endpoints)

    def test_endpoint_requires_reverification(self):
        """Test requires_reverification property for different channel types"""
        # Channels that require verification
        email_endpoint = NotificationChannelEndpoint(channel_type='email')
        telegram_endpoint = NotificationChannelEndpoint(channel_type='telegram')
        sms_endpoint = NotificationChannelEndpoint(channel_type='sms')

        self.assertTrue(email_endpoint.requires_reverification)
        self.assertTrue(telegram_endpoint.requires_reverification)
        self.assertTrue(sms_endpoint.requires_reverification)

        # Channels that auto-verify
        webhook_endpoint = NotificationChannelEndpoint(channel_type='webhook')
        slack_endpoint = NotificationChannelEndpoint(channel_type='slack')

        self.assertFalse(webhook_endpoint.requires_reverification)
        self.assertFalse(slack_endpoint.requires_reverification)

    def test_endpoint_to_cache_format(self):
        """Test serialization to cache format"""
        endpoint = NotificationChannelEndpoint.objects.create(
            owner_type='user',
            owner_id=self.user.id,
            channel_type='email',
            label='Personal Gmail',
            config={'address': 'user@gmail.com'},
            enabled=True,
            verified=True,
            routing_mode='priority_based',
            priority_filters=['critical', 'high'],
            created_by=self.user
        )

        cache_data = endpoint.to_cache_format()

        self.assertEqual(cache_data['id'], str(endpoint.id))
        self.assertEqual(cache_data['channel_type'], 'email')
        self.assertEqual(cache_data['label'], 'Personal Gmail')
        self.assertEqual(cache_data['config'], {'address': 'user@gmail.com'})
        self.assertTrue(cache_data['enabled'])
        self.assertTrue(cache_data['verified'])
        self.assertEqual(cache_data['routing_mode'], 'priority_based')
        self.assertEqual(cache_data['priority_filters'], ['critical', 'high'])

    def test_endpoint_config_validation(self):
        """Test config field validation for different channel types"""
        # Valid email config
        email_endpoint = NotificationChannelEndpoint(
            owner_type='user',
            owner_id=self.user.id,
            channel_type='email',
            label='Email',
            config={'address': 'test@example.com'},
            priority_filters=[],
            created_by=self.user
        )
        try:
            email_endpoint.full_clean()
        except ValidationError:
            self.fail("Email endpoint validation should pass with valid config")

        # Valid telegram config
        telegram_endpoint = NotificationChannelEndpoint(
            owner_type='user',
            owner_id=self.user.id,
            channel_type='telegram',
            label='Telegram',
            config={'chat_id': '123456789'},
            priority_filters=[],
            created_by=self.user
        )
        try:
            telegram_endpoint.full_clean()
        except ValidationError:
            self.fail("Telegram endpoint validation should pass with valid config")


class TestTeamMemberNotificationOverrideModel(TestCase):
    """Test TeamMemberNotificationOverride model functionality"""

    def setUp(self):
        """Set up test data before each test method"""
        self.user = User.objects.create_user(
            email="member@example.com",
            first_name="Member",
            last_name="User"
        )
        self.organization = Organization.objects.create(
            name="Test Org",
            slug="test-org"
        )
        self.team = Team.objects.create(
            organization=self.organization,
            name="Test Team",
            slug="test-team"
        )
        TeamMember.objects.create(
            team=self.team,
            user=self.user,
            role=TeamMemberRole.MEMBER
        )
        self.endpoint = NotificationChannelEndpoint.objects.create(
            owner_type='team',
            owner_id=self.team.id,
            channel_type='slack',
            label='Team Slack',
            config={'webhook_url': 'https://hooks.slack.com/...'},
            created_by=self.user
        )

    def test_override_creation_defaults(self):
        """Test creating override with default values"""
        override = TeamMemberNotificationOverride.objects.create(
            team=self.team,
            member=self.user
        )

        self.assertTrue(override.team_notifications_enabled)
        self.assertEqual(override.disabled_endpoints, [])
        self.assertEqual(override.disabled_priorities, [])

    def test_override_disable_specific_endpoint(self):
        """Test disabling a specific endpoint for a team member"""
        override = TeamMemberNotificationOverride.objects.create(
            team=self.team,
            member=self.user,
            disabled_endpoints=[str(self.endpoint.id)]
        )

        self.assertEqual(len(override.disabled_endpoints), 1)
        self.assertIn(str(self.endpoint.id), override.disabled_endpoints)

    def test_override_disable_priorities(self):
        """Test disabling specific priority levels"""
        override = TeamMemberNotificationOverride.objects.create(
            team=self.team,
            member=self.user,
            disabled_priorities=['low', 'normal']
        )

        self.assertEqual(override.disabled_priorities, ['low', 'normal'])

    def test_override_master_switch(self):
        """Test team_notifications_enabled master switch"""
        override = TeamMemberNotificationOverride.objects.create(
            team=self.team,
            member=self.user,
            team_notifications_enabled=False
        )

        self.assertFalse(override.team_notifications_enabled)

    def test_override_to_cache_format(self):
        """Test serialization to cache format"""
        override = TeamMemberNotificationOverride.objects.create(
            team=self.team,
            member=self.user,
            team_notifications_enabled=True,
            disabled_endpoints=[str(self.endpoint.id)],
            disabled_priorities=['low']
        )

        cache_data = override.to_cache_format()

        self.assertEqual(cache_data['team_id'], str(self.team.id))
        self.assertEqual(cache_data['member_id'], str(self.user.id))
        self.assertTrue(cache_data['team_notifications_enabled'])
        self.assertEqual(cache_data['disabled_endpoints'], [str(self.endpoint.id)])
        self.assertEqual(cache_data['disabled_priorities'], ['low'])
        self.assertIn('updated_at', cache_data)

    def test_override_unique_together(self):
        """Test that one member can only have one override per team"""
        # Create first override
        TeamMemberNotificationOverride.objects.create(
            team=self.team,
            member=self.user
        )

        # Try to create duplicate - should raise IntegrityError
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            TeamMemberNotificationOverride.objects.create(
                team=self.team,
                member=self.user
            )


class TestNotificationChannelVerificationModel(TestCase):
    """Test NotificationChannelVerification model functionality"""

    def setUp(self):
        """Set up test data before each test method"""
        self.user = User.objects.create_user(
            email="verification@example.com",
            first_name="Verification",
            last_name="User"
        )
        self.endpoint = NotificationChannelEndpoint.objects.create(
            owner_type='user',
            owner_id=self.user.id,
            channel_type='email',
            label='Personal Email',
            config={'address': 'user@example.com'},
            verified=False,
            created_by=self.user
        )

    def test_verification_creation(self):
        """Test creating a verification code"""
        verification = NotificationChannelVerification.objects.create(
            endpoint=self.endpoint,
            verification_code='123456',
            verification_type='initial',
            expires_at=timezone.now() + timedelta(minutes=15)
        )

        self.assertEqual(verification.endpoint, self.endpoint)
        self.assertEqual(verification.verification_code, '123456')
        self.assertEqual(verification.verification_type, 'initial')
        self.assertIsNone(verification.verified_at)

    def test_verification_is_expired_false(self):
        """Test is_expired returns False for non-expired code"""
        verification = NotificationChannelVerification.objects.create(
            endpoint=self.endpoint,
            verification_code='123456',
            verification_type='initial',
            expires_at=timezone.now() + timedelta(minutes=10)
        )

        self.assertFalse(verification.is_expired())

    def test_verification_is_expired_true(self):
        """Test is_expired returns True for expired code"""
        verification = NotificationChannelVerification.objects.create(
            endpoint=self.endpoint,
            verification_code='123456',
            verification_type='initial',
            expires_at=timezone.now() - timedelta(minutes=1)
        )

        self.assertTrue(verification.is_expired())

    def test_verification_code_format(self):
        """Test that verification codes are 6 digits"""
        verification = NotificationChannelVerification.objects.create(
            endpoint=self.endpoint,
            verification_code='123456',
            verification_type='initial',
            expires_at=timezone.now() + timedelta(minutes=15)
        )

        self.assertEqual(len(verification.verification_code), 6)
        self.assertTrue(verification.verification_code.isdigit())

    def test_verification_types(self):
        """Test different verification types"""
        # Initial verification
        initial = NotificationChannelVerification.objects.create(
            endpoint=self.endpoint,
            verification_code='123456',
            verification_type='initial',
            expires_at=timezone.now() + timedelta(minutes=15)
        )
        self.assertEqual(initial.verification_type, 'initial')

        # Re-enable verification
        re_enable = NotificationChannelVerification.objects.create(
            endpoint=self.endpoint,
            verification_code='654321',
            verification_type='re_enable',
            expires_at=timezone.now() + timedelta(minutes=15)
        )
        self.assertEqual(re_enable.verification_type, 're_enable')

    def test_verification_marks_completed(self):
        """Test marking verification as completed"""
        verification = NotificationChannelVerification.objects.create(
            endpoint=self.endpoint,
            verification_code='123456',
            verification_type='initial',
            expires_at=timezone.now() + timedelta(minutes=15)
        )

        # Mark as verified
        verification.verified_at = timezone.now()
        verification.save()

        self.assertIsNotNone(verification.verified_at)
        self.assertLessEqual(
            verification.verified_at,
            timezone.now()
        )


class TestNotificationChannelPreferencesDeleteSignal(TestCase):
    """Test post_delete signal handler for NotificationChannelPreferences"""

    def setUp(self):
        """Set up test data before each test method"""
        self.user = User.objects.create_user(
            email="delete_signal@example.com",
            first_name="Delete",
            last_name="Signal"
        )

    def test_delete_preference_updates_cache(self):
        """Test that deleting a preference updates the cache correctly"""
        from django.core.cache import cache

        # Create two preferences
        pref1 = NotificationChannelPreferences.objects.create(
            user=self.user,
            channel='email',
            enabled=True
        )
        pref2 = NotificationChannelPreferences.objects.create(
            user=self.user,
            channel='slack',
            enabled=False
        )

        # Verify cache has both preferences
        cache_key = f"user:channel_preferences:{self.user.id}"
        cached_data = cache.get(cache_key)
        self.assertIsNotNone(cached_data)
        self.assertEqual(len(cached_data['preferences']), 2)
        self.assertIn('email', cached_data['channel_lookup'])
        self.assertIn('slack', cached_data['channel_lookup'])

        # Delete one preference
        pref1.delete()

        # Verify cache is updated - should only have slack now
        cached_data = cache.get(cache_key)
        self.assertIsNotNone(cached_data)
        self.assertEqual(len(cached_data['preferences']), 1)
        self.assertNotIn('email', cached_data['channel_lookup'])
        self.assertIn('slack', cached_data['channel_lookup'])

    def test_delete_last_preference_clears_cache(self):
        """Test that deleting the last preference clears the cache"""
        from django.core.cache import cache

        # Create single preference
        pref = NotificationChannelPreferences.objects.create(
            user=self.user,
            channel='push',
            enabled=True
        )

        # Verify cache exists
        cache_key = f"user:channel_preferences:{self.user.id}"
        cached_data = cache.get(cache_key)
        self.assertIsNotNone(cached_data)

        # Delete the preference
        pref.delete()

        # Verify cache is cleared (deleted)
        cached_data = cache.get(cache_key)
        self.assertIsNone(cached_data)

    def test_delete_preserves_other_users_cache(self):
        """Test that deleting one user's preference doesn't affect others"""
        from django.core.cache import cache

        # Create another user
        other_user = User.objects.create_user(
            email="other@example.com",
            first_name="Other",
            last_name="User"
        )

        # Create preferences for both users
        pref1 = NotificationChannelPreferences.objects.create(
            user=self.user,
            channel='email',
            enabled=True
        )
        pref2 = NotificationChannelPreferences.objects.create(
            user=other_user,
            channel='email',
            enabled=True
        )

        # Verify both caches exist
        cache_key1 = f"user:channel_preferences:{self.user.id}"
        cache_key2 = f"user:channel_preferences:{other_user.id}"
        self.assertIsNotNone(cache.get(cache_key1))
        self.assertIsNotNone(cache.get(cache_key2))

        # Delete first user's preference
        pref1.delete()

        # Verify second user's cache is unaffected
        cached_data2 = cache.get(cache_key2)
        self.assertIsNotNone(cached_data2)
        self.assertEqual(len(cached_data2['preferences']), 1)
