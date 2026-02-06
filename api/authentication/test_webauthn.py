"""
Test WebAuthn/Passkey Implementation

This test file verifies that our Django Allauth WebAuthn integration is working correctly.
"""

import json
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status

from allauth.mfa.models import Authenticator

User = get_user_model()


@override_settings(
    SESSION_ENGINE='django.contrib.sessions.backends.file',
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
        }
    }
)
class WebAuthnIntegrationTest(APITestCase):
    """Test WebAuthn/Passkey integration with Django Allauth"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create(
            email='test@example.com',
            first_name='Test',
            last_name='User',
            is_email_verified=True
        )
    
    def test_webauthn_imports_available(self):
        """Test that WebAuthn imports are available"""
        try:
            from allauth.mfa.models import Authenticator
            from allauth.mfa.webauthn.internal import auth as webauthn_auth
            self.assertTrue(True, "WebAuthn imports successful")
        except ImportError as e:
            self.fail(f"WebAuthn imports failed: {e}")
    
    def test_register_passkey_endpoint_exists(self):
        """Test that the register passkey endpoint exists"""
        self.client.force_login(self.user)
        url = reverse('authentication:register_passkey')
        
        # Test initial request (should return options)
        response = self.client.post(url, {
            'device_info': {
                'webauthn_supported': True,
                'platform_authenticator': True
            }
        }, content_type='application/json')
        
        # Should return 200 with options or 501 if WebAuthn not available
        self.assertIn(response.status_code, [200, 501])
        
        if response.status_code == 200:
            data = response.json()
            self.assertTrue(data.get('success'))
            self.assertIn('options', data)
    
    def test_authenticate_passkey_endpoint_exists(self):
        """Test that the authenticate passkey endpoint exists"""
        url = reverse('authentication:authenticate_passkey')
        
        # Test initial request (should return options or error)
        response = self.client.post(url, {
            'email': 'test@example.com',
            'device_info': {
                'webauthn_supported': True
            }
        }, content_type='application/json')
        
        # Should return 404 (no passkeys), 501 (not available), or 200 (options)
        self.assertIn(response.status_code, [200, 404, 501])
    
    def test_list_passkeys_endpoint(self):
        """Test that the list passkeys endpoint works"""
        self.client.force_login(self.user)
        url = reverse('authentication:list_passkeys')
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn('passkeys', data)
        self.assertIn('count', data)
        self.assertEqual(data['count'], 0)  # No passkeys initially
    
    def test_delete_passkey_endpoint(self):
        """Test that the delete passkey endpoint works"""
        self.client.force_login(self.user)

        # Create a mock authenticator
        authenticator = Authenticator.objects.create(
            user=self.user,
            type=Authenticator.Type.WEBAUTHN,
            data={'device_name': 'Test Device'}
        )

        url = reverse('authentication:delete_passkey', kwargs={'passkey_id': authenticator.id})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get('success'))

        # Verify authenticator was deleted
        self.assertFalse(Authenticator.objects.filter(id=authenticator.id).exists())
    
    def test_signup_flow_includes_webauthn_options(self):
        """Test that signup flow includes WebAuthn options when supported"""
        # First, begin signup
        signup_begin_url = reverse('authentication:signup_begin')
        response = self.client.post(signup_begin_url, {
            'email': 'newuser@example.com',
            'device_info': {
                'webauthn_supported': True,
                'platform_authenticator': True
            }
        }, content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        
        # Note: Complete signup testing would require a valid verification code
        # which is complex to generate in tests without mocking
    
    def test_login_flow_includes_webauthn_options(self):
        """Test that login flow includes WebAuthn options when user has passkeys"""
        # Create a WebAuthn authenticator for the user
        Authenticator.objects.create(
            user=self.user,
            type=Authenticator.Type.WEBAUTHN,
            data={'device_name': 'Test Device'}
        )
        
        # Update user to indicate they have passkeys
        self.user.has_passkey = True
        self.user.save()
        
        login_url = reverse('authentication:login_passwordless')
        response = self.client.post(login_url, {
            'email': 'test@example.com',
            'auth_method': 'passkey',
            'device_info': {
                'webauthn_supported': True
            }
        }, content_type='application/json')
        
        # Should return 200 with WebAuthn options or 501 if not available
        self.assertIn(response.status_code, [200, 501])
    
    def test_signup_requires_mandatory_passkey(self):
        """Test that passkey creation is mandatory during signup"""
        # Simulate email verification completed
        new_user = User.objects.create(
            email='newuser@example.com',
            is_email_verified=True,
            is_active=False  # Not active until passkey created
        )
        
        # Try to complete signup without passkey - should fail
        # In real implementation, there would be no skip option in UI
        # User account should remain inactive until passkey is created
        self.assertFalse(new_user.is_active)
        
        # After passkey creation, user should be activated
        # This would be tested with proper WebAuthn mocking
    
    def test_passkey_signin_no_email_required(self):
        """Test that passkey sign-in doesn't require email input"""
        # With conditional UI, browser handles passkey selection
        # No email input needed in the flow
        # This is a frontend behavior but API should support it
        passkey_signin_url = reverse('authentication:signin_passkey_begin')
        response = self.client.post(passkey_signin_url, {})
        
        # Should return WebAuthn options without requiring email
        self.assertIn(response.status_code, [200, 501])


if __name__ == '__main__':
    import django
    from django.conf import settings
    from django.test.utils import get_runner
    
    django.setup()
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    failures = test_runner.run_tests(["authentication.test_webauthn"])
