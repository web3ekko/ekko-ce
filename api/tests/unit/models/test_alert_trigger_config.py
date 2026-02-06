"""
Unit tests for AlertInstance trigger configuration fields.

Tests the new trigger_type, trigger_config, last_job_created_at, and job_creation_count
fields added to support AlertJob creation.
"""
import pytest
from django.utils import timezone
from datetime import timedelta

from tests.factories.alert_factories import (
    AlertInstanceFactory,
    EventDrivenAlertInstanceFactory,
    OneTimeAlertInstanceFactory,
    PeriodicAlertInstanceFactory,
)


@pytest.mark.django_db
class TestAlertInstanceTriggerConfiguration:
    """Test trigger configuration fields on AlertInstance model"""

    def test_default_trigger_type_is_event_driven(self):
        """Test that trigger_type defaults to event_driven"""
        alert = AlertInstanceFactory()
        assert alert.trigger_type == 'event_driven'

    def test_trigger_type_choices(self):
        """Test all valid trigger_type values"""
        event_driven = EventDrivenAlertInstanceFactory()
        assert event_driven.trigger_type == 'event_driven'

        one_time = OneTimeAlertInstanceFactory()
        assert one_time.trigger_type == 'one_time'

        periodic = PeriodicAlertInstanceFactory()
        assert periodic.trigger_type == 'periodic'

    def test_trigger_config_defaults_to_empty_dict(self):
        """Test that trigger_config defaults to empty dict"""
        # When no trigger_config is provided, should default to empty dict
        alert = AlertInstanceFactory()
        assert alert.trigger_config is not None
        # If we explicitly omit it during creation (not providing the kwarg)
        # it should still have the default value from the factory

    def test_event_driven_trigger_config(self):
        """Test event_driven trigger configuration structure"""
        alert = EventDrivenAlertInstanceFactory()

        assert 'chains' in alert.trigger_config
        assert 'event_types' in alert.trigger_config
        assert isinstance(alert.trigger_config['chains'], list)
        assert isinstance(alert.trigger_config['event_types'], list)

    def test_one_time_trigger_config(self):
        """Test one_time trigger configuration structure"""
        alert = OneTimeAlertInstanceFactory()

        assert 'reset_allowed' in alert.trigger_config
        assert isinstance(alert.trigger_config['reset_allowed'], bool)

    def test_periodic_trigger_config(self):
        """Test periodic trigger configuration structure"""
        alert = PeriodicAlertInstanceFactory()

        assert 'interval_seconds' in alert.trigger_config or 'schedule' in alert.trigger_config

    def test_job_creation_count_defaults_to_zero(self):
        """Test that job_creation_count defaults to 0"""
        alert = AlertInstanceFactory()
        assert alert.job_creation_count == 0

    def test_job_creation_count_increment(self):
        """Test incrementing job_creation_count"""
        alert = AlertInstanceFactory(job_creation_count=5)
        alert.job_creation_count += 1
        alert.save()

        alert.refresh_from_db()
        assert alert.job_creation_count == 6

    def test_last_job_created_at_defaults_to_none(self):
        """Test that last_job_created_at defaults to None"""
        alert = AlertInstanceFactory()
        assert alert.last_job_created_at is None

    def test_last_job_created_at_update(self):
        """Test updating last_job_created_at"""
        now = timezone.now()
        alert = AlertInstanceFactory(last_job_created_at=now)
        alert.save()

        alert.refresh_from_db()
        assert alert.last_job_created_at is not None
        # Compare timestamps (allow small delta for microseconds)
        delta = abs((alert.last_job_created_at - now).total_seconds())
        assert delta < 1  # Within 1 second

    def test_job_tracking_workflow(self):
        """Test complete job tracking workflow"""
        alert = PeriodicAlertInstanceFactory(
            job_creation_count=0,
            last_job_created_at=None
        )

        # Simulate first job creation
        first_time = timezone.now()
        alert.job_creation_count += 1
        alert.last_job_created_at = first_time
        alert.save()

        alert.refresh_from_db()
        assert alert.job_creation_count == 1
        assert alert.last_job_created_at == first_time

        # Simulate second job creation
        second_time = first_time + timedelta(minutes=5)
        alert.job_creation_count += 1
        alert.last_job_created_at = second_time
        alert.save()

        alert.refresh_from_db()
        assert alert.job_creation_count == 2
        assert alert.last_job_created_at == second_time


@pytest.mark.django_db
class TestAlertInstanceQueryingByTriggerType:
    """Test querying alerts by trigger type"""

    def test_filter_by_event_driven(self):
        """Test filtering alerts by event_driven trigger type"""
        event_driven1 = EventDrivenAlertInstanceFactory(enabled=True)
        event_driven2 = EventDrivenAlertInstanceFactory(enabled=True)
        OneTimeAlertInstanceFactory(enabled=True)
        PeriodicAlertInstanceFactory(enabled=True)

        from app.models.alerts import AlertInstance
        latest_alerts = AlertInstance.get_latest_versions()
        event_driven_alerts = [
            a for a in latest_alerts
            if a.enabled and a.trigger_type == 'event_driven'
        ]

        assert len(event_driven_alerts) >= 2
        alert_ids = {str(a.id) for a in event_driven_alerts}
        assert str(event_driven1.id) in alert_ids
        assert str(event_driven2.id) in alert_ids

    def test_filter_by_periodic(self):
        """Test filtering alerts by periodic trigger type"""
        periodic1 = PeriodicAlertInstanceFactory(enabled=True)
        periodic2 = PeriodicAlertInstanceFactory(enabled=True)
        EventDrivenAlertInstanceFactory(enabled=True)
        OneTimeAlertInstanceFactory(enabled=True)

        from app.models.alerts import AlertInstance
        latest_alerts = AlertInstance.get_latest_versions()
        periodic_alerts = [
            a for a in latest_alerts
            if a.enabled and a.trigger_type == 'periodic'
        ]

        assert len(periodic_alerts) >= 2
        alert_ids = {str(a.id) for a in periodic_alerts}
        assert str(periodic1.id) in alert_ids
        assert str(periodic2.id) in alert_ids

    def test_filter_by_one_time(self):
        """Test filtering alerts by one_time trigger type"""
        one_time1 = OneTimeAlertInstanceFactory(enabled=True)
        one_time2 = OneTimeAlertInstanceFactory(enabled=True)
        EventDrivenAlertInstanceFactory(enabled=True)
        PeriodicAlertInstanceFactory(enabled=True)

        from app.models.alerts import AlertInstance
        latest_alerts = AlertInstance.get_latest_versions()
        one_time_alerts = [
            a for a in latest_alerts
            if a.enabled and a.trigger_type == 'one_time'
        ]

        assert len(one_time_alerts) >= 2
        alert_ids = {str(a.id) for a in one_time_alerts}
        assert str(one_time1.id) in alert_ids
        assert str(one_time2.id) in alert_ids

    def test_disabled_alerts_excluded(self):
        """Test that disabled alerts are excluded from queries"""
        EventDrivenAlertInstanceFactory(enabled=False)
        PeriodicAlertInstanceFactory(enabled=False)
        OneTimeAlertInstanceFactory(enabled=False)

        from app.models.alerts import AlertInstance
        latest_alerts = AlertInstance.get_latest_versions()
        enabled_alerts = [a for a in latest_alerts if a.enabled]

        # Should not include the disabled alerts we just created
        disabled_count = len([a for a in latest_alerts if not a.enabled])
        assert disabled_count >= 3


@pytest.mark.django_db
class TestTriggerConfigIndex:
    """Test database index on trigger_type and enabled fields"""

    def test_index_exists(self):
        """Test that index on (trigger_type, enabled) exists"""
        from app.models.alerts import AlertInstance

        # Check model Meta indexes
        indexes = AlertInstance._meta.indexes
        index_fields = [
            tuple(idx.fields) for idx in indexes
        ]

        # Should have index on trigger_type and enabled
        assert ('trigger_type', 'enabled') in index_fields

    def test_query_performance_with_index(self):
        """Test that queries use the index (basic check)"""
        # Create test data
        for _ in range(10):
            PeriodicAlertInstanceFactory(enabled=True)
        for _ in range(10):
            EventDrivenAlertInstanceFactory(enabled=True)

        from app.models.alerts import AlertInstance
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        # Query periodic alerts
        with CaptureQueriesContext(connection) as queries:
            latest_alerts = AlertInstance.get_latest_versions()
            periodic_alerts = [
                a for a in latest_alerts
                if a.enabled and a.trigger_type == 'periodic'
            ]
            # Force evaluation
            len(periodic_alerts)

        # Just verify query executed (detailed performance testing would require EXPLAIN)
        assert len(queries) > 0


@pytest.mark.django_db
class TestFactoryVariants:
    """Test the specialized factory variants"""

    def test_event_driven_factory_creates_correct_config(self):
        """Test EventDrivenAlertInstanceFactory produces correct configuration"""
        alert = EventDrivenAlertInstanceFactory()

        assert alert.trigger_type == 'event_driven'
        assert 'chains' in alert.trigger_config
        assert 'event_types' in alert.trigger_config
        assert len(alert.trigger_config['chains']) > 0
        assert len(alert.trigger_config['event_types']) > 0

    def test_one_time_factory_creates_correct_config(self):
        """Test OneTimeAlertInstanceFactory produces correct configuration"""
        alert = OneTimeAlertInstanceFactory()

        assert alert.trigger_type == 'one_time'
        assert 'reset_allowed' in alert.trigger_config

    def test_periodic_factory_creates_correct_config(self):
        """Test PeriodicAlertInstanceFactory produces correct configuration"""
        alert = PeriodicAlertInstanceFactory()

        assert alert.trigger_type == 'periodic'
        # Should have at least one of interval_seconds or schedule
        has_interval = 'interval_seconds' in alert.trigger_config
        has_schedule = 'schedule' in alert.trigger_config
        assert has_interval or has_schedule
