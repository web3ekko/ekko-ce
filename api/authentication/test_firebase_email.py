"""
Test Firebase Email Integration

Tests the Firebase email service integration for sending verification codes.
"""

import json
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status

from .firebase_utils import FirebaseAuthManager, create_action_code_settings
from .models import EmailVerificationCode

User = get_user_model()


class FirebaseAuthManagerTest(TestCase):
    """Test Firebase Auth Manager functionality"""
    
    def setUp(self):
        self.manager = FirebaseAuthManager()
    
    @patch('firebase_admin.initialize_app')
    @patch('firebase_admin.get_app')
    def test_firebase_initialization_success(self, mock_get_app, mock_init_app):
        """Test successful Firebase initialization"""
        mock_get_app.side_effect = ValueError("No app found")
        mock_init_app.return_value = MagicMock()
        
        with override_settings(FIREBASE_ADMIN_CONFIG={
            'project_id': 'test-project',
            'credentials_path': '/path/to/credentials.json'
        }):
            manager = FirebaseAuthManager()
            self.assertTrue(manager.is_available())
    
    @patch('firebase_admin.get_app')
    def test_firebase_already_initialized(self, mock_get_app):
        """Test when Firebase is already initialized"""
        mock_get_app.return_value = MagicMock()
        
        manager = FirebaseAuthManager()
        # Should not raise an exception
        self.assertIsNotNone(manager)
    
    def test_firebase_not_configured(self):
        """Test when Firebase is not configured"""
        with override_settings(FIREBASE_ADMIN_CONFIG={}):
            manager = FirebaseAuthManager()
            self.assertFalse(manager.is_available())
    
    @patch('firebase_admin.auth.create_user')
    def test_create_user_success(self, mock_create_user):
        """Test creating user in Firebase"""
        mock_user = MagicMock()
        mock_user.uid = 'firebase-uid-123'
        mock_user.email = 'test@example.com'
        mock_create_user.return_value = mock_user
        
        with patch.object(self.manager, 'is_available', return_value=True):
            user = self.manager.create_user('test@example.com')
            self.assertEqual(user.uid, 'firebase-uid-123')
            self.assertEqual(user.email, 'test@example.com')
    
    @patch('firebase_admin.auth.get_user_by_email')
    def test_get_user_by_email(self, mock_get_user):
        """Test getting user by email"""
        mock_user = MagicMock()
        mock_user.uid = 'firebase-uid-123'
        mock_user.email = 'test@example.com'
        mock_get_user.return_value = mock_user
        
        with patch.object(self.manager, 'is_available', return_value=True):
            user = self.manager.get_user_by_email('test@example.com')
            self.assertEqual(user.uid, 'firebase-uid-123')
    
    @patch('firebase_admin.auth.create_custom_token')
    def test_create_custom_token(self, mock_create_token):
        """Test creating custom auth token"""
        mock_create_token.return_value = b'custom-token-123'
        
        with patch.object(self.manager, 'is_available', return_value=True):
            token = self.manager.create_custom_token('firebase-uid-123')
            self.assertEqual(token, 'custom-token-123')
            mock_create_token.assert_called_once_with('firebase-uid-123', None)


class EmailVerificationCodeTest(TestCase):
    """Test email verification code functionality"""
    
    def setUp(self):
        self.client = Client()
        self.test_email = 'test@example.com'
    
    def test_code_generation(self):
        """Test verification code generation"""
        code = EmailVerificationCode.objects.create(
            email=self.test_email,
            code='123456',
            purpose='signup',
            ip_address='127.0.0.1',
            user_agent='TestAgent',
            expires_at=timezone.now() + timedelta(minutes=10)
        )
        
        self.assertEqual(len(code.code), 6)
        self.assertTrue(code.code.isdigit())
        self.assertFalse(code.is_used)
        self.assertFalse(code.is_expired)
        self.assertTrue(code.is_valid)
    
    def test_code_expiration(self):
        """Test code expiration logic"""
        code = EmailVerificationCode.objects.create(
            email=self.test_email,
            code='123456',
            purpose='signup',
            ip_address='127.0.0.1',
            user_agent='TestAgent',
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        
        self.assertTrue(code.is_expired)
        self.assertFalse(code.is_valid)
    
    def test_code_usage(self):
        """Test marking code as used"""
        code = EmailVerificationCode.objects.create(
            email=self.test_email,
            code='123456',
            purpose='signup',
            ip_address='127.0.0.1',
            user_agent='TestAgent',
            expires_at=timezone.now() + timedelta(minutes=10)
        )
        
        self.assertFalse(code.is_used)
        code.mark_as_used()
        self.assertTrue(code.is_used)
        self.assertFalse(code.is_valid)


class FirebaseEmailIntegrationTest(APITestCase):
    """Test Firebase email integration with API endpoints"""
    
    def setUp(self):
        self.test_email = 'test@example.com'
    
    @patch('authentication.firebase_utils.firebase_auth_manager.is_available')
    @patch('authentication.views_verification.send_verification_code_email')
    def test_signup_with_firebase_email(self, mock_send_email, mock_is_available):
        """Test signup flow with Firebase email service"""
        mock_is_available.return_value = True
        mock_send_email.return_value = True
        
        response = self.client.post('/api/auth/signup/', {
            'email': self.test_email
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('success', response.data)
        self.assertTrue(response.data['success'])
        
        # Check that verification code was created
        codes = EmailVerificationCode.objects.filter(
            email=self.test_email,
            purpose='signup'
        )
        self.assertEqual(codes.count(), 1)
    
    @patch('authentication.firebase_utils.firebase_auth_manager.is_available')
    @patch('authentication.views_verification.send_verification_code_email')
    def test_signin_with_firebase_email(self, mock_send_email, mock_is_available):
        """Test signin flow with Firebase email service"""
        mock_is_available.return_value = True
        mock_send_email.return_value = True
        
        # Create existing user
        User.objects.create(email=self.test_email, is_active=True)
        
        response = self.client.post('/api/auth/signin/email/', {
            'email': self.test_email
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('success', response.data)
        self.assertTrue(response.data['success'])
        
        # Check that verification code was created
        codes = EmailVerificationCode.objects.filter(
            email=self.test_email,
            purpose='signin'
        )
        self.assertEqual(codes.count(), 1)