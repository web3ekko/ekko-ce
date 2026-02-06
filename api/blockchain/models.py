"""
Blockchain and wallet management models
Converted from SQLAlchemy to Django ORM
"""

import uuid
import json
from django.db import models
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.exceptions import ValidationError

User = get_user_model()

# Import WalletNickname model
from .models_wallet_nicknames import WalletNickname


class Chain(models.Model):
    """Blockchain networks for the new alert system"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)  # "ethereum", "polygon", "avalanche"
    display_name = models.CharField(max_length=100)       # "Ethereum", "Polygon", "Avalanche"
    chain_id = models.IntegerField(unique=True, null=True, blank=True)  # 1, 137, 43114
    rpc_url = models.URLField(max_length=500, blank=True)
    explorer_url = models.URLField(max_length=500, blank=True)
    native_token = models.CharField(max_length=10, blank=True)  # "ETH", "MATIC", "AVAX"
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'chains'
        verbose_name = 'Chain'
        verbose_name_plural = 'Chains'
        ordering = ['display_name']
        indexes = [
            models.Index(fields=['enabled']),
            models.Index(fields=['name']),
        ]

    def __str__(self):
        return self.display_name

    def get_native_token(self):
        """Get the native token object for this chain"""
        return self.tokens.filter(is_native=True).first()

    @property
    def native_token_object(self):
        """Property to access native token object"""
        if not hasattr(self, '_native_token_cache'):
            self._native_token_cache = self.get_native_token()
        return self._native_token_cache


class SubChain(models.Model):
    """Sub-networks within chains (mainnet, testnets, L2s)"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chain = models.ForeignKey(Chain, on_delete=models.CASCADE, related_name='sub_chains')
    name = models.CharField(max_length=100)               # "mainnet", "goerli", "arbitrum"
    display_name = models.CharField(max_length=100)       # "Mainnet", "Goerli Testnet", "Arbitrum One"
    network_id = models.IntegerField(null=True, blank=True)
    rpc_url = models.URLField(max_length=500, blank=True)
    explorer_url = models.URLField(max_length=500, blank=True)
    is_testnet = models.BooleanField(default=False)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sub_chains'
        verbose_name = 'Sub Chain'
        verbose_name_plural = 'Sub Chains'
        unique_together = ['chain', 'name']
        ordering = ['chain__display_name', 'display_name']
        indexes = [
            models.Index(fields=['chain', 'enabled']),
            models.Index(fields=['is_testnet']),
        ]

    def __str__(self):
        return f"{self.chain.display_name} - {self.display_name}"


class Blockchain(models.Model):
    """Blockchain networks (ETH, BTC, SOL, etc.)"""

    id = models.UUIDField(default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True, null=True, blank=True)
    symbol = models.CharField(max_length=255, unique=True, primary_key=True)  # Primary key like original
    chain_type = models.CharField(max_length=255, null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'blockchain'
        verbose_name = 'Blockchain'
        verbose_name_plural = 'Blockchains'

    def __str__(self):
        return f"{self.name} ({self.symbol})" if self.name else self.symbol


class Category(models.Model):
    """Categories for organizing content"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'categories'
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name


class Dao(models.Model):
    """Decentralized Autonomous Organizations"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    recommended = models.BooleanField(default=False)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'dao'
        verbose_name = 'DAO'
        verbose_name_plural = 'DAOs'

    def __str__(self):
        return self.name


class Wallet(models.Model):
    """Blockchain wallet addresses"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    blockchain = models.ForeignKey(
        Blockchain,
        on_delete=models.CASCADE,
        related_name='wallets',
        to_field='symbol',
        db_column='blockchain_symbol'
    )
    address = models.CharField(max_length=255)
    name = models.TextField()
    derived_name = models.CharField(max_length=255, null=True, blank=True)
    domains = models.JSONField(null=True, blank=True)  # ENS domains, etc.
    recommended = models.BooleanField(default=False)

    # Extended fields from ekko-ce integration
    balance = models.CharField(max_length=255, null=True, blank=True)  # Handle large numbers
    status = models.CharField(max_length=50, default='active')  # active, inactive, monitoring
    subnet = models.CharField(max_length=100, default='mainnet')  # mainnet, testnet, etc.
    description = models.TextField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'wallet'
        verbose_name = 'Wallet'
        verbose_name_plural = 'Wallets'
        unique_together = [['blockchain', 'subnet', 'address']]
        indexes = [
            models.Index(fields=['blockchain']),
            models.Index(fields=['address']),
            models.Index(fields=['recommended']),
        ]

    def generate_derived_name(self):
        """Generate display name like original model"""
        address_display = f"{self.address[:6]}...{self.address[-4:]}"
        if self.name:
            return f"{self.name} ({address_display})"
        elif self.domains:
            # Pick first domain from first key's list
            first_key = next(iter(self.domains))
            domain_name = (
                self.domains[first_key][0] if self.domains[first_key] else "No Domain"
            )
            return f"{domain_name} ({address_display})"
        else:
            return f"({address_display})"

    def save(self, *args, **kwargs):
        if self.address:
            self.address = self.address.strip()
            if self.address.lower().startswith("0x"):
                self.address = self.address.lower()

        if self.subnet:
            self.subnet = self.subnet.strip().lower()

        if not self.derived_name:
            self.derived_name = self.generate_derived_name()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.derived_name or self.generate_derived_name()


class DaoSubscription(models.Model):
    """User subscriptions to DAO notifications"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, null=True, blank=True)
    dao = models.ForeignKey(Dao, on_delete=models.CASCADE, related_name='subscriptions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dao_subscriptions')
    notifications_count = models.IntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'daoSubscription'
        verbose_name = 'DAO Subscription'
        verbose_name_plural = 'DAO Subscriptions'
        unique_together = [['dao', 'user']]
        indexes = [
            models.Index(fields=['dao']),
            models.Index(fields=['user']),
        ]

    def derived_name(self):
        """Get derived name from DAO"""
        return self.dao.name if self.dao else self.name

    def __str__(self):
        return self.derived_name()


class WalletSubscription(models.Model):
    """User subscriptions to wallet notifications"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='subscriptions')
    name = models.CharField(max_length=255, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wallet_subscriptions')
    notifications_count = models.IntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'walletSubscription'
        verbose_name = 'Wallet Subscription'
        verbose_name_plural = 'Wallet Subscriptions'
        unique_together = [['wallet', 'user']]
        indexes = [
            models.Index(fields=['wallet']),
            models.Index(fields=['user']),
        ]

    def derived_name(self):
        """Get derived name from wallet"""
        return self.wallet.derived_name if self.wallet else self.name

    def __str__(self):
        return self.derived_name()


class DaoWallet(models.Model):
    """Many-to-many relationship between DAOs and wallets"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dao = models.ForeignKey(Dao, on_delete=models.CASCADE, related_name='dao_wallets')
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='dao_wallets')

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'daoWallet'
        verbose_name = 'DAO Wallet'
        verbose_name_plural = 'DAO Wallets'
        unique_together = [['dao', 'wallet']]
        indexes = [
            models.Index(fields=['dao']),
            models.Index(fields=['wallet']),
        ]

    def __str__(self):
        return f"{self.dao.name} - {self.wallet.derived_name}"


class Token(models.Model):
    """Blockchain tokens (native and ERC20/BEP20/etc)"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Chain relationship (replacing blockchain)
    chain = models.ForeignKey(
        Chain,
        on_delete=models.CASCADE,
        related_name='tokens',
        help_text="The blockchain network this token belongs to"
    )

    # Token details
    name = models.CharField(max_length=255, help_text="Token name (e.g., Ethereum, Polygon)")
    symbol = models.CharField(max_length=10, help_text="Token symbol (e.g., ETH, MATIC)")
    decimals = models.IntegerField(default=18, help_text="Number of decimals for the token")

    # Native token flag
    is_native = models.BooleanField(
        default=False,
        help_text="Whether this is the native token of the chain",
        db_index=True
    )

    # Contract address (null for native tokens)
    contract_address = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Smart contract address (null for native tokens)"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'token'
        verbose_name = 'Token'
        verbose_name_plural = 'Tokens'
        indexes = [
            models.Index(fields=['chain', 'is_native']),
            models.Index(fields=['chain', 'contract_address']),
            models.Index(fields=['symbol']),
            models.Index(fields=['is_native']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['chain'],
                condition=models.Q(is_native=True),
                name='unique_native_token_per_chain'
            ),
            models.UniqueConstraint(
                fields=['chain', 'contract_address'],
                name='unique_contract_per_chain'
            )
        ]

    def __str__(self):
        if self.is_native:
            return f"{self.name} ({self.symbol}) - Native"
        return f"{self.name} ({self.symbol})"

    def clean(self):
        """Validate token configuration"""
        from django.core.exceptions import ValidationError

        if self.is_native:
            # Native tokens should not have contract address
            if self.contract_address:
                raise ValidationError({
                    'contract_address': 'Native tokens should not have a contract address'
                })
            # Check if another native token exists for this chain
            existing = Token.objects.filter(
                chain=self.chain,
                is_native=True
            ).exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError({
                    'is_native': f'Chain {self.chain} already has a native token'
                })
        else:
            # Non-native tokens must have contract address
            if not self.contract_address:
                raise ValidationError({
                    'contract_address': 'Non-native tokens must have a contract address'
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

        # Update chain's native_token field if this is native
        if self.is_native:
            self.chain.native_token = self.symbol
            self.chain.save(update_fields=['native_token'])

    def get_redis_key(self, subnet='mainnet'):
        """Generate Redis key for this token"""
        if self.is_native:
            return f"native_token:{self.chain.name}:{subnet}"
        return f"token:{self.chain.name}:{self.contract_address}"

    def to_redis_dict(self, subnet='mainnet'):
        """Convert to dictionary for Redis storage"""
        return {
            'symbol': self.symbol,
            'name': self.name,
            'decimals': self.decimals,
            'is_native': self.is_native,
            'contract_address': self.contract_address,
            'chain_name': self.chain.name,
            'chain_display_name': self.chain.display_name,
            'network': self.chain.name,
            'subnet': subnet
        }


class Image(models.Model):
    """Image storage"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    url = models.URLField(max_length=1024)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'images'
        verbose_name = 'Image'
        verbose_name_plural = 'Images'

    def __str__(self):
        return self.url


class Story(models.Model):
    """News stories and content"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    content = models.TextField(null=True, blank=True)
    publication_date = models.DateTimeField(null=True, blank=True)
    image_url = models.URLField(max_length=1024, null=True, blank=True)
    url = models.URLField(max_length=1024, null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'story'
        verbose_name = 'Story'
        verbose_name_plural = 'Stories'

    def __str__(self):
        return self.title or f"Story {self.id}"


class BlockchainStory(models.Model):
    """Many-to-many relationship between stories and blockchains"""

    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name='blockchain_stories')
    blockchain = models.ForeignKey(
        Blockchain,
        on_delete=models.CASCADE,
        to_field='symbol',
        db_column='blockchain_symbol'
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'story_blockchain'
        verbose_name = 'Blockchain Story'
        verbose_name_plural = 'Blockchain Stories'
        unique_together = [['story', 'blockchain']]

    def __str__(self):
        return f"{self.story.title} - {self.blockchain.symbol}"


class Tag(models.Model):
    """Content tags"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tags'
        verbose_name = 'Tag'
        verbose_name_plural = 'Tags'

    def __str__(self):
        return self.name


class WalletBalance(models.Model):
    """Wallet balance history tracking"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='balance_history')
    balance = models.CharField(max_length=255)  # Handle large numbers as string
    token_price = models.CharField(max_length=255, null=True, blank=True)  # Token price in USD
    fiat_value = models.CharField(max_length=255, null=True, blank=True)  # Fiat value in USD
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wallet_balances'
        verbose_name = 'Wallet Balance'
        verbose_name_plural = 'Wallet Balances'
        indexes = [
            models.Index(fields=['wallet']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['wallet', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.wallet} - {self.balance} at {self.timestamp}"


# Redis client configuration
def get_redis_client():
    """Get Redis client instance"""
    try:
        import redis
        # TODO: Get Redis configuration from Django settings
        return redis.Redis(
            host='localhost',
            port=6379,
            db=0,
            decode_responses=True
        )
    except ImportError:
        print("Redis not installed, skipping Redis population")
        return None


# Signal handlers for Redis population
@receiver(post_save, sender=Token)
def populate_redis_on_token_save(sender, instance, created, **kwargs):
    """Populate Redis when a Token is saved (especially native tokens)"""
    if not instance.is_native:
        return  # Only populate Redis for native tokens for now

    try:
        redis_client = get_redis_client()
        if not redis_client:
            return

        # For native tokens, create entries for common subnets
        subnets = ['mainnet', 'testnet', 'devnet']
        for subnet in subnets:
            redis_key = instance.get_redis_key(subnet)
            redis_value = json.dumps(instance.to_redis_dict(subnet))

            # Set the token data in Redis
            redis_client.set(redis_key, redis_value)

            # Also set a mapping from network/subnet to token symbol for quick lookups
            mapping_key = f"token_mapping:{instance.chain.name}:{subnet}"
            redis_client.set(mapping_key, instance.symbol)

        print(f"✅ Redis populated with native token: {instance.symbol} for {instance.chain.name}")
    except Exception as e:
        print(f"❌ Failed to populate Redis for token {instance.symbol}: {e}")


@receiver(post_delete, sender=Token)
def remove_from_redis_on_token_delete(sender, instance, **kwargs):
    """Remove from Redis when a Token is deleted"""
    if not instance.is_native:
        return  # Only handle native tokens for now

    try:
        redis_client = get_redis_client()
        if not redis_client:
            return

        # Remove entries for all subnets
        subnets = ['mainnet', 'testnet', 'devnet']
        for subnet in subnets:
            redis_key = instance.get_redis_key(subnet)
            mapping_key = f"token_mapping:{instance.chain.name}:{subnet}"

            # Delete the token data from Redis
            redis_client.delete(redis_key)
            redis_client.delete(mapping_key)

        print(f"✅ Redis cleaned up for token: {instance.symbol}")
    except Exception as e:
        print(f"❌ Failed to remove from Redis for token {instance.symbol}: {e}")


@receiver(post_save, sender=Chain)
def update_chain_native_token(sender, instance, created, **kwargs):
    """Update native token field when chain is saved"""
    try:
        # If chain has a native token object, ensure the field is in sync
        native_token = instance.get_native_token()
        if native_token and instance.native_token != native_token.symbol:
            instance.native_token = native_token.symbol
            instance.save(update_fields=['native_token'])
    except Exception as e:
        print(f"❌ Failed to update native token for chain {instance.name}: {e}")
