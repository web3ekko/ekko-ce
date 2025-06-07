"""Tests for WalletBalance model and WalletBalanceRepository."""

import pytest
import uuid
from datetime import datetime, timedelta

from app.models import WalletBalance
from app.repositories import WalletBalanceRepository


class TestWalletBalanceModel:
    """Test WalletBalance model validation."""
    
    def test_wallet_balance_model_creation(self):
        """Test creating a WalletBalance model with valid data."""
        balance_data = {
            "id": str(uuid.uuid4()),
            "wallet_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "balance": 1.5,
            "token_price": 2000.0,
            "fiat_value": 3000.0
        }
        
        wallet_balance = WalletBalance(**balance_data)
        
        assert wallet_balance.id == balance_data["id"]
        assert wallet_balance.wallet_id == balance_data["wallet_id"]
        assert wallet_balance.timestamp == balance_data["timestamp"]
        assert wallet_balance.balance == balance_data["balance"]
        assert wallet_balance.token_price == balance_data["token_price"]
        assert wallet_balance.fiat_value == balance_data["fiat_value"]
    
    def test_wallet_balance_model_optional_fields(self):
        """Test WalletBalance model with optional fields."""
        balance_data = {
            "id": str(uuid.uuid4()),
            "wallet_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "balance": 1.5
        }
        
        wallet_balance = WalletBalance(**balance_data)
        
        assert wallet_balance.token_price is None  # Optional field
        assert wallet_balance.fiat_value is None  # Optional field
    
    def test_wallet_balance_model_required_fields(self):
        """Test WalletBalance model with missing required fields."""
        with pytest.raises(ValueError):
            WalletBalance(id=str(uuid.uuid4()))  # Missing required fields


class TestWalletBalanceRepository:
    """Test WalletBalanceRepository CRUD operations."""
    
    @pytest.mark.asyncio
    async def test_create_wallet_balance(self, wallet_balance_repository: WalletBalanceRepository):
        """Test creating a new wallet balance record."""
        balance_data = WalletBalance(
            id=str(uuid.uuid4()),
            wallet_id=str(uuid.uuid4()),
            timestamp=datetime.now().isoformat(),
            balance=1.5,
            token_price=2000.0,
            fiat_value=3000.0
        )
        
        created_balance = await wallet_balance_repository.create(balance_data)
        
        assert created_balance.id == balance_data.id
        assert created_balance.wallet_id == balance_data.wallet_id
        assert created_balance.balance == balance_data.balance
        assert created_balance.token_price == balance_data.token_price
        assert created_balance.fiat_value == balance_data.fiat_value
    
    @pytest.mark.asyncio
    async def test_get_balance_by_id(self, wallet_balance_repository: WalletBalanceRepository):
        """Test retrieving a balance record by ID."""
        balance_data = WalletBalance(
            id=str(uuid.uuid4()),
            wallet_id=str(uuid.uuid4()),
            timestamp=datetime.now().isoformat(),
            balance=1.5,
            token_price=2000.0,
            fiat_value=3000.0
        )
        
        created_balance = await wallet_balance_repository.create(balance_data)
        
        # Retrieve the balance
        retrieved_balance = await wallet_balance_repository.get_by_id(created_balance.id)
        
        assert retrieved_balance is not None
        assert retrieved_balance.id == created_balance.id
        assert retrieved_balance.wallet_id == created_balance.wallet_id
    
    @pytest.mark.asyncio
    async def test_get_balances_by_wallet_id(self, wallet_balance_repository: WalletBalanceRepository):
        """Test retrieving balance history for a specific wallet."""
        wallet_id = str(uuid.uuid4())
        
        # Create multiple balance records for the wallet
        balance_records = []
        for i in range(3):
            balance_data = WalletBalance(
                id=str(uuid.uuid4()),
                wallet_id=wallet_id,
                timestamp=(datetime.now() - timedelta(hours=i)).isoformat(),
                balance=float(i + 1),
                token_price=2000.0,
                fiat_value=float((i + 1) * 2000)
            )
            balance_records.append(await wallet_balance_repository.create(balance_data))
        
        # Get balance history
        wallet_balances = await wallet_balance_repository.get_by_wallet_id(wallet_id)
        
        assert len(wallet_balances) == 3
        assert all(balance.wallet_id == wallet_id for balance in wallet_balances)
        
        # Should be ordered by timestamp DESC (most recent first)
        timestamps = [balance.timestamp for balance in wallet_balances]
        assert timestamps == sorted(timestamps, reverse=True)
    
    @pytest.mark.asyncio
    async def test_get_latest_balance(self, wallet_balance_repository: WalletBalanceRepository):
        """Test getting the most recent balance for a wallet."""
        wallet_id = str(uuid.uuid4())
        
        # Create balance records with different timestamps
        older_balance = WalletBalance(
            id=str(uuid.uuid4()),
            wallet_id=wallet_id,
            timestamp=(datetime.now() - timedelta(hours=2)).isoformat(),
            balance=1.0,
            token_price=2000.0,
            fiat_value=2000.0
        )
        
        newer_balance = WalletBalance(
            id=str(uuid.uuid4()),
            wallet_id=wallet_id,
            timestamp=datetime.now().isoformat(),
            balance=2.0,
            token_price=2100.0,
            fiat_value=4200.0
        )
        
        await wallet_balance_repository.create(older_balance)
        await wallet_balance_repository.create(newer_balance)
        
        # Get latest balance
        latest_balance = await wallet_balance_repository.get_latest_balance(wallet_id)
        
        assert latest_balance is not None
        assert latest_balance.id == newer_balance.id
        assert latest_balance.balance == 2.0
    
    @pytest.mark.asyncio
    async def test_get_balance_at_time(self, wallet_balance_repository: WalletBalanceRepository):
        """Test getting balance closest to a specific timestamp."""
        wallet_id = str(uuid.uuid4())
        
        # Create balance records at different times
        base_time = datetime.now()
        
        balance1 = WalletBalance(
            id=str(uuid.uuid4()),
            wallet_id=wallet_id,
            timestamp=(base_time - timedelta(hours=3)).isoformat(),
            balance=1.0
        )
        
        balance2 = WalletBalance(
            id=str(uuid.uuid4()),
            wallet_id=wallet_id,
            timestamp=(base_time - timedelta(hours=1)).isoformat(),
            balance=2.0
        )
        
        await wallet_balance_repository.create(balance1)
        await wallet_balance_repository.create(balance2)
        
        # Get balance at a time between the two records
        target_time = (base_time - timedelta(minutes=30)).isoformat()
        balance_at_time = await wallet_balance_repository.get_balance_at_time(wallet_id, target_time)
        
        assert balance_at_time is not None
        assert balance_at_time.id == balance2.id  # Should get the most recent before target time
    
    @pytest.mark.asyncio
    async def test_get_balance_history(self, wallet_balance_repository: WalletBalanceRepository):
        """Test getting balance history within a time range."""
        wallet_id = str(uuid.uuid4())
        base_time = datetime.now()
        
        # Create balance records spanning different time periods
        balances = []
        for i in range(5):
            balance_data = WalletBalance(
                id=str(uuid.uuid4()),
                wallet_id=wallet_id,
                timestamp=(base_time - timedelta(hours=i)).isoformat(),
                balance=float(i + 1)
            )
            balances.append(await wallet_balance_repository.create(balance_data))
        
        # Get balance history for last 3 hours
        start_time = (base_time - timedelta(hours=3)).isoformat()
        end_time = base_time.isoformat()
        
        history = await wallet_balance_repository.get_balance_history(wallet_id, start_time, end_time)
        
        assert len(history) == 4  # Should include records from 0, 1, 2, 3 hours ago
        
        # Should be ordered by timestamp ASC
        timestamps = [balance.timestamp for balance in history]
        assert timestamps == sorted(timestamps)
    
    @pytest.mark.asyncio
    async def test_get_balance_changes(self, wallet_balance_repository: WalletBalanceRepository):
        """Test getting balance changes over time."""
        wallet_id = str(uuid.uuid4())
        base_time = datetime.now()
        
        # Create balance records with increasing values
        balances = [1.0, 1.5, 2.0, 1.8]  # Last one is a decrease
        for i, balance_value in enumerate(balances):
            balance_data = WalletBalance(
                id=str(uuid.uuid4()),
                wallet_id=wallet_id,
                timestamp=(base_time - timedelta(hours=len(balances) - i - 1)).isoformat(),
                balance=balance_value
            )
            await wallet_balance_repository.create(balance_data)
        
        # Get balance changes for last 24 hours
        changes = await wallet_balance_repository.get_balance_changes(wallet_id, hours=24)
        
        assert len(changes) == 3  # Should have 3 changes (excluding first record)
        
        # Check the changes are calculated correctly
        assert changes[0]["change"] == 0.5  # 1.5 - 1.0
        assert changes[1]["change"] == 0.5  # 2.0 - 1.5
        assert changes[2]["change"] == -0.2  # 1.8 - 2.0
    
    @pytest.mark.asyncio
    async def test_get_wallet_performance(self, wallet_balance_repository: WalletBalanceRepository):
        """Test getting wallet performance metrics."""
        wallet_id = str(uuid.uuid4())
        base_time = datetime.now()
        
        # Create balance records over time
        balances = [1.0, 1.5, 2.0, 1.8, 2.2]
        for i, balance_value in enumerate(balances):
            balance_data = WalletBalance(
                id=str(uuid.uuid4()),
                wallet_id=wallet_id,
                timestamp=(base_time - timedelta(days=len(balances) - i - 1)).isoformat(),
                balance=balance_value
            )
            await wallet_balance_repository.create(balance_data)
        
        # Get performance metrics for last 30 days
        performance = await wallet_balance_repository.get_wallet_performance(wallet_id, days=30)
        
        assert performance["wallet_id"] == wallet_id
        assert performance["period_days"] == 30
        assert performance["min_balance"] == 1.0
        assert performance["max_balance"] == 2.2
        assert performance["data_points"] == 5
        
        # Check percentage change calculation
        if performance["percentage_change"] is not None:
            # Should be positive since we went from 1.0 to 2.2
            assert performance["percentage_change"] > 0
    
    @pytest.mark.asyncio
    async def test_delete_wallet_balance(self, wallet_balance_repository: WalletBalanceRepository):
        """Test deleting a wallet balance record."""
        balance_data = WalletBalance(
            id=str(uuid.uuid4()),
            wallet_id=str(uuid.uuid4()),
            timestamp=datetime.now().isoformat(),
            balance=1.5
        )
        
        created_balance = await wallet_balance_repository.create(balance_data)
        
        # Delete the balance record
        deleted = await wallet_balance_repository.delete(created_balance.id)
        
        assert deleted is True
        
        # Verify balance record is deleted
        retrieved_balance = await wallet_balance_repository.get_by_id(created_balance.id)
        assert retrieved_balance is None
    
    @pytest.mark.asyncio
    async def test_cleanup_old_balances(self, wallet_balance_repository: WalletBalanceRepository):
        """Test cleaning up old balance records."""
        wallet_id = str(uuid.uuid4())
        base_time = datetime.now()
        
        # Create old and recent balance records
        old_balance = WalletBalance(
            id=str(uuid.uuid4()),
            wallet_id=wallet_id,
            timestamp=(base_time - timedelta(days=100)).isoformat(),
            balance=1.0
        )
        
        recent_balance = WalletBalance(
            id=str(uuid.uuid4()),
            wallet_id=wallet_id,
            timestamp=(base_time - timedelta(days=10)).isoformat(),
            balance=2.0
        )
        
        await wallet_balance_repository.create(old_balance)
        await wallet_balance_repository.create(recent_balance)
        
        # Cleanup records older than 90 days
        deleted_count = await wallet_balance_repository.cleanup_old_balances(wallet_id, keep_days=90)
        
        assert deleted_count == 1  # Should delete the old record
        
        # Verify old record is deleted and recent record remains
        old_retrieved = await wallet_balance_repository.get_by_id(old_balance.id)
        recent_retrieved = await wallet_balance_repository.get_by_id(recent_balance.id)
        
        assert old_retrieved is None
        assert recent_retrieved is not None
    
    @pytest.mark.asyncio
    async def test_get_balance_stats(self, wallet_balance_repository: WalletBalanceRepository):
        """Test getting balance statistics."""
        # Create some test balance records
        for i in range(2):
            wallet_id = str(uuid.uuid4())
            balance_data = WalletBalance(
                id=str(uuid.uuid4()),
                wallet_id=wallet_id,
                timestamp=datetime.now().isoformat(),
                balance=float(i + 1)
            )
            await wallet_balance_repository.create(balance_data)
        
        stats = await wallet_balance_repository.get_balance_stats()
        
        assert "total_balance_records" in stats
        assert "wallets_with_balance_data" in stats
        assert "recent_balance_updates" in stats
        assert "top_wallets_by_avg_balance" in stats
        assert stats["total_balance_records"] >= 2
        assert stats["wallets_with_balance_data"] >= 2
