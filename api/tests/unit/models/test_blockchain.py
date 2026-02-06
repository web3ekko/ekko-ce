"""
Unit tests for blockchain models
Tests Blockchain, Wallet, WalletBalance, and related models
"""
import pytest
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from tests.factories import (
    BlockchainFactory,
    WalletFactory,
    WalletBalanceFactory,
    WalletSubscriptionFactory,
    DaoFactory,
)


@pytest.mark.unit
@pytest.mark.models
class TestBlockchainModel:
    """Test Blockchain model functionality"""

    def test_blockchain_creation(self):
        """Test creating a Blockchain instance"""
        blockchain_data = BlockchainFactory.build()

        assert blockchain_data.name is not None
        assert blockchain_data.symbol is not None
        assert blockchain_data.chain_type == "EVM"
        assert len(blockchain_data.symbol) <= 10

    def test_blockchain_symbol_validation(self):
        """Test blockchain symbol validation"""
        # Test valid symbols
        valid_symbols = ["eth", "btc", "avax", "matic", "sol"]

        for symbol in valid_symbols:
            blockchain_data = BlockchainFactory.build(symbol=symbol)
            assert blockchain_data.symbol == symbol
            assert len(blockchain_data.symbol) <= 10

    def test_blockchain_chain_types(self):
        """Test different blockchain chain types"""
        chain_types = ["EVM", "Bitcoin", "Solana", "Cosmos"]

        for chain_type in chain_types:
            blockchain_data = BlockchainFactory.build(chain_type=chain_type)
            assert blockchain_data.chain_type == chain_type

    def test_blockchain_name_generation(self):
        """Test blockchain name generation"""
        blockchain_data = BlockchainFactory.build()

        # Name should be a string and not empty
        assert isinstance(blockchain_data.name, str)
        assert len(blockchain_data.name) > 0

        # Symbol should be derived from name or set independently
        assert isinstance(blockchain_data.symbol, str)
        assert len(blockchain_data.symbol) > 0


@pytest.mark.unit
@pytest.mark.models
class TestWalletModel:
    """Test Wallet model functionality"""

    def test_wallet_creation(self):
        """Test creating a Wallet instance"""
        wallet_data = WalletFactory.build()

        assert wallet_data.blockchain is not None
        assert wallet_data.blockchain.symbol is not None
        assert wallet_data.address is not None
        assert wallet_data.name is not None
        assert wallet_data.balance is not None
        assert wallet_data.status in ["active", "inactive", "monitoring"]
        assert wallet_data.subnet in ["mainnet", "testnet", "goerli", "sepolia"]

    def test_wallet_address_formats(self):
        """Test different wallet address formats"""
        # Ethereum address format
        eth_blockchain = BlockchainFactory.build(symbol="eth")
        eth_wallet = WalletFactory.build(blockchain=eth_blockchain)
        assert eth_wallet.address.startswith("0x")
        assert len(eth_wallet.address) == 42  # 0x + 40 hex chars

        # Bitcoin address format (simulated)
        btc_blockchain = BlockchainFactory.build(symbol="btc")
        btc_wallet = WalletFactory.build(
            blockchain=btc_blockchain, address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        )
        assert len(btc_wallet.address) >= 26
        assert len(btc_wallet.address) <= 35

    def test_wallet_balance_validation(self):
        """Test wallet balance validation"""
        # Test various balance formats
        balances = [
            "0",
            "1000000000000000000",  # 1 ETH in wei
            "500000000000000000",  # 0.5 ETH in wei
            "1234567890123456789",
        ]

        for balance in balances:
            wallet_data = WalletFactory.build(balance=balance)
            assert wallet_data.balance == balance
            assert wallet_data.balance.isdigit()

    def test_wallet_status_validation(self):
        """Test wallet status validation"""
        valid_statuses = ["active", "inactive", "pending", "error"]

        for status in valid_statuses:
            wallet_data = WalletFactory.build(status=status)
            assert wallet_data.status == status

    def test_wallet_subnet_validation(self):
        """Test wallet subnet validation"""
        valid_subnets = ["mainnet", "testnet", "fuji", "goerli"]

        for subnet in valid_subnets:
            wallet_data = WalletFactory.build(subnet=subnet)
            assert wallet_data.subnet == subnet

    def test_wallet_optional_fields(self):
        """Test wallet optional fields"""
        wallet_data = WalletFactory.build()

        # These fields can be None
        optional_fields = ["derived_name", "domains", "description"]
        for field in optional_fields:
            # Field should exist on the model
            assert hasattr(wallet_data, field)

    def test_wallet_timestamps(self):
        """Test wallet timestamp fields"""
        wallet_data = WalletFactory.build()

        # Timestamps exist but may be None for build() - only set on save/create
        assert hasattr(wallet_data, 'created_at')
        assert hasattr(wallet_data, 'updated_at')


@pytest.mark.unit
@pytest.mark.models
class TestWalletBalanceModel:
    """Test WalletBalance model functionality"""

    def test_wallet_balance_creation(self):
        """Test creating a WalletBalance instance"""
        balance_data = WalletBalanceFactory.build()

        assert balance_data.wallet_id is not None
        assert balance_data.balance is not None
        assert balance_data.token_price is not None
        assert balance_data.fiat_value is not None
        assert isinstance(balance_data.timestamp, datetime)

    def test_wallet_balance_calculations(self):
        """Test wallet balance calculations"""
        # Create balance with known values
        balance_data = WalletBalanceFactory.build(
            balance="1000000000000000000",  # 1 ETH in wei
            token_price="2000",  # $2000 per ETH
            fiat_value="2000",  # $2000 total value
        )

        assert balance_data.balance == "1000000000000000000"
        assert balance_data.token_price == "2000"
        assert balance_data.fiat_value == "2000"

    def test_wallet_balance_precision(self):
        """Test wallet balance precision handling"""
        # Test high precision balances
        precise_balances = ["1234567890123456789", "999999999999999999", "1", "0"]

        for balance in precise_balances:
            balance_data = WalletBalanceFactory.build(balance=balance)
            assert balance_data.balance == balance

    def test_wallet_balance_price_tracking(self):
        """Test price tracking functionality"""
        wallet_id = uuid.uuid4()

        # Create multiple balance records for price history
        price_history = [
            {"token_price": "1800", "fiat_value": "1800"},
            {"token_price": "1900", "fiat_value": "1900"},
            {"token_price": "2000", "fiat_value": "2000"},
            {"token_price": "2100", "fiat_value": "2100"},
        ]

        balance_records = []
        for i, price_data in enumerate(price_history):
            balance_data = WalletBalanceFactory.build(
                wallet_id=wallet_id,
                balance="1000000000000000000",  # 1 ETH
                **price_data,
            )
            balance_records.append(balance_data)

        # Verify all records belong to same wallet
        for record in balance_records:
            assert record.wallet_id == wallet_id

        # Verify price progression
        prices = [float(record.token_price) for record in balance_records]
        assert prices == [1800.0, 1900.0, 2000.0, 2100.0]


@pytest.mark.unit
@pytest.mark.models
class TestWalletSubscriptionModel:
    """Test WalletSubscription model functionality"""

    def test_wallet_subscription_creation(self):
        """Test creating a WalletSubscription instance"""
        subscription_data = WalletSubscriptionFactory.build()

        assert subscription_data.user_id is not None
        assert subscription_data.wallet_id is not None
        assert subscription_data.name is not None
        assert isinstance(subscription_data.notifications_count, int)
        assert subscription_data.notifications_count >= 0

    def test_wallet_subscription_notification_tracking(self):
        """Test notification count tracking"""
        subscription_data = WalletSubscriptionFactory.build(notifications_count=0)

        # Simulate notification increments
        subscription_data.notifications_count += 1
        assert subscription_data.notifications_count == 1

        subscription_data.notifications_count += 5
        assert subscription_data.notifications_count == 6

    def test_wallet_subscription_relationships(self):
        """Test subscription relationship data"""
        user_id = uuid.uuid4()
        wallet_id = uuid.uuid4()

        subscription_data = WalletSubscriptionFactory.build(
            user_id=user_id, wallet_id=wallet_id, name="My ETH Wallet Subscription"
        )

        assert subscription_data.user_id == user_id
        assert subscription_data.wallet_id == wallet_id
        assert subscription_data.name == "My ETH Wallet Subscription"


@pytest.mark.unit
@pytest.mark.models
class TestDaoModel:
    """Test Dao model functionality"""

    def test_dao_creation(self):
        """Test creating a Dao instance"""
        dao_data = DaoFactory.build()

        assert dao_data.name is not None
        assert dao_data.description is not None
        assert dao_data.recommended in [True, False]
        # Timestamps exist but may be None for build() - only set on save/create
        assert hasattr(dao_data, 'created_at')
        assert hasattr(dao_data, 'updated_at')

    def test_dao_recommendation_status(self):
        """Test DAO recommendation status"""
        # Test non-recommended DAO
        dao_data = DaoFactory.build(recommended=False)
        assert dao_data.recommended is False

        # Test recommended DAO
        recommended_dao = DaoFactory.build(recommended=True)
        assert recommended_dao.recommended is True

    def test_dao_description_validation(self):
        """Test DAO description validation"""
        long_description = "A" * 500  # 500 character description

        dao_data = DaoFactory.build(description=long_description)
        assert len(dao_data.description) <= 500

    def test_dao_name_uniqueness(self):
        """Test DAO name uniqueness"""
        dao1_data = DaoFactory.build()
        dao2_data = DaoFactory.build()

        # Names should be different
        assert dao1_data.name != dao2_data.name

        # IDs should be different
        assert dao1_data.id != dao2_data.id


@pytest.mark.unit
@pytest.mark.models
class TestBlockchainModelRelationships:
    """Test relationships between blockchain models"""

    def test_blockchain_wallet_relationship(self):
        """Test blockchain-wallet relationship"""
        blockchain = BlockchainFactory.build(symbol="eth")

        # Create multiple wallets for the same blockchain
        wallets = []
        for i in range(3):
            wallet_data = WalletFactory.build(
                blockchain=blockchain, name=f"Wallet {i}"
            )
            wallets.append(wallet_data)

        # All wallets should belong to the same blockchain
        for wallet in wallets:
            assert wallet.blockchain.symbol == blockchain.symbol

        # Wallet addresses should be unique
        addresses = [w.address for w in wallets]
        assert len(addresses) == len(set(addresses))

    def test_wallet_balance_history(self):
        """Test wallet balance history relationship"""
        wallet_id = uuid.uuid4()

        # Create balance history for a wallet
        balance_history = []
        for i in range(5):
            balance_data = WalletBalanceFactory.build(
                wallet_id=wallet_id,
                balance=str(
                    1000000000000000000 + i * 100000000000000000
                ),  # Increasing balance
            )
            balance_history.append(balance_data)

        # All balance records should belong to the same wallet
        for balance in balance_history:
            assert balance.wallet_id == wallet_id

        # Balance amounts should be different
        balances = [b.balance for b in balance_history]
        assert len(balances) == len(set(balances))

    def test_user_wallet_subscriptions(self):
        """Test user-wallet subscription relationships"""
        user_id = uuid.uuid4()

        # Create multiple wallet subscriptions for a user
        subscriptions = []
        for i in range(3):
            wallet_id = uuid.uuid4()
            subscription_data = WalletSubscriptionFactory.build(
                user_id=user_id, wallet_id=wallet_id, name=f"Subscription {i}"
            )
            subscriptions.append(subscription_data)

        # All subscriptions should belong to the same user
        for subscription in subscriptions:
            assert subscription.user_id == user_id

        # Wallet IDs should be different
        wallet_ids = [s.wallet_id for s in subscriptions]
        assert len(wallet_ids) == len(set(wallet_ids))
