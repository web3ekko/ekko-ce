"""Tests for Wallet model and WalletRepository."""

import pytest
import uuid
from datetime import datetime

from app.models import Wallet
from app.repositories import WalletRepository


class TestWalletModel:
    """Test Wallet model validation."""
    
    def test_wallet_model_creation(self):
        """Test creating a Wallet model with valid data."""
        wallet_data = {
            "id": str(uuid.uuid4()),
            "blockchain_symbol": "ETH",
            "address": "0x1234567890abcdef1234567890abcdef12345678",
            "name": "Test Wallet",
            "balance": 1.5,
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "updated_at": None
        }
        
        wallet = Wallet(**wallet_data)
        
        assert wallet.id == wallet_data["id"]
        assert wallet.blockchain_symbol == wallet_data["blockchain_symbol"]
        assert wallet.address == wallet_data["address"]
        assert wallet.name == wallet_data["name"]
        assert wallet.balance == wallet_data["balance"]
        assert wallet.status == wallet_data["status"]
    
    def test_wallet_model_default_values(self):
        """Test Wallet model default values."""
        wallet_data = {
            "id": str(uuid.uuid4()),
            "blockchain_symbol": "ETH",
            "address": "0x1234567890abcdef1234567890abcdef12345678",
            "name": "Test Wallet"
        }
        
        wallet = Wallet(**wallet_data)
        
        assert wallet.balance == 0.0  # Default balance
        assert wallet.status == "active"  # Default status
    
    def test_wallet_model_required_fields(self):
        """Test Wallet model with missing required fields."""
        with pytest.raises(ValueError):
            Wallet(id=str(uuid.uuid4()))  # Missing required fields


class TestWalletRepository:
    """Test WalletRepository CRUD operations."""
    
    @pytest.mark.asyncio
    async def test_create_wallet(self, wallet_repository: WalletRepository):
        """Test creating a new wallet."""
        wallet_data = Wallet(
            id=str(uuid.uuid4()),
            blockchain_symbol="ETH",
            address="0x1234567890abcdef1234567890abcdef12345678",
            name="Test Wallet",
            balance=1.5,
            status="active",
            created_at=datetime.now().isoformat()
        )
        
        created_wallet = await wallet_repository.create(wallet_data)
        
        assert created_wallet.id == wallet_data.id
        assert created_wallet.blockchain_symbol == wallet_data.blockchain_symbol
        assert created_wallet.address == wallet_data.address
        assert created_wallet.name == wallet_data.name
        assert created_wallet.balance == wallet_data.balance
    
    @pytest.mark.asyncio
    async def test_get_wallet_by_id(self, wallet_repository: WalletRepository):
        """Test retrieving a wallet by ID."""
        wallet_data = Wallet(
            id=str(uuid.uuid4()),
            blockchain_symbol="ETH",
            address="0x1234567890abcdef1234567890abcdef12345678",
            name="Test Wallet",
            balance=1.5,
            status="active",
            created_at=datetime.now().isoformat()
        )
        
        created_wallet = await wallet_repository.create(wallet_data)
        
        # Retrieve the wallet
        retrieved_wallet = await wallet_repository.get_by_id(created_wallet.id)
        
        assert retrieved_wallet is not None
        assert retrieved_wallet.id == created_wallet.id
        assert retrieved_wallet.address == created_wallet.address
    
    @pytest.mark.asyncio
    async def test_get_wallet_by_address(self, wallet_repository: WalletRepository):
        """Test retrieving a wallet by blockchain and address."""
        wallet_data = Wallet(
            id=str(uuid.uuid4()),
            blockchain_symbol="ETH",
            address="0x1234567890abcdef1234567890abcdef12345678",
            name="Test Wallet",
            balance=1.5,
            status="active",
            created_at=datetime.now().isoformat()
        )
        
        created_wallet = await wallet_repository.create(wallet_data)
        
        # Retrieve by address
        retrieved_wallet = await wallet_repository.get_by_address(
            created_wallet.blockchain_symbol, 
            created_wallet.address
        )
        
        assert retrieved_wallet is not None
        assert retrieved_wallet.id == created_wallet.id
        assert retrieved_wallet.address == created_wallet.address
    
    @pytest.mark.asyncio
    async def test_update_wallet(self, wallet_repository: WalletRepository):
        """Test updating a wallet."""
        wallet_data = Wallet(
            id=str(uuid.uuid4()),
            blockchain_symbol="ETH",
            address="0x1234567890abcdef1234567890abcdef12345678",
            name="Test Wallet",
            balance=1.5,
            status="active",
            created_at=datetime.now().isoformat()
        )
        
        created_wallet = await wallet_repository.create(wallet_data)
        
        # Update the wallet
        updates = {
            "name": "Updated Test Wallet",
            "balance": 2.5
        }
        
        updated_wallet = await wallet_repository.update(created_wallet.id, updates)
        
        assert updated_wallet is not None
        assert updated_wallet.name == "Updated Test Wallet"
        assert updated_wallet.balance == 2.5
        assert updated_wallet.address == created_wallet.address  # Unchanged
    
    @pytest.mark.asyncio
    async def test_update_balance(self, wallet_repository: WalletRepository):
        """Test updating wallet balance specifically."""
        wallet_data = Wallet(
            id=str(uuid.uuid4()),
            blockchain_symbol="ETH",
            address="0x1234567890abcdef1234567890abcdef12345678",
            name="Test Wallet",
            balance=1.0,
            status="active",
            created_at=datetime.now().isoformat()
        )
        
        created_wallet = await wallet_repository.create(wallet_data)
        
        # Update balance
        updated_wallet = await wallet_repository.update_balance(created_wallet.id, 5.0)
        
        assert updated_wallet is not None
        assert updated_wallet.balance == 5.0
    
    @pytest.mark.asyncio
    async def test_delete_wallet(self, wallet_repository: WalletRepository):
        """Test deleting a wallet."""
        wallet_data = Wallet(
            id=str(uuid.uuid4()),
            blockchain_symbol="ETH",
            address="0x1234567890abcdef1234567890abcdef12345678",
            name="Test Wallet",
            balance=1.5,
            status="active",
            created_at=datetime.now().isoformat()
        )
        
        created_wallet = await wallet_repository.create(wallet_data)
        
        # Delete the wallet
        deleted = await wallet_repository.delete(created_wallet.id)
        
        assert deleted is True
        
        # Verify wallet is deleted
        retrieved_wallet = await wallet_repository.get_by_id(created_wallet.id)
        assert retrieved_wallet is None
    
    @pytest.mark.asyncio
    async def test_list_wallets(self, wallet_repository: WalletRepository):
        """Test listing wallets."""
        # Create multiple wallets
        wallets_data = []
        for i in range(3):
            wallet_data = Wallet(
                id=str(uuid.uuid4()),
                blockchain_symbol="ETH",
                address=f"0x{uuid.uuid4().hex[:40]}",
                name=f"Test Wallet {i}",
                balance=float(i + 1),
                status="active",
                created_at=datetime.now().isoformat()
            )
            wallets_data.append(await wallet_repository.create(wallet_data))
        
        # List all wallets
        all_wallets = await wallet_repository.list()
        
        assert len(all_wallets) >= 3
        
        # Check that our created wallets are in the list
        created_ids = {wallet.id for wallet in wallets_data}
        retrieved_ids = {wallet.id for wallet in all_wallets}
        
        assert created_ids.issubset(retrieved_ids)
    
    @pytest.mark.asyncio
    async def test_list_wallets_by_blockchain(self, wallet_repository: WalletRepository):
        """Test listing wallets by blockchain."""
        # Create wallets for different blockchains
        eth_wallet = Wallet(
            id=str(uuid.uuid4()),
            blockchain_symbol="ETH",
            address="0x1234567890abcdef1234567890abcdef12345678",
            name="ETH Wallet",
            balance=1.0,
            status="active",
            created_at=datetime.now().isoformat()
        )
        
        btc_wallet = Wallet(
            id=str(uuid.uuid4()),
            blockchain_symbol="BTC",
            address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            name="BTC Wallet",
            balance=0.5,
            status="active",
            created_at=datetime.now().isoformat()
        )
        
        await wallet_repository.create(eth_wallet)
        await wallet_repository.create(btc_wallet)
        
        # Get ETH wallets only
        eth_wallets = await wallet_repository.get_by_blockchain("ETH")
        
        assert len(eth_wallets) >= 1
        assert all(wallet.blockchain_symbol == "ETH" for wallet in eth_wallets)
    
    @pytest.mark.asyncio
    async def test_get_active_wallets(self, wallet_repository: WalletRepository):
        """Test getting active wallets."""
        # Create active and inactive wallets
        active_wallet = Wallet(
            id=str(uuid.uuid4()),
            blockchain_symbol="ETH",
            address="0x1234567890abcdef1234567890abcdef12345678",
            name="Active Wallet",
            balance=1.0,
            status="active",
            created_at=datetime.now().isoformat()
        )
        
        inactive_wallet = Wallet(
            id=str(uuid.uuid4()),
            blockchain_symbol="ETH",
            address="0xabcdef1234567890abcdef1234567890abcdef12",
            name="Inactive Wallet",
            balance=1.0,
            status="inactive",
            created_at=datetime.now().isoformat()
        )
        
        await wallet_repository.create(active_wallet)
        await wallet_repository.create(inactive_wallet)
        
        # Get active wallets only
        active_wallets = await wallet_repository.get_active_wallets()
        
        assert len(active_wallets) >= 1
        assert all(wallet.status == "active" for wallet in active_wallets)
    
    @pytest.mark.asyncio
    async def test_address_exists(self, wallet_repository: WalletRepository):
        """Test checking if address exists."""
        wallet_data = Wallet(
            id=str(uuid.uuid4()),
            blockchain_symbol="ETH",
            address="0x1234567890abcdef1234567890abcdef12345678",
            name="Test Wallet",
            balance=1.0,
            status="active",
            created_at=datetime.now().isoformat()
        )
        
        await wallet_repository.create(wallet_data)
        
        # Check existing address
        exists = await wallet_repository.address_exists("ETH", "0x1234567890abcdef1234567890abcdef12345678")
        assert exists is True
        
        # Check non-existing address
        not_exists = await wallet_repository.address_exists("ETH", "0xnonexistent1234567890abcdef1234567890ab")
        assert not_exists is False
    
    @pytest.mark.asyncio
    async def test_search_wallets(self, wallet_repository: WalletRepository):
        """Test searching wallets by name or address."""
        wallet_data = Wallet(
            id=str(uuid.uuid4()),
            blockchain_symbol="ETH",
            address="0x1234567890abcdef1234567890abcdef12345678",
            name="Searchable Wallet",
            balance=1.0,
            status="active",
            created_at=datetime.now().isoformat()
        )
        
        await wallet_repository.create(wallet_data)
        
        # Search by name
        results = await wallet_repository.search_wallets("Searchable")
        assert len(results) >= 1
        assert any(wallet.name == "Searchable Wallet" for wallet in results)
        
        # Search by address
        results = await wallet_repository.search_wallets("1234567890")
        assert len(results) >= 1
        assert any("1234567890" in wallet.address for wallet in results)
    
    @pytest.mark.asyncio
    async def test_get_wallet_stats(self, wallet_repository: WalletRepository):
        """Test getting wallet statistics."""
        # Create some test wallets
        for i in range(2):
            wallet_data = Wallet(
                id=str(uuid.uuid4()),
                blockchain_symbol="ETH" if i == 0 else "BTC",
                address=f"0x{uuid.uuid4().hex[:40]}" if i == 0 else f"1{uuid.uuid4().hex[:33]}",
                name=f"Test Wallet {i}",
                balance=float(i + 1),
                status="active",
                created_at=datetime.now().isoformat()
            )
            await wallet_repository.create(wallet_data)
        
        stats = await wallet_repository.get_wallet_stats()
        
        assert "total_wallets" in stats
        assert "active_wallets" in stats
        assert "wallets_by_blockchain" in stats
        assert "total_balance_by_blockchain" in stats
        assert stats["total_wallets"] >= 2
        assert stats["active_wallets"] >= 2
