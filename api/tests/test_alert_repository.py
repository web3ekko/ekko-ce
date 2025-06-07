"""Tests for Alert model and AlertRepository."""

import pytest
import uuid
from datetime import datetime

from app.models import Alert
from app.repositories import AlertRepository


class TestAlertModel:
    """Test Alert model validation."""
    
    def test_alert_model_creation(self):
        """Test creating an Alert model with valid data."""
        alert_data = {
            "id": str(uuid.uuid4()),
            "type": "transaction",
            "message": "Test alert message",
            "time": datetime.now().isoformat(),
            "status": "new",
            "icon": "warning",
            "priority": "high",
            "related_wallet_id": str(uuid.uuid4()),
            "query": "SELECT * FROM transactions",
            "job_spec": {"interval": 60, "condition": "balance > 1.0"}
        }
        
        alert = Alert(**alert_data)
        
        assert alert.id == alert_data["id"]
        assert alert.type == alert_data["type"]
        assert alert.message == alert_data["message"]
        assert alert.status == alert_data["status"]
        assert alert.priority == alert_data["priority"]
        assert alert.job_spec == alert_data["job_spec"]
    
    def test_alert_model_default_values(self):
        """Test Alert model default values."""
        alert_data = {
            "id": str(uuid.uuid4()),
            "type": "transaction",
            "message": "Test alert message",
            "time": datetime.now().isoformat(),
            "status": "new"
        }

        alert = Alert(**alert_data)

        assert alert.icon is None  # Optional field
        assert alert.priority is None  # Optional field
        assert alert.related_wallet_id is None  # Optional field
        assert alert.query is None  # Optional field
        assert alert.job_spec is None  # Optional field
    
    def test_alert_model_required_fields(self):
        """Test Alert model with missing required fields."""
        with pytest.raises(ValueError):
            Alert(id=str(uuid.uuid4()))  # Missing required fields


class TestAlertRepository:
    """Test AlertRepository CRUD operations."""
    
    @pytest.mark.asyncio
    async def test_create_alert(self, alert_repository: AlertRepository):
        """Test creating a new alert."""
        alert_data = Alert(
            id=str(uuid.uuid4()),
            type="transaction",
            message="Test alert message",
            time=datetime.now().isoformat(),
            status="new",
            icon="warning",
            priority="high",
            related_wallet_id=str(uuid.uuid4())
        )
        
        created_alert = await alert_repository.create(alert_data)
        
        assert created_alert.id == alert_data.id
        assert created_alert.type == alert_data.type
        assert created_alert.message == alert_data.message
        assert created_alert.status == alert_data.status
        assert created_alert.priority == alert_data.priority
    
    @pytest.mark.asyncio
    async def test_create_alert_with_job_spec(self, alert_repository: AlertRepository):
        """Test creating an alert with job specification."""
        job_spec = {
            "interval": 60,
            "condition": "balance > 1.0",
            "action": "send_notification"
        }
        
        alert_data = Alert(
            id=str(uuid.uuid4()),
            type="balance",
            message="Balance alert",
            time=datetime.now().isoformat(),
            status="active",
            job_spec=job_spec,
            notifications_enabled=True
        )
        
        created_alert = await alert_repository.create(alert_data)
        
        assert created_alert.job_spec == job_spec
        assert isinstance(created_alert.job_spec, dict)
    
    @pytest.mark.asyncio
    async def test_get_alert_by_id(self, alert_repository: AlertRepository):
        """Test retrieving an alert by ID."""
        alert_data = Alert(
            id=str(uuid.uuid4()),
            type="transaction",
            message="Test alert message",
            time=datetime.now().isoformat(),
            status="new",
            notifications_enabled=True
        )
        
        created_alert = await alert_repository.create(alert_data)
        
        # Retrieve the alert
        retrieved_alert = await alert_repository.get_by_id(created_alert.id)
        
        assert retrieved_alert is not None
        assert retrieved_alert.id == created_alert.id
        assert retrieved_alert.message == created_alert.message
    
    @pytest.mark.asyncio
    async def test_update_alert(self, alert_repository: AlertRepository):
        """Test updating an alert."""
        alert_data = Alert(
            id=str(uuid.uuid4()),
            type="transaction",
            message="Test alert message",
            time=datetime.now().isoformat(),
            status="new",
            notifications_enabled=True
        )
        
        created_alert = await alert_repository.create(alert_data)
        
        # Update the alert
        updates = {
            "status": "resolved",
            "priority": "low"
        }
        
        updated_alert = await alert_repository.update(created_alert.id, updates)
        
        assert updated_alert is not None
        assert updated_alert.status == "resolved"
        assert updated_alert.priority == "low"
        assert updated_alert.message == created_alert.message  # Unchanged
    
    @pytest.mark.asyncio
    async def test_update_status(self, alert_repository: AlertRepository):
        """Test updating alert status specifically."""
        alert_data = Alert(
            id=str(uuid.uuid4()),
            type="transaction",
            message="Test alert message",
            time=datetime.now().isoformat(),
            status="new",
            notifications_enabled=True
        )
        
        created_alert = await alert_repository.create(alert_data)
        
        # Update status
        updated_alert = await alert_repository.update_status(created_alert.id, "acknowledged")
        
        assert updated_alert is not None
        assert updated_alert.status == "acknowledged"
    
    @pytest.mark.asyncio
    async def test_delete_alert(self, alert_repository: AlertRepository):
        """Test deleting an alert."""
        alert_data = Alert(
            id=str(uuid.uuid4()),
            type="transaction",
            message="Test alert message",
            time=datetime.now().isoformat(),
            status="new",
            notifications_enabled=True
        )
        
        created_alert = await alert_repository.create(alert_data)
        
        # Delete the alert
        deleted = await alert_repository.delete(created_alert.id)
        
        assert deleted is True
        
        # Verify alert is deleted
        retrieved_alert = await alert_repository.get_by_id(created_alert.id)
        assert retrieved_alert is None
    
    @pytest.mark.asyncio
    async def test_get_alerts_by_wallet_id(self, alert_repository: AlertRepository):
        """Test getting alerts for a specific wallet."""
        wallet_id = str(uuid.uuid4())
        
        # Create alerts for the wallet
        for i in range(2):
            alert_data = Alert(
                id=str(uuid.uuid4()),
                type="transaction",
                message=f"Test alert {i}",
                time=datetime.now().isoformat(),
                status="new",
                related_wallet_id=wallet_id,
                notifications_enabled=True
            )
            await alert_repository.create(alert_data)
        
        # Create alert for different wallet
        other_alert = Alert(
            id=str(uuid.uuid4()),
            type="transaction",
            message="Other wallet alert",
            time=datetime.now().isoformat(),
            status="new",
            related_wallet_id=str(uuid.uuid4()),
            notifications_enabled=True
        )
        await alert_repository.create(other_alert)
        
        # Get alerts for specific wallet
        wallet_alerts = await alert_repository.get_by_wallet_id(wallet_id)
        
        assert len(wallet_alerts) == 2
        assert all(alert.related_wallet_id == wallet_id for alert in wallet_alerts)
    
    @pytest.mark.asyncio
    async def test_get_alerts_by_status(self, alert_repository: AlertRepository):
        """Test getting alerts by status."""
        # Create alerts with different statuses
        new_alert = Alert(
            id=str(uuid.uuid4()),
            type="transaction",
            message="New alert",
            time=datetime.now().isoformat(),
            status="new",
            notifications_enabled=True
        )
        
        resolved_alert = Alert(
            id=str(uuid.uuid4()),
            type="transaction",
            message="Resolved alert",
            time=datetime.now().isoformat(),
            status="resolved",
            notifications_enabled=True
        )
        
        await alert_repository.create(new_alert)
        await alert_repository.create(resolved_alert)
        
        # Get new alerts only
        new_alerts = await alert_repository.get_by_status("new")
        
        assert len(new_alerts) >= 1
        assert all(alert.status == "new" for alert in new_alerts)
    
    @pytest.mark.asyncio
    async def test_get_alerts_by_type(self, alert_repository: AlertRepository):
        """Test getting alerts by type."""
        # Create alerts with different types
        transaction_alert = Alert(
            id=str(uuid.uuid4()),
            type="transaction",
            message="Transaction alert",
            time=datetime.now().isoformat(),
            status="new",
            notifications_enabled=True
        )
        
        balance_alert = Alert(
            id=str(uuid.uuid4()),
            type="balance",
            message="Balance alert",
            time=datetime.now().isoformat(),
            status="new",
            notifications_enabled=True
        )
        
        await alert_repository.create(transaction_alert)
        await alert_repository.create(balance_alert)
        
        # Get transaction alerts only
        transaction_alerts = await alert_repository.get_by_type("transaction")
        
        assert len(transaction_alerts) >= 1
        assert all(alert.type == "transaction" for alert in transaction_alerts)
    
    @pytest.mark.asyncio
    async def test_search_alerts(self, alert_repository: AlertRepository):
        """Test searching alerts by message or type."""
        alert_data = Alert(
            id=str(uuid.uuid4()),
            type="transaction",
            message="Searchable alert message",
            time=datetime.now().isoformat(),
            status="new",
            notifications_enabled=True
        )
        
        await alert_repository.create(alert_data)
        
        # Search by message
        results = await alert_repository.search_alerts("Searchable")
        assert len(results) >= 1
        assert any("Searchable" in alert.message for alert in results)
        
        # Search by type
        results = await alert_repository.search_alerts("transaction")
        assert len(results) >= 1
        assert any(alert.type == "transaction" for alert in results)
    
    @pytest.mark.asyncio
    async def test_get_alerts_by_priority(self, alert_repository: AlertRepository):
        """Test getting alerts by priority."""
        # Create alerts with different priorities
        high_alert = Alert(
            id=str(uuid.uuid4()),
            type="transaction",
            message="High priority alert",
            time=datetime.now().isoformat(),
            status="new",
            priority="high"
        )

        low_alert = Alert(
            id=str(uuid.uuid4()),
            type="transaction",
            message="Low priority alert",
            time=datetime.now().isoformat(),
            status="new",
            priority="low"
        )

        await alert_repository.create(high_alert)
        await alert_repository.create(low_alert)

        # Get high priority alerts
        high_alerts = await alert_repository.get_by_priority("high")

        assert len(high_alerts) >= 1
        assert all(alert.priority == "high" for alert in high_alerts)
    
    @pytest.mark.asyncio
    async def test_bulk_update_status(self, alert_repository: AlertRepository):
        """Test bulk updating alert status."""
        # Create multiple alerts
        alert_ids = []
        for i in range(3):
            alert_data = Alert(
                id=str(uuid.uuid4()),
                type="transaction",
                message=f"Bulk test alert {i}",
                time=datetime.now().isoformat(),
                status="new",
                notifications_enabled=True
            )
            created_alert = await alert_repository.create(alert_data)
            alert_ids.append(created_alert.id)
        
        # Bulk update status
        updated_count = await alert_repository.bulk_update_status(alert_ids, "resolved")
        
        assert updated_count == 3
        
        # Verify all alerts were updated
        for alert_id in alert_ids:
            alert = await alert_repository.get_by_id(alert_id)
            assert alert.status == "resolved"
    
    @pytest.mark.asyncio
    async def test_get_alert_stats(self, alert_repository: AlertRepository):
        """Test getting alert statistics."""
        # Create some test alerts
        for i in range(2):
            alert_data = Alert(
                id=str(uuid.uuid4()),
                type="transaction" if i == 0 else "balance",
                message=f"Test alert {i}",
                time=datetime.now().isoformat(),
                status="new" if i == 0 else "resolved",
                priority="high" if i == 0 else "low",
                notifications_enabled=True
            )
            await alert_repository.create(alert_data)
        
        stats = await alert_repository.get_alert_stats()
        
        assert "total_alerts" in stats
        assert "alerts_by_status" in stats
        assert "alerts_by_type" in stats
        assert "alerts_by_priority" in stats
        assert stats["total_alerts"] >= 2
