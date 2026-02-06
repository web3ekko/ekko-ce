"""
Wallet Nicknames - Custom names for blockchain wallet addresses
Enables personalized notifications showing "CustomName (0x1234...5678)" instead of just addresses
"""

import uuid
import re
import logging
from typing import Optional
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinLengthValidator, MaxLengthValidator
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

logger = logging.getLogger(__name__)
User = get_user_model()


class WalletNickname(models.Model):
    """
    User-defined custom names for blockchain wallet addresses.

    Enables personalized notifications where alerts show friendly names
    instead of just truncated addresses. Each user can maintain their own
    nicknames for wallet addresses they monitor.

    Example: "My Main Wallet (0x1234...5678)" instead of "0x1234...5678"
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='wallet_nicknames',
        help_text="The user who created this nickname"
    )
    wallet_address = models.CharField(
        max_length=255,
        db_index=True,
        help_text="The blockchain wallet address (e.g., 0x1234...)"
    )
    custom_name = models.CharField(
        max_length=50,
        validators=[MinLengthValidator(1), MaxLengthValidator(50)],
        help_text="Custom name for the wallet (1-50 characters)"
    )
    chain_id = models.IntegerField(
        db_index=True,
        help_text="Blockchain network chain ID (e.g., 1 for Ethereum mainnet)"
    )
    notes = models.TextField(
        blank=True,
        default='',
        help_text="Optional notes about this wallet"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'wallet_nicknames'
        verbose_name = 'Wallet Nickname'
        verbose_name_plural = 'Wallet Nicknames'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'chain_id']),
            models.Index(fields=['wallet_address']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'wallet_address', 'chain_id'],
                name='unique_user_wallet_chain'
            )
        ]

    def __str__(self) -> str:
        """Return friendly display format: CustomName (0xABCD...5678)"""
        truncated = self.truncate_address(self.wallet_address)
        return f"{self.custom_name} ({truncated})"

    @staticmethod
    def truncate_address(address: str, prefix_len: int = 6, suffix_len: int = 4) -> str:
        """
        Truncate blockchain address to readable format.

        Args:
            address: Full blockchain address
            prefix_len: Number of characters to show at start (default: 6 including 0x)
            suffix_len: Number of characters to show at end (default: 4)

        Returns:
            Truncated address in format "0xABCD...5678"

        Examples:
            >>> WalletNickname.truncate_address("0x1234567890abcdef1234567890abcdef12345678")
            "0x1234...5678"
        """
        if not address:
            return ""

        # Handle addresses shorter than truncation length
        if len(address) <= (prefix_len + suffix_len + 3):  # +3 for "..."
            return address

        return f"{address[:prefix_len]}...{address[-suffix_len:]}"

    def clean(self) -> None:
        """
        Validate wallet address format.

        Currently validates EVM addresses (0x followed by 40 hex characters).
        Can be extended for other blockchain address formats.

        Raises:
            ValidationError: If wallet_address format is invalid
        """
        super().clean()

        # Normalize address to lowercase for consistency
        if self.wallet_address:
            self.wallet_address = self.wallet_address.lower().strip()

        # Validate EVM address format (0x followed by 40 hex characters)
        # This covers Ethereum, Polygon, Avalanche, BSC, etc.
        evm_pattern = r'^0x[a-fA-F0-9]{40}$'

        if not re.match(evm_pattern, self.wallet_address):
            # Check if it might be a Bitcoin or Solana address
            # Bitcoin: starts with 1, 3, or bc1 (base58/bech32)
            # Solana: base58 encoded, typically 32-44 characters
            bitcoin_pattern = r'^(1|3|bc1)[a-zA-Z0-9]{25,62}$'
            solana_pattern = r'^[1-9A-HJ-NP-Za-km-z]{32,44}$'

            if re.match(bitcoin_pattern, self.wallet_address):
                # Valid Bitcoin address
                pass
            elif re.match(solana_pattern, self.wallet_address):
                # Valid Solana address
                pass
            else:
                raise ValidationError({
                    'wallet_address': (
                        'Invalid wallet address format. Must be a valid blockchain address '
                        '(EVM: 0x followed by 40 hex characters, Bitcoin: standard address, '
                        'Solana: base58 encoded address)'
                    )
                })

    def save(self, *args, **kwargs) -> None:
        """Save with validation"""
        self.full_clean()
        super().save(*args, **kwargs)

    def get_display_name(self) -> str:
        """
        Get formatted display name for notifications.

        Returns:
            Formatted string: "CustomName (0xABCD...5678)"
        """
        return str(self)

    @classmethod
    def get_nickname_for_address(
        cls,
        user: User,
        address: str,
        chain_id: int
    ) -> Optional['WalletNickname']:
        """
        Retrieve a wallet nickname for a specific user, address, and chain.

        Args:
            user: The user who owns the nickname
            address: The wallet address
            chain_id: The blockchain chain ID

        Returns:
            WalletNickname instance if found, None otherwise
        """
        try:
            return cls.objects.get(
                user=user,
                wallet_address=address.lower(),
                chain_id=chain_id
            )
        except cls.DoesNotExist:
            return None

    @classmethod
    def get_display_name_or_address(
        cls,
        user: User,
        address: str,
        chain_id: int
    ) -> str:
        """
        Get custom name if exists, otherwise return truncated address.

        Args:
            user: The user who might have a nickname
            address: The wallet address
            chain_id: The blockchain chain ID

        Returns:
            Custom name with truncated address, or just truncated address

        Examples:
            >>> # With nickname
            >>> WalletNickname.get_display_name_or_address(user, "0x1234...", 1)
            "My Wallet (0x1234...5678)"

            >>> # Without nickname
            >>> WalletNickname.get_display_name_or_address(user, "0x1234...", 1)
            "0x1234...5678"
        """
        nickname = cls.get_nickname_for_address(user, address, chain_id)
        if nickname:
            return nickname.get_display_name()
        return cls.truncate_address(address)


# ===================================================================
# Django Signals for Redis Cache Invalidation
# ===================================================================

@receiver(post_save, sender=WalletNickname)
@receiver(post_delete, sender=WalletNickname)
def invalidate_wallet_nickname_cache(sender, instance, **kwargs):
    """
    Invalidate wallet nickname cache when WalletNickname is created, updated, or deleted.

    This ensures the Redis cache stays in sync with the database by removing
    the cached data. The next access will repopulate the cache from PostgreSQL.

    Args:
        sender: The model class (WalletNickname)
        instance: The WalletNickname instance being saved/deleted
        **kwargs: Additional signal arguments (created, using, etc.)
    """
    try:
        from app.services.notification_cache import NotificationCacheManager
        cache_manager = NotificationCacheManager()
        cache_manager.invalidate_wallet_nicknames(str(instance.user_id))
        logger.info(f"Invalidated wallet nickname cache for user {instance.user_id}")
    except Exception as e:
        # Signal handlers should NOT raise exceptions that break model operations
        logger.error(f"Error invalidating wallet nickname cache for user {instance.user_id}: {e}")
