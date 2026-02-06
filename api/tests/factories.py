"""
Factory classes for generating test data using factory_boy
"""

import factory
from factory.django import DjangoModelFactory
from factory import Faker, SubFactory, LazyAttribute, Trait, post_generation
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import random
import uuid

from app.models import (
    # Alerts
    Alert, AlertJobSpec, AlertChangeLog, AlertExecution,
    # Blockchain
    BlockchainNode,
)

User = get_user_model()


class UserFactory(DjangoModelFactory):
    """Factory for creating test users"""
    class Meta:
        model = User

    email = factory.Faker('email')  # Generates unique random emails
    username = factory.LazyAttribute(lambda obj: obj.email)  # Use email as username
    first_name = Faker('first_name')
    last_name = Faker('last_name')
    firebase_uid = factory.LazyFunction(lambda: f"firebase_{uuid.uuid4().hex}")  # Unique firebase UID
    is_active = True
    is_staff = False
    is_superuser = False

    class Params:
        admin = Trait(
            is_staff=True,
            is_superuser=True,
            username='admin'
        )
        premium = Trait(
            username=factory.Sequence(lambda n: f'premium_user{n}')
        )

    @post_generation
    def password(self, create, extracted, **kwargs):
        if create:
            self.set_password(extracted or 'testpass123')
            self.save()


class AlertFactory(DjangoModelFactory):
    """Factory for creating alerts"""
    class Meta:
        model = Alert

    name = Faker('sentence', nb_words=3)
    nl_description = Faker('paragraph', nb_sentences=2)
    version = factory.Sequence(lambda n: n + 1)
    enabled = True
    user = SubFactory(UserFactory)
    chain_scope = factory.LazyAttribute(
        lambda o: [{'chain': random.choice(['ethereum', 'bitcoin', 'solana']),
                   'sub_chains': ['mainnet']}]
    )

    class Params:
        disabled = Trait(enabled=False)
        multi_chain = Trait(
            chain_scope=[
                {'chain': 'ethereum', 'sub_chains': ['mainnet', 'goerli']},
                {'chain': 'polygon', 'sub_chains': ['mainnet']}
            ]
        )


class AlertJobSpecFactory(DjangoModelFactory):
    """Factory for alert job specifications"""
    class Meta:
        model = AlertJobSpec

    alert = SubFactory(AlertFactory)
    alert_version = factory.LazyAttribute(lambda o: o.alert.version)
    status = 'active'
    generated_by = 'llm'
    generation_model = factory.Faker('random_element', elements=['gpt-4', 'gpt-3.5-turbo'])
    generation_prompt_hash = factory.Faker('sha256')
    job_spec = factory.LazyAttribute(
        lambda o: {
            'query': f'SELECT * FROM {o.alert.chain_scope[0]["chain"]}_data WHERE value > 100',
            'conditions': ['value > 100'],
            'schedule': '*/5 * * * *'
        }
    )

    class Params:
        pending = Trait(status='pending_review')
        failed = Trait(
            status='failed',
            validation_errors={'error': 'Invalid query syntax'}
        )


class AlertExecutionFactory(DjangoModelFactory):
    """Factory for alert executions"""
    class Meta:
        model = AlertExecution

    alert = SubFactory(AlertFactory)
    alert_version = factory.LazyAttribute(lambda o: o.alert.version)
    execution_id = factory.Faker('uuid4')
    status = 'completed'
    result = 'triggered'
    result_value = factory.Faker('pydecimal', left_digits=3, right_digits=2, positive=True)
    execution_time_ms = factory.Faker('random_int', min=10, max=500)
    rows_processed = factory.Faker('random_int', min=100, max=10000)
    started_at = factory.LazyFunction(lambda: timezone.now() - timedelta(minutes=5))
    completed_at = factory.LazyAttribute(
        lambda o: o.started_at + timedelta(milliseconds=o.execution_time_ms)
    )

    class Params:
        failed = Trait(
            status='failed',
            result='error',
            error_message='Execution failed',
            error_details={'error': 'Timeout'},
            completed_at=None
        )


class BlockchainNodeFactory(DjangoModelFactory):
    """Factory for blockchain nodes"""
    class Meta:
        model = BlockchainNode

    chain_id = factory.LazyFunction(lambda: f'chain-{uuid.uuid4().hex[:12]}')  # Unique chain ID
    chain_name = factory.Faker('company')
    network = factory.Faker('random_element', elements=['mainnet', 'testnet', 'devnet'])
    subnet = factory.LazyAttribute(lambda o: o.network)
    vm_type = factory.Faker('random_element', elements=['EVM', 'UTXO', 'SVM', 'COSMOS'])
    rpc_url = factory.LazyAttribute(lambda o: f'https://{o.chain_id}.rpc.example.com')
    ws_url = factory.LazyAttribute(
        lambda o: f'wss://{o.chain_id}.ws.example.com' if o.vm_type in ['EVM', 'SVM'] else ''
    )
    enabled = True
    is_primary = False
    priority = 1
    latency_ms = factory.Faker('random_int', min=50, max=300)
    success_rate = factory.Faker('pydecimal', left_digits=2, right_digits=1, min_value=90, max_value=99.9)
    last_health_check = factory.LazyFunction(timezone.now)

    class Params:
        ethereum = Trait(
            chain_id='ethereum-mainnet',
            chain_name='Ethereum',
            vm_type='EVM',
            network='mainnet'
        )
        unhealthy = Trait(
            success_rate=Decimal('85.0'),
            latency_ms=1500,
            last_health_check=factory.LazyFunction(lambda: timezone.now() - timedelta(hours=1))
        )
