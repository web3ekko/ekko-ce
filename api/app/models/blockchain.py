"""
Blockchain infrastructure models
"""

from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone


class VMType(models.TextChoices):
    EVM = 'EVM', 'Ethereum Virtual Machine'
    UTXO = 'UTXO', 'Unspent Transaction Output'
    SVM = 'SVM', 'Solana Virtual Machine'
    COSMOS = 'COSMOS', 'Cosmos SDK'


class BlockchainNode(models.Model):
    """
    Represents a blockchain node configuration for Ekko platform
    """
    chain_id = models.CharField(max_length=50, unique=True, db_index=True)
    chain_name = models.CharField(max_length=100)
    network = models.CharField(max_length=50, db_index=True)  # mainnet, testnet, etc.
    subnet = models.CharField(max_length=50, default='mainnet')
    vm_type = models.CharField(max_length=10, choices=VMType.choices)
    
    # Connection details
    rpc_url = models.URLField(max_length=500)
    ws_url = models.CharField(max_length=500, blank=True)  # Changed to CharField to accept ws:// and wss:// URLs
    
    # Status and configuration
    enabled = models.BooleanField(default=False, db_index=True)
    is_primary = models.BooleanField(default=False)
    priority = models.IntegerField(default=1)
    
    # Performance metrics
    latency_ms = models.IntegerField(null=True, blank=True)
    success_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    last_health_check = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'blockchain_nodes'
        ordering = ['network', 'priority']
        unique_together = [['network', 'subnet', 'is_primary']]
        indexes = [
            models.Index(fields=['network', 'enabled']),
            models.Index(fields=['vm_type', 'enabled']),
        ]
    
    def __str__(self):
        return f"{self.chain_name} ({self.network}-{self.subnet})"
    
    def clean(self):
        """Validate node configuration"""
        super().clean()
        
        # Only one primary node per network-subnet combination
        if self.is_primary and self.enabled:
            existing_primary = BlockchainNode.objects.filter(
                network=self.network,
                subnet=self.subnet,
                is_primary=True,
                enabled=True
            ).exclude(pk=self.pk)
            
            if existing_primary.exists():
                raise ValidationError({
                    'is_primary': f'There is already a primary node for {self.network}-{self.subnet}'
                })
        
        # Validate WebSocket URL for certain VM types
        if self.vm_type in [VMType.EVM, VMType.SVM] and not self.ws_url:
            raise ValidationError({
                'ws_url': f'WebSocket URL is required for {self.vm_type} nodes'
            })
        
        # Basic validation for WebSocket URLs
        if self.ws_url and not (self.ws_url.startswith('ws://') or self.ws_url.startswith('wss://')):
            raise ValidationError({
                'ws_url': 'WebSocket URL must start with ws:// or wss://'
            })
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    @property
    def is_healthy(self):
        """Check if node is considered healthy"""
        if not self.last_health_check:
            return False
        
        # Consider unhealthy if not checked in last 5 minutes
        time_since_check = timezone.now() - self.last_health_check
        if time_since_check.total_seconds() > 300:
            return False
        
        # Check success rate
        if self.success_rate and self.success_rate < 90:
            return False
        
        # Check latency
        if self.latency_ms and self.latency_ms > 1000:
            return False
        
        return True
    
    def get_connection_config(self):
        """Get connection configuration for wasmCloud actors"""
        return {
            'chain_id': self.chain_id,
            'chain_name': self.chain_name,
            'vm_type': self.vm_type,
            'rpc_url': self.rpc_url,
            'ws_url': self.ws_url,
            'priority': self.priority
        }

    def get_provider_config(self):
        """
        Get provider configuration for Redis storage.

        This format is used by wasmCloud providers to configure
        their blockchain connections. The config is stored in Redis
        and read by the provider on startup.

        Returns:
            dict: Provider configuration with all required fields
        """
        return {
            "provider_name": f"newheads-{self.vm_type.lower()}",
            "chain_id": self.chain_id,
            "chain_name": self.chain_name,
            "network": self.network,
            "subnet": self.subnet,
            "vm_type": self.vm_type.lower(),
            "rpc_url": self.rpc_url,
            "ws_url": self.ws_url,
            "enabled": self.enabled,
        }