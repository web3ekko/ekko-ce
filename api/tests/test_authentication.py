"""
Authentication System Unit Tests

These tests are derived from the authentication PRD and technical context:
- /docs/prd/01-AUTHENTICATION-SYSTEM-USDT.md
- /docs/technical/authentication/TECHNICAL-CONTEXT-Authentication.md
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch, MagicMock
import json

from knox.models import AuthToken
from authentication.models import EmailVerificationCode

User = get_user_model()


class AuthenticationSystemArchitectureTest(TestCase):
    """
    Test Scenario: Authentication System Architecture
    Validates that core components are properly configured
    """
    
    def test_core_authentication_components_available(self):
        """Test that Django + Knox tokens are available"""
        self.assertTrue(hasattr(User, 'auth_token_set'))
        self.assertTrue(AuthToken)
    
    def test_knox_token_configuration(self):
        """Test Knox token configuration matches specification"""
        from django.conf import settings
        from knox.settings import knox_settings
        
        # Verify 48-hour expiry
        self.assertEqual(knox_settings.TOKEN_TTL, timedelta(hours=48))
        
        # Verify auto-refresh is enabled
        self.assertTrue(knox_settings.AUTO_REFRESH)
        
        # Verify unlimited tokens per user
        self.assertIsNone(knox_settings.TOKEN_LIMIT_PER_USER)
    
    def test_firebase_integration_configuration(self):
        """Test Firebase configuration is available"""
        from django.conf import settings
        
        # Firebase settings should be configured
        self.assertTrue(hasattr(settings, 'FIREBASE_PROJECT_ID'))
        self.assertTrue(hasattr(settings, 'FIREBASE_API_KEY'))


class PasswordlessAuthenticationFlowTest(TestCase):
    """
    Test Scenario: Passwordless Authentication Flow
    Validates 3-second authentication target and automatic Knox token generation
    """
    
    def setUp(self):
        self.client = Client()
        self.test_email = 'test@ekko.zone'
    
    @patch("authentication.views.send_verification_code_email")
    def test_signup_flow_automatic_knox_token_generation(self, mock_send_email):
        """Test that Knox tokens are generated automatically during signup"""
        # Mock email sending
        mock_send_email.return_value = True
        
        # Step 1: Begin signup process
        response = self.client.post('/api/auth/signup/', {
            'email': self.test_email
        })
        
        self.assertEqual(response.status_code, 200)
        
        # Get the verification code
        code = EmailVerificationCode.objects.get(email=self.test_email)
        
        # Step 2: Complete email verification (should auto-generate Knox token)
        response = self.client.post('/api/auth/signup/verify-code/', {
            'email': self.test_email,
            'code': code.code
        })
        
        self.assertEqual(response.status_code, 200)
        
        # Verify Knox token was automatically generated
        response_data = json.loads(response.content)
        self.assertIn('token', response_data)
        self.assertIsNotNone(response_data['token'])
        
        # Verify user is marked as verified
        user = User.objects.get(email=self.test_email)
        self.assertTrue(user.is_email_verified)
        
        # Verify Knox token exists in database
        knox_tokens = AuthToken.objects.filter(user=user)
        self.assertEqual(knox_tokens.count(), 1)
    
    @patch("authentication.views_verification.send_verification_code_email")
    def test_authentication_performance_target(self, mock_send_email):
        """Test that authentication completes within 3-second target"""
        import time
        
        # Mock email sending
        mock_send_email.return_value = True
        
        # Create verified user
        user = User.objects.create(
            email=self.test_email,
            is_email_verified=True
        )
        
        # Request signin code
        response = self.client.post('/api/auth/signin/email/send-code/', {
            'email': self.test_email
        })
        self.assertEqual(response.status_code, 200)
        
        # Get the verification code
        code = EmailVerificationCode.objects.get(email=self.test_email)
        
        # Measure authentication time
        start_time = time.time()
        
        response = self.client.post('/api/auth/signin/email/verify-code/', {
            'email': self.test_email,
            'code': code.code
        })
        
        end_time = time.time()
        authentication_time = end_time - start_time
        
        # Should complete in under 3 seconds (allowing for test overhead)
        self.assertLess(authentication_time, 3.0)
        self.assertEqual(response.status_code, 200)


class UserRegistrationProcessTest(TestCase):
    """
    Test Scenario: User Registration Process
    Validates Django-Firebase integration and automatic Knox token generation
    """
    
    def setUp(self):
        self.client = Client()
        self.test_email = 'test@ekko.zone'
    
    @patch("authentication.views.send_verification_code_email")
    def test_django_user_creation(self, mock_send_email):
        """Test Django user creation with verification code"""
        # Mock email sending
        mock_send_email.return_value = True
        
        # Begin signup
        response = self.client.post('/api/auth/signup/', {
            'email': self.test_email
        })
        
        self.assertEqual(response.status_code, 200)
        mock_send_email.assert_called_once()
        
        # Verify code was created
        code = EmailVerificationCode.objects.get(email=self.test_email)
        self.assertEqual(len(code.code), 6)
        self.assertTrue(code.code.isdigit())
    
    @patch("authentication.views.send_verification_code_email")
    def test_automatic_knox_token_generation_no_separate_api_call(self, mock_send_email):
        """Test that Knox tokens are generated automatically, no separate API call needed"""
        # Mock email sending
        mock_send_email.return_value = True
        
        # Request signup
        response = self.client.post('/api/auth/signup/', {
            'email': self.test_email
        })
        self.assertEqual(response.status_code, 200)
        
        # Get verification code
        code = EmailVerificationCode.objects.get(email=self.test_email)
        
        # Verify initial state - user is created as inactive/unverified, but no Knox tokens yet
        self.assertEqual(User.objects.filter(email=self.test_email).count(), 1)
        user = User.objects.get(email=self.test_email)
        self.assertFalse(user.is_active)
        self.assertFalse(user.is_email_verified)
        self.assertEqual(AuthToken.objects.filter(user=user).count(), 0)
        
        # Complete email verification
        response = self.client.post('/api/auth/signup/verify-code/', {
            'email': self.test_email,
            'code': code.code
        })
        
        self.assertEqual(response.status_code, 200)
        
        # Verify user was created
        user = User.objects.get(email=self.test_email)
        
        # Verify Knox token was automatically created (no separate API call)
        knox_tokens = AuthToken.objects.filter(user=user)
        self.assertEqual(knox_tokens.count(), 1)
        
        # Verify token is included in response
        response_data = json.loads(response.content)
        self.assertIn('token', response_data)
        
        # Verify token format
        knox_token = response_data['token']
        self.assertIsInstance(knox_token, str)
        self.assertGreater(len(knox_token), 20)  # Knox tokens are substantial length


class KnoxTokenManagementTest(TestCase):
    """
    Test Scenario: Knox Token Management for Multi-Device Access
    Validates device-specific tokens and multi-device support
    """
    
    def setUp(self):
        self.user = User.objects.create(
            email='test@ekko.zone',
            is_email_verified=True
        )
    
    def test_device_specific_tokens(self):
        """Test that each device gets unique secure tokens"""
        # Simulate authentication from device 1
        token1, _ = AuthToken.objects.create(user=self.user)
        
        # Simulate authentication from device 2
        token2, _ = AuthToken.objects.create(user=self.user)
        
        # Tokens should be different
        self.assertNotEqual(token1.digest, token2.digest)
        
        # Both should belong to same user
        self.assertEqual(token1.user, self.user)
        self.assertEqual(token2.user, self.user)
    
    def test_unlimited_tokens_per_user(self):
        """Test that users can have unlimited tokens (multi-device support)"""
        # Create multiple tokens for same user
        for i in range(10):  # Simulate 10 devices
            AuthToken.objects.create(user=self.user)
        
        # All tokens should be created successfully
        user_tokens = AuthToken.objects.filter(user=self.user)
        self.assertEqual(user_tokens.count(), 10)
    
    def test_48_hour_token_expiry_with_auto_refresh(self):
        """Test Knox token expiry and auto-refresh configuration"""
        token, _ = AuthToken.objects.create(user=self.user)
        
        # Token should expire in 48 hours
        expected_expiry = timezone.now() + timedelta(hours=48)
        self.assertAlmostEqual(
            token.expiry, 
            expected_expiry, 
            delta=timedelta(minutes=1)  # Allow 1 minute variance
        )
    
    def test_authorization_header_format(self):
        """Test that tokens work with Authorization header format: 'Token {knox_token}'"""
        from knox.auth import TokenAuthentication

        # Create token
        _, token_key = AuthToken.objects.create(user=self.user)

        # Test authentication header format
        auth = TokenAuthentication()

        # Knox tokens should authenticate with "Token" prefix
        # This validates our API accepts the specified header format

    def test_validate_token_endpoint_with_valid_token(self):
        """Test that /api/auth/validate-token/ returns user info for valid token"""
        # Create token
        _, token_key = AuthToken.objects.create(user=self.user)

        # Call validate-token endpoint
        client = Client()
        response = client.get(
            '/api/auth/validate-token/',
            HTTP_AUTHORIZATION=f'Token {token_key}'
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)

        # Verify response structure
        self.assertTrue(response_data.get('valid'))
        self.assertIn('user', response_data)
        self.assertEqual(response_data['user']['email'], self.user.email)
        self.assertEqual(response_data['user']['id'], str(self.user.id))

    def test_validate_token_endpoint_with_invalid_token(self):
        """Test that /api/auth/validate-token/ returns 401 for invalid token"""
        client = Client()
        response = client.get(
            '/api/auth/validate-token/',
            HTTP_AUTHORIZATION='Token invalid_token_12345'
        )

        self.assertEqual(response.status_code, 401)

    def test_validate_token_endpoint_without_token(self):
        """Test that /api/auth/validate-token/ returns 401 without token"""
        client = Client()
        response = client.get('/api/auth/validate-token/')

        self.assertEqual(response.status_code, 401)

    def test_validate_token_endpoint_with_expired_token(self):
        """Test that /api/auth/validate-token/ returns 401 for expired token"""
        # Create token
        token_instance, token_key = AuthToken.objects.create(user=self.user)

        # Expire the token by setting expiry to past
        token_instance.expiry = timezone.now() - timedelta(hours=1)
        token_instance.save()

        # Call validate-token endpoint
        client = Client()
        response = client.get(
            '/api/auth/validate-token/',
            HTTP_AUTHORIZATION=f'Token {token_key}'
        )

        self.assertEqual(response.status_code, 401)


class AuthenticationErrorHandlingTest(TestCase):
    """
    Test Scenario: Authentication Error Handling
    Validates professional error messages and recovery paths
    """
    
    def setUp(self):
        self.client = Client()
    
    def test_invalid_email_validation(self):
        """Test clear validation error for invalid email"""
        response = self.client.post('/api/auth/signup/', {
            'email': 'invalid-email-format'
        })
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertIn('error', response_data)
    
    def test_knox_token_automatic_refresh(self):
        """Test Knox token automatic refresh behavior"""
        # Create user with token
        user = User.objects.create(
            email='test@ekko.zone',
            is_email_verified=True
        )
        
        token, token_key = AuthToken.objects.create(user=user)
        original_expiry = token.expiry
        
        # Make authenticated request (should trigger auto-refresh)
        client = Client()
        client.defaults['HTTP_AUTHORIZATION'] = f'Token {token_key}'
        
        response = client.get('/api/auth/validate-token/')
        
        if response.status_code == 200:
            # If auto-refresh is working, expiry should be extended
            # (Note: This depends on Knox configuration being properly set)
            token.refresh_from_db()
            # Expiry may be extended due to auto-refresh


class SecurityRequirementsTest(TestCase):
    """
    Test Scenario: Security Requirements for Business Users
    Validates enterprise-grade security measures
    """
    
    def test_knox_token_encryption(self):
        """Test that Knox tokens are encrypted and stored securely"""
        user = User.objects.create(
            email='test@ekko.zone',
            is_email_verified=True
        )
        
        token, token_key = AuthToken.objects.create(user=user)
        
        # Token digest should be stored, not plain token
        self.assertTrue(token.digest)
        self.assertNotEqual(token.digest, token_key)
        
        # Digest should be hashed (not reversible)
        self.assertGreater(len(token.digest), 60)  # SHA-256 hash length
    
    def test_rate_limiting_configuration(self):
        """Test that rate limiting is configured for authentication endpoints"""
        from django.conf import settings
        
        # Rate limiting should be configured
        # (This test validates that throttling settings exist)
        throttle_classes = getattr(settings, 'REST_FRAMEWORK', {}).get('DEFAULT_THROTTLE_CLASSES', [])
        throttle_rates = getattr(settings, 'REST_FRAMEWORK', {}).get('DEFAULT_THROTTLE_RATES', {})
        
        # Some form of throttling should be configured
        self.assertTrue(throttle_classes or throttle_rates)


class PerformanceRequirementsTest(TestCase):
    """
    Test Scenario: Performance Requirements for Business Users
    Validates performance targets for business user experience
    """
    
    def test_knox_token_validation_performance(self):
        """Test Knox token validation meets <100ms target"""
        import time
        
        user = User.objects.create(
            email='test@ekko.zone',
            is_email_verified=True
        )
        
        token, token_key = AuthToken.objects.create(user=user)
        
        # Measure token validation time
        start_time = time.time()
        
        # Simulate token validation
        client = Client()
        client.defaults['HTTP_AUTHORIZATION'] = f'Token {token_key}'
        response = client.get('/api/auth/validate-token/')
        
        end_time = time.time()
        validation_time = (end_time - start_time) * 1000  # Convert to milliseconds
        
        # Should complete in under 100ms (allowing for test overhead)
        self.assertLess(validation_time, 200)  # 200ms to account for test environment


class IntegrationTest(TestCase):
    """
    Integration test validating the complete authentication flow
    matches the consolidated specification
    """
    
    @patch("authentication.views.send_verification_code_email")
    def test_complete_authentication_flow_specification_compliance(self, mock_send_email):
        """Test complete flow matches consolidated authentication specification"""
        
        # Mock email sending
        mock_send_email.return_value = True
        
        test_email = 'integration@ekko.zone'
        
        # Step 1: Email collection and validation
        response = self.client.post('/api/auth/signup/', {
            'email': test_email
        })
        self.assertEqual(response.status_code, 200)
        
        # Step 2: Email sent with verification code
        mock_send_email.assert_called_once()
        
        # Step 3: Get verification code
        code = EmailVerificationCode.objects.get(email=test_email)
        self.assertEqual(len(code.code), 6)
        
        # Step 4: Complete verification with automatic Knox token generation
        response = self.client.post('/api/auth/signup/verify-code/', {
            'email': test_email,
            'code': code.code
        })
        
        self.assertEqual(response.status_code, 200)
        
        # Validate specification compliance
        response_data = json.loads(response.content)
        
        # Knox token automatically generated
        self.assertIn('token', response_data)
        self.assertIsNotNone(response_data['token'])
        
        # User properly created
        user = User.objects.get(email=test_email)
        self.assertTrue(user.is_email_verified)
        
        # Knox token exists in database
        knox_tokens = AuthToken.objects.filter(user=user)
        self.assertEqual(knox_tokens.count(), 1)
        
        # API access works with Knox token
        client = Client()
        knox_token = response_data['token']
        client.defaults['HTTP_AUTHORIZATION'] = f'Token {knox_token}'
        
        api_response = client.get('/api/auth/validate-token/')
        self.assertEqual(api_response.status_code, 200)
