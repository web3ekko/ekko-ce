"""
Firebase Authentication Utilities for Email Link Generation

Provides utilities for generating Firebase email action links for:
- Password reset
- Email verification  
- Passwordless sign-in

Uses Firebase Admin SDK for secure server-side link generation.
"""

import json
import logging
from typing import Optional, Dict, Any

import firebase_admin
from firebase_admin import auth, credentials
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)


class FirebaseAuthManager:
    """
    Manager class for Firebase Authentication operations
    """
    
    _instance = None
    _app = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize_firebase()
        return cls._instance
    
    def _initialize_firebase(self):
        """
        Initialize Firebase Admin SDK
        """
        if self._app is not None:
            return
            
        try:
            # Check if Firebase is already initialized
            firebase_admin.get_app()
            logger.info("Firebase Admin SDK already initialized")
            return
        except ValueError:
            # Firebase not initialized, proceed with initialization
            pass
        
        firebase_config = getattr(settings, 'FIREBASE_ADMIN_CONFIG', {})
        project_id = firebase_config.get('project_id')
        
        if not project_id:
            logger.warning("Firebase project ID not configured, Firebase features will be disabled")
            return
        
        # Initialize Firebase with service account credentials
        cred = self._get_credentials(firebase_config)
        
        if cred:
            self._app = firebase_admin.initialize_app(cred, {
                'projectId': project_id
            })
            logger.info(f"Firebase Admin SDK initialized for project: {project_id}")
        else:
            logger.warning("Firebase credentials not found, Firebase features will be disabled")
    
    def _get_credentials(self, config: Dict[str, Any]) -> Optional[credentials.Certificate]:
        """
        Get Firebase credentials from configuration
        """
        # Try service account key file path first
        credentials_path = config.get('credentials_path')
        if credentials_path:
            try:
                return credentials.Certificate(credentials_path)
            except Exception as e:
                logger.error(f"Failed to load Firebase credentials from file: {e}")
        
        # Try service account key JSON string or dict
        service_account_key = config.get('service_account_key')
        if service_account_key:
            try:
                # Check if it's already a dict (parsed by Django settings) or a string that needs parsing
                if isinstance(service_account_key, dict):
                    key_dict = service_account_key
                else:
                    key_dict = json.loads(service_account_key)
                return credentials.Certificate(key_dict)
            except Exception as e:
                logger.error(f"Failed to parse Firebase service account key: {e}")
        
        # Try default credentials (for Google Cloud environments)
        try:
            return credentials.ApplicationDefault()
        except Exception as e:
            logger.debug(f"Default credentials not available: {e}")
        
        return None
    
    def is_available(self) -> bool:
        """
        Check if Firebase is properly configured and available
        """
        return self._app is not None
    
    def generate_password_reset_link(
        self, 
        email: str, 
        action_code_settings: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate a password reset link using Firebase Admin SDK
        
        Args:
            email: User's email address
            action_code_settings: Optional action code settings
            
        Returns:
            Password reset link
            
        Raises:
            ImproperlyConfigured: If Firebase is not properly configured
            Exception: If link generation fails
        """
        if not self.is_available():
            raise ImproperlyConfigured("Firebase Admin SDK is not properly configured")
        
        try:
            if action_code_settings:
                link = auth.generate_password_reset_link(email, action_code_settings)
            else:
                link = auth.generate_password_reset_link(email)
            
            logger.info(f"Generated password reset link for {email}")
            return link
            
        except Exception as e:
            logger.error(f"Failed to generate password reset link for {email}: {e}")
            raise
    
    def generate_email_verification_link(
        self, 
        email: str, 
        action_code_settings: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate an email verification link using Firebase Admin SDK
        
        Args:
            email: User's email address
            action_code_settings: Optional action code settings
            
        Returns:
            Email verification link
            
        Raises:
            ImproperlyConfigured: If Firebase is not properly configured
            Exception: If link generation fails
        """
        if not self.is_available():
            logger.error(f"🔥 Firebase not available for email verification link: {email}")
            raise ImproperlyConfigured("Firebase Admin SDK is not properly configured")

        try:
            logger.info(f"🔥 Generating Firebase email verification link for: {email}")
            logger.info(f"🔥 Action code settings provided: {action_code_settings is not None}")

            if action_code_settings:
                logger.info(f"🔥 Using action code settings: {action_code_settings}")
                link = auth.generate_email_verification_link(email, action_code_settings)
            else:
                logger.info(f"🔥 Using default settings for email verification link")
                link = auth.generate_email_verification_link(email)

            logger.info(f"🔥 Successfully generated email verification link for: {email}")
            logger.info(f"🔥 Generated link: {link[:50]}...")  # Log first 50 chars for security
            return link

        except Exception as e:
            logger.error(f"🔥 Failed to generate email verification link for {email}: {e}")
            logger.error(f"🔥 Exception type: {type(e).__name__}")
            logger.error(f"🔥 Exception details: {str(e)}")
            raise

    def create_user(self, email: str, **kwargs):
        """
        Create a user in Firebase Auth

        Args:
            email: User's email address
            **kwargs: Additional user properties

        Returns:
            Firebase UserRecord

        Raises:
            ImproperlyConfigured: If Firebase is not properly configured
            Exception: If user creation fails
        """
        if not self.is_available():
            raise ImproperlyConfigured("Firebase Admin SDK is not properly configured")

        try:
            user_record = auth.create_user(
                email=email,
                email_verified=False,  # Will be verified via email link
                **kwargs
            )
            logger.info(f"🔥 Created Firebase user: {email} (uid: {user_record.uid})")
            return user_record

        except Exception as e:
            logger.error(f"🔥 Failed to create Firebase user for {email}: {e}")
            raise
    
    def verify_id_token(self, id_token: str) -> Dict[str, Any]:
        """
        Verify a Firebase ID token

        Args:
            id_token: Firebase ID token to verify

        Returns:
            Decoded token claims

        Raises:
            ImproperlyConfigured: If Firebase is not properly configured
            Exception: If token verification fails
        """
        if not self.is_available():
            raise ImproperlyConfigured("Firebase Admin SDK is not properly configured")

        try:
            decoded_token = auth.verify_id_token(id_token)
            logger.debug(f"Verified ID token for user: {decoded_token.get('uid')}")
            return decoded_token

        except Exception as e:
            logger.error(f"Failed to verify ID token: {e}")
            raise

    def create_custom_token(self, uid: str, additional_claims: Dict[str, Any] = None) -> bytes:
        """
        Create a Firebase custom token

        Args:
            uid: User ID for the custom token
            additional_claims: Optional additional claims to include

        Returns:
            Custom token as bytes

        Raises:
            ImproperlyConfigured: If Firebase is not properly configured
            Exception: If token creation fails
        """
        if not self.is_available():
            raise ImproperlyConfigured("Firebase Admin SDK is not properly configured")

        try:
            custom_token = auth.create_custom_token(uid, additional_claims)
            logger.info(f"Created custom token for user: {uid}")
            return custom_token

        except Exception as e:
            logger.error(f"Failed to create custom token for user {uid}: {e}")
            raise


# Singleton instance
firebase_auth_manager = FirebaseAuthManager()


def create_action_code_settings(
    continue_url: str,
    handle_code_in_app: bool = True,
    ios_bundle_id: Optional[str] = None,
    android_package_name: Optional[str] = None,
    android_install_app: bool = True,
    android_minimum_version: Optional[str] = None,
    link_domain: Optional[str] = None
):
    """
    Create action code settings for Firebase email links

    Args:
        continue_url: URL to redirect to after action completion
        handle_code_in_app: Whether to handle the code in the app
        ios_bundle_id: iOS bundle ID for mobile app handling
        android_package_name: Android package name for mobile app handling
        android_install_app: Whether to install Android app if not present
        android_minimum_version: Minimum Android app version
        link_domain: Custom domain for the link

    Returns:
        Firebase ActionCodeSettings object
    """
    from firebase_admin.auth import ActionCodeSettings

    # Create the ActionCodeSettings object
    action_code_settings = ActionCodeSettings(
        url=continue_url,
        handle_code_in_app=handle_code_in_app
    )

    # Add iOS settings if provided
    if ios_bundle_id:
        action_code_settings.ios_bundle_id = ios_bundle_id

    # Add Android settings if provided
    if android_package_name:
        action_code_settings.android_package_name = android_package_name
        action_code_settings.android_install_app = android_install_app
        if android_minimum_version:
            action_code_settings.android_minimum_version = android_minimum_version

    # Add custom domain if provided
    if link_domain:
        action_code_settings.dynamic_link_domain = link_domain

    return action_code_settings
