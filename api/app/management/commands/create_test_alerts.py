"""
Management command to create test alerts for Phase 3 validation.

Usage:
    python manage.py create_test_alerts

Creates a diverse set of test alerts for validating the Alert Scheduler Provider v2.0:
- Event-driven alerts (address monitoring)
- Periodic alerts (cron scheduling)
- One-time alerts (scheduled times)
"""

from django.core.management.base import BaseCommand
from app.models.alerts import AlertInstance, AlertTemplate
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import json

User = get_user_model()


class Command(BaseCommand):
    help = 'Create test alerts for Phase 3 validation'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=20,
            help='Number of test alerts to create (default: 20)',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing test alerts before creating new ones',
        )

    def handle(self, *args, **options):
        count = options['count']

        # Get or create test user (use email as lookup since username might be empty)
        try:
            test_user = User.objects.get(email='test@example.com')
            self.stdout.write(f'Using existing test user (ID: {test_user.id})')
        except User.DoesNotExist:
            test_user = User.objects.create_user(
                username='test_user_phase3',
                email='test_phase3@example.com',
                password='test_password'
            )
            self.stdout.write(self.style.SUCCESS(f'Created test user: {test_user.username}'))

        # Clear existing test alerts if requested
        if options['clear']:
            deleted_count = AlertInstance.objects.filter(
                name__startswith='Test Alert -'
            ).delete()[0]
            self.stdout.write(self.style.WARNING(f'Cleared {deleted_count} existing test alerts'))

        # Create alerts
        alerts_created = 0

        # Event-driven alerts (50% of total)
        event_count = count // 2
        for i in range(event_count):
            alert = AlertInstance.objects.create(
                name=f'Test Alert - Event Driven {i+1}',
                user=test_user,
                trigger_type='event_driven',
                trigger_config={
                    'priority': 'normal' if i % 2 == 0 else 'high',
                    'dedup_window_seconds': 300,
                },
                spec={
                    'scope': {
                        'addresses': [f'0x{"a" * (40 - len(str(i)))}{i:04d}'],
                        'chains': ['ethereum', 'polygon'] if i % 3 == 0 else ['ethereum'],
                        'contracts': []
                    },
                    'filters': {
                        'value_threshold': 1000000 * (i + 1),
                        'gas_threshold': None,
                        'event_types': []
                    },
                    'trigger': {
                        'mode': 'event',
                        'event_type': 'transfer'
                    }
                },
                enabled=True,
            )
            alerts_created += 1

        # Periodic alerts (30% of total)
        periodic_count = (count * 3) // 10
        cron_expressions = [
            '*/5 * * * *',  # Every 5 minutes
            '0 * * * *',    # Every hour
            '0 0 * * *',    # Every day at midnight
            '0 9 * * 1',    # Every Monday at 9 AM
        ]

        for i in range(periodic_count):
            cron = cron_expressions[i % len(cron_expressions)]
            alert = AlertInstance.objects.create(
                name=f'Test Alert - Periodic {i+1}',
                user=test_user,
                trigger_type='periodic',
                trigger_config={
                    'cron_expression': cron,
                    'timezone': 'UTC',
                    'priority': 'normal',
                },
                spec={
                    'scope': {
                        'addresses': [],
                        'chains': ['ethereum'],
                        'contracts': []
                    },
                    'filters': {},
                    'trigger': {
                        'mode': 'schedule',
                        'schedule_type': 'periodic'
                    }
                },
                enabled=True,
            )
            alerts_created += 1

        # One-time alerts (20% of total)
        onetime_count = count - event_count - periodic_count
        for i in range(onetime_count):
            # Schedule alerts at various times in the future
            scheduled_time = timezone.now() + timedelta(minutes=5 + (i * 10))

            alert = AlertInstance.objects.create(
                name=f'Test Alert - One Time {i+1}',
                user=test_user,
                trigger_type='one_time',
                trigger_config={
                    'scheduled_time': scheduled_time.isoformat(),
                    'timezone': 'UTC',
                    'priority': 'high' if i % 2 == 0 else 'normal',
                },
                spec={
                    'scope': {
                        'addresses': [],
                        'chains': ['ethereum'],
                        'contracts': []
                    },
                    'filters': {},
                    'trigger': {
                        'mode': 'schedule',
                        'schedule_type': 'one_time'
                    }
                },
                enabled=True,
            )
            alerts_created += 1

        # Summary
        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Created {alerts_created} test alerts:'
        ))
        self.stdout.write(f'  - Event-driven: {event_count}')
        self.stdout.write(f'  - Periodic: {periodic_count}')
        self.stdout.write(f'  - One-time: {onetime_count}')

        self.stdout.write(self.style.SUCCESS(
            f'\n🔄 Next step: Run "python manage.py warm_alert_cache" to sync to Redis'
        ))
