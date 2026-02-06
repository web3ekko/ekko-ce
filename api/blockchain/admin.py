"""
Django Admin Configuration for Blockchain Models
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Chain, SubChain, Blockchain, Category, Dao, Wallet, DaoSubscription,
    WalletSubscription, DaoWallet, Token, Image, Story,
    BlockchainStory, Tag, WalletBalance
)


class TokenInline(admin.TabularInline):
    """Inline admin for tokens belonging to a chain"""
    model = Token
    extra = 0
    fields = ['symbol', 'name', 'decimals', 'is_native', 'contract_address']
    readonly_fields = ['created_at']
    
    def get_queryset(self, request):
        """Order tokens with native first"""
        qs = super().get_queryset(request)
        return qs.order_by('-is_native', 'symbol')


@admin.register(Chain)
class ChainAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'name', 'chain_id', 'native_token_display', 'enabled', 'created_at']
    list_filter = ['enabled', 'created_at']
    search_fields = ['name', 'display_name', 'native_token']
    ordering = ['display_name']
    readonly_fields = ['created_at', 'native_token']
    inlines = [TokenInline]
    
    def native_token_display(self, obj):
        """Display native token with indicator"""
        if obj.native_token:
            native = obj.get_native_token()
            if native:
                return format_html(
                    '<span style="color: green; font-weight: bold;">✓ {}</span>',
                    obj.native_token
                )
            return obj.native_token
        return '-'
    native_token_display.short_description = 'Native Token'


@admin.register(SubChain)
class SubChainAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'chain', 'name', 'network_id', 'is_testnet', 'enabled']
    list_filter = ['chain', 'is_testnet', 'enabled', 'created_at']
    search_fields = ['name', 'display_name', 'chain__name', 'chain__display_name']
    ordering = ['chain__display_name', 'display_name']
    readonly_fields = ['created_at']


@admin.register(Blockchain)
class BlockchainAdmin(admin.ModelAdmin):
    list_display = ['symbol', 'name', 'chain_type', 'created_at']
    list_filter = ['chain_type', 'created_at']
    search_fields = ['name', 'symbol']
    ordering = ['name']


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at']
    search_fields = ['name']
    ordering = ['name']


@admin.register(Dao)
class DaoAdmin(admin.ModelAdmin):
    list_display = ['name', 'recommended', 'created_at']
    list_filter = ['recommended', 'created_at']
    search_fields = ['name', 'description']
    ordering = ['name']


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ['derived_name', 'blockchain', 'address_short', 'status', 'recommended', 'created_at']
    list_filter = ['blockchain', 'status', 'recommended', 'subnet', 'created_at']
    search_fields = ['address', 'name', 'description']
    ordering = ['-created_at']

    def address_short(self, obj):
        return f"{obj.address[:10]}...{obj.address[-6:]}"
    address_short.short_description = 'Address'


@admin.register(Token)
class TokenAdmin(admin.ModelAdmin):
    list_display = ['symbol', 'name', 'chain', 'decimals', 'is_native_display', 'contract_address_short', 'created_at']
    list_filter = ['is_native', 'chain', 'decimals', 'created_at']
    search_fields = ['name', 'symbol', 'contract_address', 'chain__name', 'chain__display_name']
    ordering = ['-is_native', 'chain__name', 'symbol']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Token Information', {
            'fields': ('symbol', 'name', 'decimals')
        }),
        ('Chain & Type', {
            'fields': ('chain', 'is_native', 'contract_address')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def is_native_display(self, obj):
        """Display native token indicator"""
        if obj.is_native:
            return format_html('<span style="color: green; font-weight: bold;">✓ Native</span>')
        return format_html('<span style="color: gray;">Token</span>')
    is_native_display.short_description = 'Type'
    
    def contract_address_short(self, obj):
        """Display shortened contract address"""
        if obj.contract_address:
            return f"{obj.contract_address[:10]}...{obj.contract_address[-6:]}"
        return '-'
    contract_address_short.short_description = 'Contract'


@admin.register(DaoSubscription)
class DaoSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['derived_name', 'user', 'dao', 'notifications_count', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__email', 'dao__name', 'name']
    ordering = ['-created_at']


@admin.register(WalletSubscription)
class WalletSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['derived_name', 'user', 'wallet', 'notifications_count', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__email', 'wallet__address', 'name']
    ordering = ['-created_at']


@admin.register(DaoWallet)
class DaoWalletAdmin(admin.ModelAdmin):
    list_display = ['dao', 'wallet', 'created_at']
    list_filter = ['created_at']
    search_fields = ['dao__name', 'wallet__address']
    ordering = ['-created_at']


@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    list_display = ['title', 'publication_date', 'created_at']
    list_filter = ['publication_date', 'created_at']
    search_fields = ['title', 'description', 'content']
    ordering = ['-publication_date']


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at']
    search_fields = ['name']
    ordering = ['name']


@admin.register(WalletBalance)
class WalletBalanceAdmin(admin.ModelAdmin):
    list_display = ['wallet', 'balance', 'fiat_value', 'timestamp']
    list_filter = ['timestamp']
    search_fields = ['wallet__address']
    ordering = ['-timestamp']
