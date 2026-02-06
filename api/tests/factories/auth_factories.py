"""
Django model factories for authentication models
Uses factory_boy for consistent test data generation
"""
import factory
import uuid
from datetime import datetime, timedelta
from faker import Faker
from django.contrib.auth import get_user_model
from django.utils import timezone

from authentication.models import (
    UserDevice,
    AuthenticationLog,
    EmailVerificationCode,
)

fake = Faker()
User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    """Factory for User model"""

    class Meta:
        model = User
        skip_postgeneration_save = True

    email = factory.Faker("email")  # Generates unique random emails
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    is_active = True
    is_email_verified = True
    has_passkey = False
    preferred_auth_method = "passkey"
    username = factory.LazyAttribute(lambda obj: obj.email)  # Use email as username
    firebase_uid = factory.LazyFunction(lambda: f"firebase_{uuid.uuid4().hex}")  # Unique firebase UID
    
    # Timestamps are handled by Django automatically
    
    @factory.post_generation
    def set_password(self, create, extracted, **kwargs):
        """Set a password for the user (though we use passwordless auth)"""
        if not create:
            return
        # Set an unusable password since we use passwordless auth
        self.set_unusable_password()
        self.save()


class AdminUserFactory(UserFactory):
    """Factory for admin users"""

    email = factory.Faker("email")  # Generates unique random emails
    is_staff = True
    is_superuser = True


class UserDeviceFactory(factory.django.DjangoModelFactory):
    """Factory for UserDevice model"""
    
    class Meta:
        model = UserDevice
    
    user = factory.SubFactory(UserFactory)
    device_name = factory.Faker("word")
    device_type = factory.Iterator(["web", "ios", "android", "desktop"])
    device_id = factory.LazyFunction(lambda: f"device_{uuid.uuid4().hex}")
    supports_passkey = True
    supports_biometric = False
    is_trusted = False
    device_fingerprint = factory.LazyFunction(lambda: fake.sha256()[:32])
    trust_expires_at = factory.LazyFunction(
        lambda: timezone.now() + timedelta(days=90)
    )


class AuthenticationLogFactory(factory.django.DjangoModelFactory):
    """Factory for AuthenticationLog model"""
    
    class Meta:
        model = AuthenticationLog
    
    user = factory.SubFactory(UserFactory)
    action = factory.Iterator(["login", "logout", "signup", "recovery", "2fa_setup"])
    method = factory.Iterator(["passkey", "email", "recovery_code", "totp"])
    success = True
    ip_address = factory.Faker("ipv4")
    user_agent = factory.Faker("user_agent")
    device_fingerprint = factory.LazyFunction(lambda: fake.sha256()[:32])
    error_message = None
    metadata = factory.LazyFunction(lambda: {"test": "data"})


class EmailVerificationCodeFactory(factory.django.DjangoModelFactory):
    """Factory for EmailVerificationCode model"""
    
    class Meta:
        model = EmailVerificationCode
    
    user = factory.SubFactory(UserFactory)
    code = factory.LazyFunction(lambda: f"{fake.random_int(100000, 999999)}")
    purpose = factory.Iterator(["login", "signup", "password_reset", "email_change"])
    expires_at = factory.LazyFunction(
        lambda: timezone.now() + timedelta(minutes=15)
    )
    is_used = False
    used_at = None


# Utility functions for creating related objects
def create_user_with_device(**user_kwargs):
    """Create a user with a trusted device"""
    user = UserFactory(**user_kwargs)
    device = UserDeviceFactory(user=user, is_trusted=True)
    return user, device


def create_verification_code_flow(user=None, purpose="login"):
    """Create a complete email verification flow"""
    if user is None:
        user = UserFactory()

    verification_code = EmailVerificationCodeFactory(user=user, purpose=purpose)
    auth_log = AuthenticationLogFactory(
        user=user,
        action=purpose,
        method="email"
    )

    return {
        'user': user,
        'verification_code': verification_code,
        'auth_log': auth_log,
    }


def create_complete_auth_setup(**user_kwargs):
    """
    Create a complete auth setup for tests.

    Notes:
    - Ekko's production auth uses Django Allauth MFA for passkeys + 2FA.
    - For unit/integration tests, we represent an enabled setup by setting
      `user.has_passkey` and `user.has_2fa` and returning a stable structure
      for downstream assertions.
    """
    user = UserFactory(**user_kwargs)
    device = UserDeviceFactory(user=user, is_trusted=True)

    user.has_passkey = True
    user.has_2fa = True
    user.save(update_fields=["has_passkey", "has_2fa"])

    passkey = {"kind": "webauthn", "user_id": str(user.id), "device_id": str(device.id)}
    recovery_codes = [f"RC-{i:02d}-{uuid.uuid4().hex[:8]}" for i in range(10)]

    return {
        "user": user,
        "device": device,
        "passkey": passkey,
        "recovery_codes": recovery_codes,
    }
