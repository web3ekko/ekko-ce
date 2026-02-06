"""
Tests for the Token model with native token support
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from blockchain.models import Chain, Token


class TokenModelTest(TestCase):
    """Test the Token model functionality"""
    
    def setUp(self):
        """Create test chains"""
        self.ethereum = Chain.objects.create(
            name='ethereum',
            display_name='Ethereum',
            chain_id=1,
            enabled=True
        )
        
        self.polygon = Chain.objects.create(
            name='polygon',
            display_name='Polygon',
            chain_id=137,
            enabled=True
        )
    
    def test_create_native_token(self):
        """Test creating a native token"""
        eth_token = Token.objects.create(
            chain=self.ethereum,
            name='Ethereum',
            symbol='ETH',
            decimals=18,
            is_native=True
        )
        
        self.assertEqual(eth_token.symbol, 'ETH')
        self.assertTrue(eth_token.is_native)
        self.assertIsNone(eth_token.contract_address)
        self.assertEqual(str(eth_token), 'Ethereum (ETH) - Native')
    
    def test_native_token_no_contract_address(self):
        """Test that native tokens cannot have contract address"""
        token = Token(
            chain=self.ethereum,
            name='Ethereum',
            symbol='ETH',
            decimals=18,
            is_native=True,
            contract_address='0x123'  # This should fail
        )
        
        with self.assertRaises(ValidationError) as cm:
            token.clean()
        
        self.assertIn('contract_address', cm.exception.message_dict)
    
    def test_only_one_native_token_per_chain(self):
        """Test that only one native token can exist per chain"""
        # Create first native token
        Token.objects.create(
            chain=self.ethereum,
            name='Ethereum',
            symbol='ETH',
            decimals=18,
            is_native=True
        )
        
        # Try to create second native token
        token2 = Token(
            chain=self.ethereum,
            name='Another Token',
            symbol='ATK',
            decimals=18,
            is_native=True
        )
        
        with self.assertRaises(ValidationError) as cm:
            token2.clean()
        
        self.assertIn('is_native', cm.exception.message_dict)
    
    def test_non_native_token_requires_contract(self):
        """Test that non-native tokens must have contract address"""
        token = Token(
            chain=self.ethereum,
            name='USD Coin',
            symbol='USDC',
            decimals=6,
            is_native=False
            # No contract_address - should fail
        )
        
        with self.assertRaises(ValidationError) as cm:
            token.clean()
        
        self.assertIn('contract_address', cm.exception.message_dict)
    
    def test_create_erc20_token(self):
        """Test creating an ERC20 token"""
        usdc = Token.objects.create(
            chain=self.ethereum,
            name='USD Coin',
            symbol='USDC',
            decimals=6,
            is_native=False,
            contract_address='0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'
        )
        
        self.assertEqual(usdc.symbol, 'USDC')
        self.assertFalse(usdc.is_native)
        self.assertIsNotNone(usdc.contract_address)
        self.assertEqual(str(usdc), 'USD Coin (USDC)')
    
    def test_chain_native_token_property(self):
        """Test Chain.get_native_token() method"""
        # Create native token
        eth_token = Token.objects.create(
            chain=self.ethereum,
            name='Ethereum',
            symbol='ETH',
            decimals=18,
            is_native=True
        )
        
        # Test retrieval
        native = self.ethereum.get_native_token()
        self.assertEqual(native, eth_token)
        self.assertEqual(native.symbol, 'ETH')
        
        # Test chain without native token
        self.assertIsNone(self.polygon.get_native_token())
    
    def test_redis_key_generation(self):
        """Test Redis key generation for tokens"""
        # Native token
        eth_token = Token.objects.create(
            chain=self.ethereum,
            name='Ethereum',
            symbol='ETH',
            decimals=18,
            is_native=True
        )
        
        self.assertEqual(
            eth_token.get_redis_key('mainnet'),
            'native_token:ethereum:mainnet'
        )
        self.assertEqual(
            eth_token.get_redis_key('testnet'),
            'native_token:ethereum:testnet'
        )
        
        # ERC20 token
        usdc = Token.objects.create(
            chain=self.ethereum,
            name='USD Coin',
            symbol='USDC',
            decimals=6,
            is_native=False,
            contract_address='0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'
        )
        
        self.assertEqual(
            usdc.get_redis_key(),
            'token:ethereum:0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'
        )
    
    def test_redis_dict_format(self):
        """Test Redis dictionary format for tokens"""
        eth_token = Token.objects.create(
            chain=self.ethereum,
            name='Ethereum',
            symbol='ETH',
            decimals=18,
            is_native=True
        )
        
        redis_dict = eth_token.to_redis_dict('mainnet')
        
        self.assertEqual(redis_dict['symbol'], 'ETH')
        self.assertEqual(redis_dict['name'], 'Ethereum')
        self.assertEqual(redis_dict['decimals'], 18)
        self.assertTrue(redis_dict['is_native'])
        self.assertIsNone(redis_dict['contract_address'])
        self.assertEqual(redis_dict['chain_name'], 'ethereum')
        self.assertEqual(redis_dict['network'], 'ethereum')
        self.assertEqual(redis_dict['subnet'], 'mainnet')
    
    def test_multiple_tokens_per_chain(self):
        """Test that a chain can have multiple tokens (1 native + many ERC20)"""
        # Native token
        eth = Token.objects.create(
            chain=self.ethereum,
            name='Ethereum',
            symbol='ETH',
            decimals=18,
            is_native=True
        )
        
        # ERC20 tokens
        usdc = Token.objects.create(
            chain=self.ethereum,
            name='USD Coin',
            symbol='USDC',
            decimals=6,
            is_native=False,
            contract_address='0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'
        )
        
        usdt = Token.objects.create(
            chain=self.ethereum,
            name='Tether',
            symbol='USDT',
            decimals=6,
            is_native=False,
            contract_address='0xdAC17F958D2ee523a2206206994597C13D831ec7'
        )
        
        # Check chain has all tokens
        chain_tokens = self.ethereum.tokens.all()
        self.assertEqual(chain_tokens.count(), 3)
        self.assertIn(eth, chain_tokens)
        self.assertIn(usdc, chain_tokens)
        self.assertIn(usdt, chain_tokens)
        
        # Check only one is native
        native_tokens = chain_tokens.filter(is_native=True)
        self.assertEqual(native_tokens.count(), 1)
        self.assertEqual(native_tokens.first(), eth)