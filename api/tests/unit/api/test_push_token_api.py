"""
Unit tests for Push Token API endpoints

Tests the device push token registration, update, revoke, and listing endpoints.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from unittest.mock import patch
from authentication.models import UserDevice
from knox.models import AuthToken

User = get_user_model()


class TestPushTokenAPIBase(APITestCase):
    """Base class for push token API tests with common setup"""

    def setUp(self):
        """Set up test data before each test method"""
        self.user = User.objects.create_user(
            email="pushtest@example.com",
            first_name="Push",
            last_name="Tester"
        )
        # Create Knox token for authentication
        _, self.token = AuthToken.objects.create(self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token}')

        # Valid FCM token (typical format)
        self.valid_fcm_token = "d" * 152  # FCM tokens are typically 152 chars

        # Create a test device
        self.device = UserDevice.objects.create(
            user=self.user,
            device_name="Test iPhone",
            device_type="ios",
            device_id="test_device_001",
            device_fingerprint="test_fp_001",
            is_active=True,
        )


class TestRegisterPushToken(TestPushTokenAPIBase):
    """Test POST /api/auth/devices/register-push/"""

    def test_register_push_token_new_device(self):
        """Test registering a push token creates a new device"""
        url = reverse('authentication:register_push_token')
        data = {
            'device_token': self.valid_fcm_token,
            'token_type': 'fcm',
            'device_name': 'New Android Phone',
            'device_type': 'android',
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['device']['token_type'], 'fcm')
        self.assertEqual(response.data['device']['device_name'], 'New Android Phone')
        self.assertTrue(response.data['device']['push_enabled'])

    def test_register_push_token_existing_device(self):
        """Test registering a push token for an existing device"""
        url = reverse('authentication:register_push_token')
        data = {
            'device_token': self.valid_fcm_token,
            'token_type': 'apns',
            'device_id': self.device.device_id,
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['device']['token_type'], 'apns')

        # Verify token was saved
        self.device.refresh_from_db()
        self.assertEqual(self.device.device_token, self.valid_fcm_token)
        self.assertEqual(self.device.token_type, 'apns')

    def test_register_push_token_invalid_token_too_short(self):
        """Test that short tokens are rejected"""
        url = reverse('authentication:register_push_token')
        data = {
            'device_token': 'too_short',
            'token_type': 'fcm',
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('device_token', response.data)

    def test_register_push_token_missing_token(self):
        """Test that missing token returns error"""
        url = reverse('authentication:register_push_token')
        data = {
            'token_type': 'fcm',
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_push_token_unauthenticated(self):
        """Test that unauthenticated requests are rejected"""
        self.client.credentials()  # Remove auth
        url = reverse('authentication:register_push_token')
        data = {
            'device_token': self.valid_fcm_token,
            'token_type': 'fcm',
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TestUpdateDevicePushToken(TestPushTokenAPIBase):
    """Test PATCH /api/auth/devices/{device_id}/push-token/"""

    def test_update_push_token_success(self):
        """Test updating a push token"""
        # First register a token
        self.device.register_push_token(self.valid_fcm_token, 'fcm')

        url = reverse('authentication:update_device_push_token', args=[self.device.id])
        new_token = "e" * 152
        data = {
            'device_token': new_token,
        }

        response = self.client.patch(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])

        # Verify token was updated
        self.device.refresh_from_db()
        self.assertEqual(self.device.device_token, new_token)

    def test_update_push_token_with_new_type(self):
        """Test updating a push token with a new token type"""
        self.device.register_push_token(self.valid_fcm_token, 'fcm')

        url = reverse('authentication:update_device_push_token', args=[self.device.id])
        new_token = "f" * 152
        data = {
            'device_token': new_token,
            'token_type': 'apns',
        }

        response = self.client.patch(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.device.refresh_from_db()
        self.assertEqual(self.device.token_type, 'apns')

    def test_update_push_token_device_not_found(self):
        """Test updating a push token for non-existent device"""
        import uuid
        fake_id = uuid.uuid4()
        url = reverse('authentication:update_device_push_token', args=[fake_id])
        data = {
            'device_token': self.valid_fcm_token,
        }

        response = self.client.patch(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_push_token_other_users_device(self):
        """Test that users cannot update other users' device tokens"""
        # Create another user and their device
        other_user = User.objects.create_user(
            email="other@example.com",
            first_name="Other",
            last_name="User"
        )
        other_device = UserDevice.objects.create(
            user=other_user,
            device_name="Other's Phone",
            device_type="android",
            device_id="other_device_001",
            device_fingerprint="other_fp_001",
        )

        url = reverse('authentication:update_device_push_token', args=[other_device.id])
        data = {
            'device_token': self.valid_fcm_token,
        }

        response = self.client.patch(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TestRevokeDevicePushToken(TestPushTokenAPIBase):
    """Test DELETE /api/auth/devices/{device_id}/push-token/revoke/"""

    def test_revoke_push_token_success(self):
        """Test revoking a push token"""
        # First register a token
        self.device.register_push_token(self.valid_fcm_token, 'fcm')
        self.assertTrue(self.device.push_enabled)

        url = reverse('authentication:revoke_device_push_token', args=[self.device.id])

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])

        # Verify token was revoked
        self.device.refresh_from_db()
        self.assertIsNone(self.device.device_token)
        self.assertIsNone(self.device.token_type)
        self.assertFalse(self.device.push_enabled)

    def test_revoke_push_token_device_not_found(self):
        """Test revoking a push token for non-existent device"""
        import uuid
        fake_id = uuid.uuid4()
        url = reverse('authentication:revoke_device_push_token', args=[fake_id])

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TestToggleDevicePush(TestPushTokenAPIBase):
    """Test PATCH /api/auth/devices/{device_id}/push-enabled/"""

    def test_disable_push_notifications(self):
        """Test disabling push notifications"""
        self.device.register_push_token(self.valid_fcm_token, 'fcm')
        self.assertTrue(self.device.push_enabled)

        url = reverse('authentication:toggle_device_push', args=[self.device.id])
        data = {'enabled': False}

        response = self.client.patch(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['device']['push_enabled'])

        self.device.refresh_from_db()
        self.assertFalse(self.device.push_enabled)

    def test_enable_push_notifications(self):
        """Test enabling push notifications"""
        self.device.register_push_token(self.valid_fcm_token, 'fcm')
        self.device.set_push_enabled(False)

        url = reverse('authentication:toggle_device_push', args=[self.device.id])
        data = {'enabled': True}

        response = self.client.patch(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['device']['push_enabled'])

    def test_toggle_push_missing_enabled_field(self):
        """Test toggle with missing enabled field"""
        url = reverse('authentication:toggle_device_push', args=[self.device.id])
        data = {}

        response = self.client.patch(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TestListPushEnabledDevices(TestPushTokenAPIBase):
    """Test GET /api/auth/devices/push-enabled/"""

    def test_list_push_enabled_devices_empty(self):
        """Test listing when no devices have push enabled"""
        url = reverse('authentication:list_push_enabled_devices')

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['count'], 0)
        self.assertEqual(response.data['devices'], [])

    def test_list_push_enabled_devices_with_devices(self):
        """Test listing devices with push tokens"""
        # Register push token for existing device
        self.device.register_push_token(self.valid_fcm_token, 'fcm')

        # Create another device with push token
        device2 = UserDevice.objects.create(
            user=self.user,
            device_name="Android Tablet",
            device_type="android",
            device_id="test_device_002",
            device_fingerprint="test_fp_002",
            is_active=True,
        )
        device2.register_push_token("g" * 152, 'fcm')

        url = reverse('authentication:list_push_enabled_devices')

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(len(response.data['devices']), 2)

    def test_list_excludes_disabled_devices(self):
        """Test that disabled devices are excluded from the list"""
        self.device.register_push_token(self.valid_fcm_token, 'fcm')
        self.device.set_push_enabled(False)

        url = reverse('authentication:list_push_enabled_devices')

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)

    def test_list_excludes_inactive_devices(self):
        """Test that inactive devices are excluded"""
        self.device.register_push_token(self.valid_fcm_token, 'fcm')
        self.device.is_active = False
        self.device.save()
        # Need to refresh the cache after changing is_active directly
        self.device._warm_push_cache()

        url = reverse('authentication:list_push_enabled_devices')

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)

    def test_list_unauthenticated(self):
        """Test that unauthenticated requests are rejected"""
        self.client.credentials()  # Remove auth
        url = reverse('authentication:list_push_enabled_devices')

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
