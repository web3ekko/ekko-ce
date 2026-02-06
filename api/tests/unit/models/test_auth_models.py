"""
Unit tests for authentication models using Django TestCase
Tests User, UserDevice, and related Django models with proper database isolation
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from datetime import timedelta

from authentication.models import (
    UserDevice,
    AuthenticationLog,
    EmailVerificationCode,
)
from tests.factories.auth_factories import (
    UserFactory,
    AdminUserFactory,
    UserDeviceFactory,
)

User = get_user_model()


class TestUserModel(TestCase):
    """Test User model functionality with proper database isolation"""

    def setUp(self):
        """Set up test data before each test method"""
        self.test_email = "test@example.com"
        self.test_first_name = "Test"
        self.test_last_name = "User"
    
    def test_user_creation(self):
        """Test creating a User instance"""
        user = User.objects.create_user(
            email=self.test_email,
            first_name=self.test_first_name,
            last_name=self.test_last_name
        )
        
        self.assertEqual(user.email, self.test_email)
        self.assertEqual(user.first_name, self.test_first_name)
        self.assertEqual(user.last_name, self.test_last_name)
        self.assertEqual(user.full_name, f"{self.test_first_name} {self.test_last_name}")
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_email_verified)  # Default is False
        self.assertFalse(user.has_passkey)
        self.assertEqual(user.preferred_auth_method, "passkey")
    
    def test_admin_user_creation(self):
        """Test creating an admin user"""
        admin = User.objects.create_superuser(
            email="admin@example.com",
            first_name="Admin",
            last_name="User"
        )
        
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertIn("admin", admin.email)
    
    def test_user_unique_email(self):
        """Test email uniqueness constraint"""
        User.objects.create_user(
            email="unique@example.com",
            first_name="First",
            last_name="User"
        )
        
        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                email="unique@example.com",
                first_name="Second",
                last_name="User"
            )
    
    def test_user_passwordless_auth(self):
        """Test that users have unusable passwords by default"""
        user = User.objects.create_user(
            email="passwordless@example.com",
            first_name="Test",
            last_name="User"
        )
        
        self.assertFalse(user.has_usable_password())
    
    def test_user_full_name_property(self):
        """Test full_name property"""
        user = User.objects.create_user(
            email="john@example.com",
            first_name="John",
            last_name="Doe"
        )
        
        self.assertEqual(user.full_name, "John Doe")
        
        # Test with empty last name
        user.last_name = ""
        user.save()
        self.assertEqual(user.full_name, "John")
    
    def test_user_str_representation(self):
        """Test string representation of User"""
        user = User.objects.create_user(
            email="john@example.com",
            first_name="John",
            last_name="Doe"
        )
        
        self.assertEqual(str(user), "John Doe (john@example.com)")
    
    def test_user_timestamps(self):
        """Test that timestamps are properly set"""
        before = timezone.now()
        user = User.objects.create_user(
            email="timestamp@example.com",
            first_name="Time",
            last_name="Stamp"
        )
        after = timezone.now()
        
        self.assertLessEqual(before, user.created_at)
        self.assertLessEqual(user.created_at, after)
        self.assertLessEqual(before, user.updated_at)
        self.assertLessEqual(user.updated_at, after)
    
    def test_user_firebase_uid_unique(self):
        """Test Firebase UID uniqueness"""
        user1 = User.objects.create_user(
            email="user1@example.com",
            first_name="User",
            last_name="One"
        )
        user1.firebase_uid = "firebase123"
        user1.save()
        
        user2 = User.objects.create_user(
            email="user2@example.com",
            first_name="User",
            last_name="Two"
        )
        user2.firebase_uid = "firebase123"
        
        with self.assertRaises(IntegrityError):
            user2.save()
    
    def test_user_auth_preferences(self):
        """Test user authentication preferences"""
        user = User.objects.create_user(
            email="prefs@example.com",
            first_name="Pref",
            last_name="User"
        )
        
        # Default preference
        self.assertEqual(user.preferred_auth_method, "passkey")
        
        # Change preference
        user.preferred_auth_method = "email"
        user.save()
        
        user.refresh_from_db()
        self.assertEqual(user.preferred_auth_method, "email")
    
    def test_user_email_verification_status(self):
        """Test email verification status"""
        # Verified user
        verified_user = User.objects.create_user(
            email="verified@example.com",
            first_name="Verified",
            last_name="User"
        )
        verified_user.is_email_verified = True
        verified_user.save()
        self.assertTrue(verified_user.is_email_verified)
        
        # Unverified user
        unverified_user = User.objects.create_user(
            email="unverified@example.com",
            first_name="Unverified",
            last_name="User"
        )
        unverified_user.is_email_verified = False
        unverified_user.save()
        self.assertFalse(unverified_user.is_email_verified)


class TestUserDeviceModel(TestCase):
    """Test UserDevice model functionality with proper database isolation"""
    
    def setUp(self):
        """Set up test data before each test method"""
        self.user = User.objects.create_user(
            email="device@example.com",
            first_name="Device",
            last_name="User"
        )
    
    def test_device_creation(self):
        """Test creating a UserDevice instance"""
        device = UserDevice.objects.create(
            user=self.user,
            device_name="Test iPhone",
            device_type="ios",
            device_id="test_device_123",
            device_fingerprint="unique_fingerprint_123"
        )
        
        self.assertEqual(device.user, self.user)
        self.assertEqual(device.device_name, "Test iPhone")
        self.assertEqual(device.device_type, "ios")
        self.assertEqual(device.device_id, "test_device_123")
        self.assertFalse(device.supports_passkey)  # Default is False
        self.assertFalse(device.is_trusted)
    
    def test_device_trust_expiry(self):
        """Test device trust expiration"""
        device = UserDevice.objects.create(
            user=self.user,
            device_name="Trusted Device",
            device_type="web",
            device_id="trusted_device_001",
            device_fingerprint="trusted_123",
            is_trusted=True,
            trust_expires_at=timezone.now() + timedelta(days=90)
        )
        
        # Trust should expire in future
        self.assertGreater(device.trust_expires_at, timezone.now())
        
        # Test expired trust
        device.trust_expires_at = timezone.now() - timedelta(days=1)
        device.save()
        
        # Should implement is_trust_valid property
        self.assertLess(device.trust_expires_at, timezone.now())
    
    def test_device_id_uniqueness(self):
        """Test device ID uniqueness"""
        UserDevice.objects.create(
            user=self.user,
            device_name="Device 1",
            device_type="web",
            device_id="unique_device_456",
            device_fingerprint="unique_fp_456"
        )
        
        with self.assertRaises(IntegrityError):
            UserDevice.objects.create(
                user=self.user,
                device_name="Device 2",
                device_type="web",
                device_id="unique_device_456",  # Same device_id should fail
                device_fingerprint="different_fp_789"
            )
    
    def test_device_types(self):
        """Test valid device types"""
        valid_types = ["web", "ios", "android", "desktop"]
        
        for i, device_type in enumerate(valid_types):
            device = UserDevice.objects.create(
                user=self.user,
                device_name=f"Device {i}",
                device_type=device_type,
                device_id=f"device_{device_type}_{i}",
                device_fingerprint=f"fp_{device_type}_{i}"
            )
            self.assertEqual(device.device_type, device_type)
    
    def test_device_user_relationship(self):
        """Test device belongs to user"""
        device1 = UserDevice.objects.create(
            user=self.user,
            device_name="iPhone",
            device_type="ios",
            device_id="iphone_device_001",
            device_fingerprint="iphone_fp"
        )
        device2 = UserDevice.objects.create(
            user=self.user,
            device_name="iPad",
            device_type="ios",
            device_id="ipad_device_002",
            device_fingerprint="ipad_fp"
        )
        
        self.assertEqual(self.user.devices.count(), 2)
        self.assertIn(device1, self.user.devices.all())
        self.assertIn(device2, self.user.devices.all())


class TestAuthenticationLogModel(TestCase):
    """Test AuthenticationLog model functionality with proper database isolation"""
    
    def setUp(self):
        """Set up test data before each test method"""
        self.user = User.objects.create_user(
            email="log@example.com",
            first_name="Log",
            last_name="User"
        )
    
    def test_auth_log_creation(self):
        """Test creating authentication log entries"""
        log = AuthenticationLog.objects.create(
            user=self.user,
            method="passkey",
            success=True,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0"
        )
        
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.method, "passkey")
        self.assertTrue(log.success)
    
    def test_auth_log_failure(self):
        """Test logging failed authentication attempts"""
        log = AuthenticationLog.objects.create(
            user=self.user,
            method="passkey",
            success=False,
            failure_reason="Invalid credential",
            ip_address="192.168.1.1"
        )
        
        self.assertFalse(log.success)
        self.assertEqual(log.failure_reason, "Invalid credential")
    
    def test_auth_log_metadata(self):
        """Test storing metadata in auth logs"""
        device_info = {
            "device_id": "abc123",
            "location": "San Francisco",
            "risk_score": 0.2
        }
        
        log = AuthenticationLog.objects.create(
            user=self.user,
            method="email_code",
            success=True,
            ip_address="192.168.1.1",
            device_info=device_info
        )
        
        self.assertEqual(log.device_info, device_info)
    
    def test_auth_log_methods(self):
        """Test different authentication methods"""
        methods = ["passkey", "email_code", "totp", "recovery_code"]
        
        for method in methods:
            log = AuthenticationLog.objects.create(
                user=self.user,
                method=method,
                success=True,
                ip_address="192.168.1.1"
            )
            self.assertEqual(log.method, method)
    


class TestEmailVerificationCodeModel(TestCase):
    """Test EmailVerificationCode model functionality with proper database isolation"""
    
    def setUp(self):
        """Set up test data before each test method"""
        self.user = User.objects.create_user(
            email="verify@example.com",
            first_name="Verify",
            last_name="User"
        )
    
    def test_verification_code_creation(self):
        """Test creating email verification codes"""
        code = EmailVerificationCode.objects.create(
            user=self.user,
            email=self.user.email,
            code="123456",
            purpose="signin",
            ip_address="192.168.1.1",
            expires_at=timezone.now() + timedelta(minutes=10)
        )
        
        self.assertEqual(code.user, self.user)
        self.assertEqual(code.email, self.user.email)
        self.assertEqual(code.code, "123456")
        self.assertEqual(code.purpose, "signin")
        # Check if code is used based on used_at field
        self.assertIsNone(code.used_at)
    
    def test_verification_code_expiry(self):
        """Test verification code expiration"""
        code = EmailVerificationCode.objects.create(
            user=self.user,
            email=self.user.email,
            code="123456",
            purpose="signin",
            ip_address="192.168.1.1",
            expires_at=timezone.now() + timedelta(minutes=15)
        )
        
        # Should expire in future (default 15 minutes)
        self.assertGreater(code.expires_at, timezone.now())
        
        # Test expired code
        code.expires_at = timezone.now() - timedelta(minutes=1)
        code.save()
        
        self.assertLess(code.expires_at, timezone.now())
    
    def test_verification_code_usage(self):
        """Test marking verification code as used"""
        code = EmailVerificationCode.objects.create(
            user=self.user,
            email=self.user.email,
            code="123456",
            purpose="signup",
            ip_address="192.168.1.1",
            expires_at=timezone.now() + timedelta(minutes=10)
        )
        
        # Check if code is used based on used_at field
        self.assertIsNone(code.used_at)
        
        # Mark code as used
        code.used_at = timezone.now()
        code.save()
        
        code.refresh_from_db()
        self.assertIsNotNone(code.used_at)
    
    def test_verification_code_purposes(self):
        """Test different verification code purposes"""
        # Only test valid purposes from the model's choices
        purposes = ["signin", "signup", "recovery"]
        
        for i, purpose in enumerate(purposes):
            code = EmailVerificationCode.objects.create(
                user=self.user,
                email=self.user.email,
                code=f"10000{i}",  # 6-digit code
                purpose=purpose,
                ip_address="192.168.1.1",
                expires_at=timezone.now() + timedelta(minutes=10)
            )
            self.assertEqual(code.purpose, purpose)
    
    def test_multiple_verification_codes(self):
        """Test user can have multiple verification codes"""
        codes = []
        for i in range(3):
            code = EmailVerificationCode.objects.create(
                user=self.user,
                email=self.user.email,
                code=f"12345{i}",  # 6-digit code
                purpose="signin",
                ip_address="192.168.1.1",
                expires_at=timezone.now() + timedelta(minutes=10)
            )
            codes.append(code)
        
        self.assertEqual(self.user.verification_codes.count(), 3)
        for code in codes:
            self.assertIn(code, self.user.verification_codes.all())


class TestAuthModelRelationships(TestCase):
    """Test relationships between auth models with proper database isolation"""
    
    def setUp(self):
        """Set up test data before each test method"""
        self.user = User.objects.create_user(
            email="relation@example.com",
            first_name="Relation",
            last_name="User"
        )
    
    def test_user_devices_relationship(self):
        """Test user can have multiple devices"""
        device1 = UserDevice.objects.create(
            user=self.user,
            device_name="iPhone",
            device_type="ios",
            device_id="iphone_device_123",
            device_fingerprint="iphone_123"
        )
        device2 = UserDevice.objects.create(
            user=self.user,
            device_name="iPad",
            device_type="ios",
            device_id="ipad_device_456",
            device_fingerprint="ipad_456"
        )
        device3 = UserDevice.objects.create(
            user=self.user,
            device_name="MacBook",
            device_type="desktop",
            device_id="mac_device_789",
            device_fingerprint="mac_789"
        )
        
        self.assertEqual(self.user.devices.count(), 3)
        device_names = set(self.user.devices.values_list('device_name', flat=True))
        self.assertEqual(device_names, {"iPhone", "iPad", "MacBook"})
    
    def test_user_authentication_logs(self):
        """Test user authentication log history"""
        # Create various auth logs
        AuthenticationLog.objects.create(
            user=self.user,
            method="passkey",
            success=True,
            ip_address="192.168.1.1"
        )
        
        AuthenticationLog.objects.create(
            user=self.user,
            method="email_code",
            success=False,
            ip_address="192.168.1.1",
            failure_reason="Invalid code"
        )
        
        AuthenticationLog.objects.create(
            user=self.user,
            method="passkey",
            success=True,
            ip_address="192.168.1.1"
        )
        
        self.assertEqual(self.user.auth_logs.count(), 3)
        
        # Check successful auth attempts
        successful_auths = self.user.auth_logs.filter(
            success=True
        )
        self.assertEqual(successful_auths.count(), 2)
    
    def test_cascade_deletion(self):
        """Test cascade deletion of related objects"""
        # Create related objects
        device = UserDevice.objects.create(
            user=self.user,
            device_name="Test Device",
            device_type="web",
            device_id="test_device_deletion",
            device_fingerprint="test_fp"
        )
        log = AuthenticationLog.objects.create(
            user=self.user,
            method="email_code",
            success=True,
            ip_address="192.168.1.1"
        )
        code = EmailVerificationCode.objects.create(
            user=self.user,
            email=self.user.email,
            code="123456",
            purpose="signin",
            ip_address="192.168.1.1",
            expires_at=timezone.now() + timedelta(minutes=10)
        )
        
        # Delete user
        user_id = self.user.id
        self.user.delete()
        
        # Verify related objects are deleted
        self.assertFalse(UserDevice.objects.filter(user_id=user_id).exists())
        self.assertFalse(AuthenticationLog.objects.filter(user_id=user_id).exists())
        self.assertFalse(EmailVerificationCode.objects.filter(user_id=user_id).exists())


class TestUserDevicePushTokenModel(TestCase):
    """Test UserDevice push notification token functionality"""

    def setUp(self):
        """Set up test data before each test method"""
        self.user = User.objects.create_user(
            email="pushtoken@example.com",
            first_name="Push",
            last_name="User"
        )
        self.device = UserDevice.objects.create(
            user=self.user,
            device_name="Test iPhone",
            device_type="ios",
            device_id="push_device_001",
            device_fingerprint="push_fp_001"
        )

    def test_device_push_token_fields_exist(self):
        """Test that push token fields exist with default values"""
        self.assertIsNone(self.device.device_token)
        self.assertIsNone(self.device.token_type)
        self.assertIsNone(self.device.token_hash)
        self.assertIsNone(self.device.token_updated_at)
        self.assertTrue(self.device.push_enabled)

    def test_register_push_token_fcm(self):
        """Test registering an FCM push token"""
        token = "test_fcm_token_123456789"

        self.device.register_push_token(token, token_type='fcm')
        self.device.refresh_from_db()

        self.assertEqual(self.device.device_token, token)
        self.assertEqual(self.device.token_type, 'fcm')
        self.assertTrue(self.device.push_enabled)
        self.assertIsNotNone(self.device.token_hash)
        self.assertIsNotNone(self.device.token_updated_at)
        # Token hash should be SHA256 (64 hex characters)
        self.assertEqual(len(self.device.token_hash), 64)

    def test_register_push_token_apns(self):
        """Test registering an APNs push token"""
        token = "test_apns_token_abcdef"

        self.device.register_push_token(token, token_type='apns')
        self.device.refresh_from_db()

        self.assertEqual(self.device.device_token, token)
        self.assertEqual(self.device.token_type, 'apns')
        self.assertTrue(self.device.push_enabled)

    def test_revoke_push_token(self):
        """Test revoking a push token"""
        # First register a token
        self.device.register_push_token("test_token_to_revoke", token_type='fcm')
        self.device.refresh_from_db()
        self.assertIsNotNone(self.device.device_token)

        # Now revoke it
        self.device.revoke_push_token()
        self.device.refresh_from_db()

        self.assertIsNone(self.device.device_token)
        self.assertIsNone(self.device.token_type)
        self.assertIsNone(self.device.token_hash)
        self.assertFalse(self.device.push_enabled)

    def test_set_push_enabled(self):
        """Test enabling/disabling push for a device"""
        self.device.register_push_token("test_token", token_type='fcm')
        self.device.refresh_from_db()
        self.assertTrue(self.device.push_enabled)

        # Disable push
        self.device.set_push_enabled(False)
        self.device.refresh_from_db()
        self.assertFalse(self.device.push_enabled)

        # Re-enable push
        self.device.set_push_enabled(True)
        self.device.refresh_from_db()
        self.assertTrue(self.device.push_enabled)

    def test_get_push_devices_cached(self):
        """Test getting cached push-enabled devices for a user"""
        # Register push tokens on two devices
        self.device.register_push_token("token1", token_type='fcm')

        device2 = UserDevice.objects.create(
            user=self.user,
            device_name="Test Android",
            device_type="android",
            device_id="push_device_002",
            device_fingerprint="push_fp_002"
        )
        device2.register_push_token("token2", token_type='fcm')

        # Get cached devices
        cached = UserDevice.get_push_devices_cached(self.user.id)

        self.assertEqual(cached['user_id'], str(self.user.id))
        self.assertEqual(len(cached['devices']), 2)
        self.assertIn('cached_at', cached)

        # Check device data structure
        device_tokens = [d['device_token'] for d in cached['devices']]
        self.assertIn("token1", device_tokens)
        self.assertIn("token2", device_tokens)

    def test_get_push_devices_excludes_disabled(self):
        """Test that disabled devices are excluded from cache"""
        # Register token but disable push
        self.device.register_push_token("token1", token_type='fcm')
        self.device.set_push_enabled(False)

        cached = UserDevice.get_push_devices_cached(self.user.id)

        self.assertEqual(len(cached['devices']), 0)

    def test_token_hash_is_sha256(self):
        """Test that token hash is correct SHA256"""
        import hashlib

        token = "my_unique_push_token"
        expected_hash = hashlib.sha256(token.encode()).hexdigest()

        self.device.register_push_token(token, token_type='fcm')
        self.device.refresh_from_db()

        self.assertEqual(self.device.token_hash, expected_hash)

    def test_multiple_devices_different_users(self):
        """Test that push cache is user-specific"""
        # Register token for first user
        self.device.register_push_token("user1_token", token_type='fcm')

        # Create second user with device
        user2 = User.objects.create_user(
            email="pushtoken2@example.com",
            first_name="Push2",
            last_name="User2"
        )
        device2 = UserDevice.objects.create(
            user=user2,
            device_name="User2 Phone",
            device_type="android",
            device_id="push_device_003",
            device_fingerprint="push_fp_003"
        )
        device2.register_push_token("user2_token", token_type='fcm')

        # Get cached devices for each user
        user1_cached = UserDevice.get_push_devices_cached(self.user.id)
        user2_cached = UserDevice.get_push_devices_cached(user2.id)

        # Each user should only see their own devices
        self.assertEqual(len(user1_cached['devices']), 1)
        self.assertEqual(user1_cached['devices'][0]['device_token'], "user1_token")

        self.assertEqual(len(user2_cached['devices']), 1)
        self.assertEqual(user2_cached['devices'][0]['device_token'], "user2_token")


class TestUserDeviceDeleteSignal(TestCase):
    """Test post_delete signal handler for UserDevice push cache"""

    def setUp(self):
        """Set up test data before each test method"""
        self.user = User.objects.create_user(
            email="delete_signal@example.com",
            first_name="Delete",
            last_name="Signal"
        )

    def test_delete_device_updates_push_cache(self):
        """Test that deleting a device updates the push cache correctly"""
        from django.core.cache import cache

        # Create two devices with push tokens
        device1 = UserDevice.objects.create(
            user=self.user,
            device_name="iPhone",
            device_type="ios",
            device_id="delete_device_001",
            device_fingerprint="delete_fp_001"
        )
        device1.register_push_token("token1", token_type='apns')

        device2 = UserDevice.objects.create(
            user=self.user,
            device_name="Android",
            device_type="android",
            device_id="delete_device_002",
            device_fingerprint="delete_fp_002"
        )
        device2.register_push_token("token2", token_type='fcm')

        # Verify cache has both devices
        cache_key = f"user:push_devices:{self.user.id}"
        cached_data = cache.get(cache_key)
        self.assertIsNotNone(cached_data)
        self.assertEqual(len(cached_data['devices']), 2)

        # Delete one device
        device1.delete()

        # Verify cache is updated - should only have device2 now
        cached_data = cache.get(cache_key)
        self.assertIsNotNone(cached_data)
        self.assertEqual(len(cached_data['devices']), 1)
        self.assertEqual(cached_data['devices'][0]['device_token'], 'token2')

    def test_delete_last_push_device_keeps_empty_cache(self):
        """Test that deleting the last push device results in empty cache"""
        from django.core.cache import cache

        # Create single device with push token
        device = UserDevice.objects.create(
            user=self.user,
            device_name="Only Phone",
            device_type="ios",
            device_id="delete_device_003",
            device_fingerprint="delete_fp_003"
        )
        device.register_push_token("only_token", token_type='fcm')

        # Verify cache exists with device
        cache_key = f"user:push_devices:{self.user.id}"
        cached_data = cache.get(cache_key)
        self.assertIsNotNone(cached_data)
        self.assertEqual(len(cached_data['devices']), 1)

        # Delete the device
        device.delete()

        # Cache should still exist but with empty devices list
        cached_data = cache.get(cache_key)
        self.assertIsNotNone(cached_data)
        self.assertEqual(len(cached_data['devices']), 0)

    def test_delete_device_without_push_token_updates_cache(self):
        """Test that deleting a device without push token still updates cache"""
        from django.core.cache import cache

        # Create device with push token
        device_with_token = UserDevice.objects.create(
            user=self.user,
            device_name="Phone with token",
            device_type="ios",
            device_id="delete_device_004",
            device_fingerprint="delete_fp_004"
        )
        device_with_token.register_push_token("active_token", token_type='fcm')

        # Create device without push token
        device_without_token = UserDevice.objects.create(
            user=self.user,
            device_name="Phone without token",
            device_type="android",
            device_id="delete_device_005",
            device_fingerprint="delete_fp_005"
        )

        # Verify cache shows only the device with token
        cache_key = f"user:push_devices:{self.user.id}"
        cached_data = cache.get(cache_key)
        self.assertEqual(len(cached_data['devices']), 1)

        # Delete device without token
        device_without_token.delete()

        # Cache should still have the device with token
        cached_data = cache.get(cache_key)
        self.assertIsNotNone(cached_data)
        self.assertEqual(len(cached_data['devices']), 1)
        self.assertEqual(cached_data['devices'][0]['device_token'], 'active_token')

    def test_delete_preserves_other_users_push_cache(self):
        """Test that deleting one user's device doesn't affect others"""
        from django.core.cache import cache

        # Create another user
        other_user = User.objects.create_user(
            email="other_push@example.com",
            first_name="Other",
            last_name="User"
        )

        # Create devices for both users
        device1 = UserDevice.objects.create(
            user=self.user,
            device_name="User1 Phone",
            device_type="ios",
            device_id="delete_device_006",
            device_fingerprint="delete_fp_006"
        )
        device1.register_push_token("user1_token", token_type='fcm')

        device2 = UserDevice.objects.create(
            user=other_user,
            device_name="User2 Phone",
            device_type="android",
            device_id="delete_device_007",
            device_fingerprint="delete_fp_007"
        )
        device2.register_push_token("user2_token", token_type='fcm')

        # Verify both caches exist
        cache_key1 = f"user:push_devices:{self.user.id}"
        cache_key2 = f"user:push_devices:{other_user.id}"
        self.assertIsNotNone(cache.get(cache_key1))
        self.assertIsNotNone(cache.get(cache_key2))

        # Delete first user's device
        device1.delete()

        # Verify second user's cache is unaffected
        cached_data2 = cache.get(cache_key2)
        self.assertIsNotNone(cached_data2)
        self.assertEqual(len(cached_data2['devices']), 1)
        self.assertEqual(cached_data2['devices'][0]['device_token'], 'user2_token')

        # First user's cache should show empty
        cached_data1 = cache.get(cache_key1)
        self.assertIsNotNone(cached_data1)
        self.assertEqual(len(cached_data1['devices']), 0)