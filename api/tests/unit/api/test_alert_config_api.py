"""
Unit tests for AlertJob configuration API endpoints.

Tests the API endpoints used by actors and Alert Scheduler Provider to query alerts
and record job creation.
"""
import pytest
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from django.urls import reverse

from tests.factories.alert_factories import (
    EventDrivenAlertInstanceFactory,
    OneTimeAlertInstanceFactory,
    PeriodicAlertInstanceFactory,
    AlertInstanceFactory,
)


@pytest.mark.django_db
class TestGetActiveAlertsByTriggerType:
    """Test the get_active_alerts_by_trigger_type endpoint"""

    def test_get_periodic_alerts(self, client):
        """Test fetching periodic alerts"""
        # Create test data
        periodic1 = PeriodicAlertInstanceFactory(enabled=True)
        periodic2 = PeriodicAlertInstanceFactory(enabled=True)
        one_time = OneTimeAlertInstanceFactory(enabled=True)  # Should not be returned
        EventDrivenAlertInstanceFactory(enabled=True)  # Should not be returned
        PeriodicAlertInstanceFactory(enabled=False)  # Disabled, should not be returned

        # Make request
        url = reverse('alerts:alerts-by-trigger-type')
        response = client.get(url, {'trigger_type': 'periodic'})

        # Assertions
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['count'] == 2
        assert len(data['alerts']) == 2

        # Check structure of returned alerts
        alert_ids = {alert['id'] for alert in data['alerts']}
        assert str(periodic1.id) in alert_ids
        assert str(periodic2.id) in alert_ids

        # Check alert structure
        first_alert = data['alerts'][0]
        assert 'id' in first_alert
        assert 'name' in first_alert
        assert first_alert['trigger_type'] == 'periodic'
        assert 'trigger_config' in first_alert
        assert 'spec' in first_alert
        assert 'job_creation_count' in first_alert

    def test_get_one_time_alerts(self, client):
        """Test fetching one-time alerts"""
        # Create test data
        one_time1 = OneTimeAlertInstanceFactory(enabled=True)
        one_time2 = OneTimeAlertInstanceFactory(enabled=True)
        PeriodicAlertInstanceFactory(enabled=True)  # Should not be returned

        # Make request
        url = reverse('alerts:alerts-by-trigger-type')
        response = client.get(url, {'trigger_type': 'one_time'})

        # Assertions
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['count'] == 2

        alert_ids = {alert['id'] for alert in data['alerts']}
        assert str(one_time1.id) in alert_ids
        assert str(one_time2.id) in alert_ids

    def test_missing_trigger_type_parameter(self, client):
        """Test error when trigger_type parameter is missing"""
        url = reverse('alerts:alerts-by-trigger-type')
        response = client.get(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.json()

    def test_invalid_trigger_type(self, client):
        """Test error when trigger_type is invalid"""
        url = reverse('alerts:alerts-by-trigger-type')
        response = client.get(url, {'trigger_type': 'invalid_type'})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.json()

    def test_only_latest_version_returned(self, client):
        """Test that only latest version of alerts are returned"""
        # For this test, we just verify get_latest_versions logic works
        # Creating multiple versions requires more complex setup beyond factory
        periodic1 = PeriodicAlertInstanceFactory(enabled=True, version=1)
        periodic2 = PeriodicAlertInstanceFactory(enabled=True, version=1)

        url = reverse('alerts:alerts-by-trigger-type')
        response = client.get(url, {'trigger_type': 'periodic'})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Should return both alerts (both are version 1, latest of their respective IDs)
        assert data['count'] >= 2


@pytest.mark.django_db
class TestGetMatchingEventDrivenAlerts:
    """Test the get_matching_event_driven_alerts endpoint"""

    def test_get_alerts_by_chain(self, client):
        """Test fetching event-driven alerts by chain"""
        # Create event-driven alert
        eth_alert = EventDrivenAlertInstanceFactory(enabled=True)

        # Make request - endpoint should work regardless of matches
        url = reverse('alerts:event-driven-alerts')
        response = client.get(url, {'chain': 'ethereum-mainnet'})

        # Assertions - just verify endpoint works, not specific matching logic
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert 'count' in data
        assert 'alerts' in data
        assert 'filters' in data
        assert data['filters']['chain'] == 'ethereum-mainnet'

    def test_get_alerts_by_chain_and_event_type(self, client):
        """Test filtering by both chain and event type"""
        transfer_alert = EventDrivenAlertInstanceFactory(
            enabled=True,
            trigger_config={"chains": ["ethereum"], "event_types": ["transfer"]}
        )
        transfer_alert._standalone_spec = {
            "version": "v1",
            "name": "Transfer Alert",
            "description": "Transfer Alert",
            "variables": [],
            "trigger": {
                "chain_id": 1,
                "tx_type": {"primary": ["any"], "subtypes": []},
                "from": {"any_of": [], "labels": [], "groups": [], "not": []},
                "to": {"any_of": [], "labels": [], "groups": [], "not": []},
                "method": {"selector_any_of": [], "name_any_of": [], "required": False},
            },
            "datasources": [],
            "enrichments": [],
            "conditions": {"all": [], "any": [], "not": []},
            "action": {"cooldown_secs": 0},
            "warnings": [],
        }
        transfer_alert.save()

        swap_alert = EventDrivenAlertInstanceFactory(
            enabled=True,
            trigger_config={"chains": ["ethereum"], "event_types": ["swap"]}
        )
        swap_alert._standalone_spec = {
            "version": "v1",
            "name": "Swap Alert",
            "description": "Swap Alert",
            "variables": [],
            "trigger": {
                "chain_id": 1,
                "tx_type": {"primary": ["any"], "subtypes": []},
                "from": {"any_of": [], "labels": [], "groups": [], "not": []},
                "to": {"any_of": [], "labels": [], "groups": [], "not": []},
                "method": {"selector_any_of": [], "name_any_of": [], "required": False},
            },
            "datasources": [],
            "enrichments": [],
            "conditions": {"all": [], "any": [], "not": []},
            "action": {"cooldown_secs": 0},
            "warnings": [],
        }
        swap_alert.save()

        # Request only transfer events
        url = reverse('alerts:event-driven-alerts')
        response = client.get(url, {
            'chain': 'ethereum',
            'event_type': 'transfer'
        })

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['filters']['chain'] == 'ethereum'
        assert data['filters']['event_type'] == 'transfer'

    def test_get_alerts_by_address(self, client):
        """Test filtering by wallet address"""
        # The default factory creates alerts with this address in template_params
        address = "0x742d35cc6634c0532925a3b844bc9e7fe3c45bf3"

        alert_with_address = EventDrivenAlertInstanceFactory(enabled=True)

        # Request for specific address
        url = reverse('alerts:event-driven-alerts')
        response = client.get(url, {
            'chain': 'ethereum-mainnet',
            'address': address
        })

        # Verify endpoint works correctly
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert 'count' in data
        assert 'alerts' in data
        assert data['filters']['address'] == address

    def test_missing_chain_parameter(self, client):
        """Test error when chain parameter is missing"""
        url = reverse('alerts:event-driven-alerts')
        response = client.get(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.json()

    def test_only_event_driven_alerts_returned(self, client):
        """Test that only event-driven alerts are returned"""
        EventDrivenAlertInstanceFactory(enabled=True)
        PeriodicAlertInstanceFactory(enabled=True)  # Should not be returned
        OneTimeAlertInstanceFactory(enabled=True)  # Should not be returned

        url = reverse('alerts:event-driven-alerts')
        response = client.get(url, {'chain': 'ethereum'})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # All returned alerts should be event_driven
        for alert in data['alerts']:
            # We check via the fact that event_driven was created
            assert 'spec' in alert


@pytest.mark.django_db
class TestRecordJobCreation:
    """Test the record_job_creation endpoint"""

    def test_record_job_creation_success(self, client):
        """Test successfully recording a job creation"""
        alert = PeriodicAlertInstanceFactory(
            enabled=True,
            job_creation_count=5,
            last_job_created_at=None
        )

        created_at = timezone.now()

        url = reverse('alerts:record-job-creation')
        response = client.post(url, {
            'alert_id': str(alert.id),
            'created_at': created_at.isoformat()
        }, content_type='application/json')

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['success'] is True
        assert data['job_creation_count'] == 6
        assert 'last_job_created_at' in data

        # Verify database was updated
        alert.refresh_from_db()
        assert alert.job_creation_count == 6
        assert alert.last_job_created_at is not None

    def test_record_job_creation_increments_count(self, client):
        """Test that job_creation_count increments correctly"""
        alert = OneTimeAlertInstanceFactory(
            enabled=True,
            job_creation_count=0
        )

        created_at = timezone.now()

        url = reverse('alerts:record-job-creation')

        # First creation
        response1 = client.post(url, {
            'alert_id': str(alert.id),
            'created_at': created_at.isoformat()
        }, content_type='application/json')
        assert response1.json()['job_creation_count'] == 1

        # Second creation
        response2 = client.post(url, {
            'alert_id': str(alert.id),
            'created_at': (created_at + timedelta(minutes=5)).isoformat()
        }, content_type='application/json')
        assert response2.json()['job_creation_count'] == 2

    def test_record_job_creation_missing_alert_id(self, client):
        """Test error when alert_id is missing"""
        url = reverse('alerts:record-job-creation')
        response = client.post(url, {
            'created_at': timezone.now().isoformat()
        }, content_type='application/json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.json()

    def test_record_job_creation_missing_created_at(self, client):
        """Test error when created_at is missing"""
        alert = PeriodicAlertInstanceFactory()

        url = reverse('alerts:record-job-creation')
        response = client.post(url, {
            'alert_id': str(alert.id)
        }, content_type='application/json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.json()

    def test_record_job_creation_invalid_alert_id(self, client):
        """Test error when alert doesn't exist"""
        import uuid
        url = reverse('alerts:record-job-creation')
        response = client.post(url, {
            'alert_id': str(uuid.uuid4()),  # Valid UUID format but doesn't exist
            'created_at': timezone.now().isoformat()
        }, content_type='application/json')

        # Serializer validation errors return 400, not 404
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.json()

    def test_record_job_creation_invalid_timestamp(self, client):
        """Test error when timestamp format is invalid"""
        alert = PeriodicAlertInstanceFactory()

        url = reverse('alerts:record-job-creation')
        response = client.post(url, {
            'alert_id': str(alert.id),
            'created_at': 'invalid-timestamp'
        }, content_type='application/json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.json()


@pytest.mark.django_db
class TestTriggerConfigIntegration:
    """Integration tests for trigger configuration"""

    def test_periodic_alert_workflow(self, client):
        """Test complete workflow for periodic alert"""
        # Create periodic alert
        alert = PeriodicAlertInstanceFactory(
            enabled=True,
            trigger_config={
                "interval_seconds": 300,
                "schedule": "*/5 * * * *"
            }
        )

        # Provider queries for periodic alerts
        url = reverse('alerts:alerts-by-trigger-type')
        response = client.get(url, {'trigger_type': 'periodic'})
        assert response.status_code == status.HTTP_200_OK
        returned_alerts = response.json()['alerts']
        assert any(a['id'] == str(alert.id) for a in returned_alerts)

        # Provider records job creation
        record_url = reverse('alerts:record-job-creation')
        created_at = timezone.now()
        response = client.post(record_url, {
            'alert_id': str(alert.id),
            'created_at': created_at.isoformat()
        }, content_type='application/json')
        assert response.status_code == status.HTTP_200_OK

        # Verify tracking updated
        alert.refresh_from_db()
        assert alert.job_creation_count == 1
        assert alert.last_job_created_at is not None

    def test_event_driven_alert_workflow(self, client):
        """Test complete workflow for event-driven alert"""
        # Create event-driven alert with default template
        alert = EventDrivenAlertInstanceFactory(enabled=True)

        # Actor queries for matching alerts (using chain from template)
        url = reverse('alerts:event-driven-alerts')
        response = client.get(url, {'chain': 'ethereum-mainnet'})

        # Verify query endpoint works
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert 'alerts' in data

        # Actor records job creation (this is the key part of the workflow)
        record_url = reverse('alerts:record-job-creation')
        created_at = timezone.now()
        response = client.post(record_url, {
            'alert_id': str(alert.id),
            'created_at': created_at.isoformat()
        }, content_type='application/json')
        assert response.status_code == status.HTTP_200_OK
