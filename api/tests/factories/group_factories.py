"""
Django model factories for group models.
Uses factory_boy for consistent test data generation.
"""

import factory
import uuid
from datetime import datetime, timedelta
from faker import Faker
from django.utils import timezone

from app.models.groups import GenericGroup, GroupSubscription, GroupType
from tests.factories.auth_factories import UserFactory

fake = Faker()


class GenericGroupFactory(factory.django.DjangoModelFactory):
    """Factory for GenericGroup model"""

    class Meta:
        model = GenericGroup

    name = factory.Sequence(lambda n: f"Test Group {n}")
    description = factory.Faker("sentence")
    group_type = factory.Iterator([
        GroupType.WALLET, GroupType.ALERT, GroupType.NETWORK, GroupType.TOKEN
    ])
    owner = factory.SubFactory(UserFactory)
    settings = factory.LazyAttribute(
        lambda o: {"alert_type": "wallet"} if o.group_type == GroupType.ALERT else {}
    )
    member_data = factory.LazyFunction(lambda: {"members": {}})
    member_count = 0


class WalletGroupFactory(GenericGroupFactory):
    """Factory for wallet groups"""

    group_type = GroupType.WALLET
    name = factory.Sequence(lambda n: f"Wallet Group {n}")


class AlertGroupFactory(GenericGroupFactory):
    """Factory for alert groups"""

    group_type = GroupType.ALERT
    name = factory.Sequence(lambda n: f"Alert Group {n}")
    settings = factory.LazyFunction(lambda: {"alert_type": "wallet"})


class NetworkGroupFactory(GenericGroupFactory):
    """Factory for network groups"""

    group_type = GroupType.NETWORK
    name = factory.Sequence(lambda n: f"Network Group {n}")


class TokenGroupFactory(GenericGroupFactory):
    """Factory for token groups"""

    group_type = GroupType.TOKEN
    name = factory.Sequence(lambda n: f"Token Group {n}")


class GroupWithMembersFactory(GenericGroupFactory):
    """Factory for groups with initial members"""

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        member_count = kwargs.pop('member_count_to_add', 3)
        group = super()._create(model_class, *args, **kwargs)

        # Add sample members
        for i in range(member_count):
            member_key = f"ETH:mainnet:0x{''.join([fake.random_letter() for _ in range(40)])}"
            group.add_member_local(
                member_key=member_key,
                added_by=str(group.owner.id),
                label=f"Wallet {i}",
                tags=["test"],
                metadata={}
            )

        return group


class GroupSubscriptionFactory(factory.django.DjangoModelFactory):
    """Factory for GroupSubscription model"""

    class Meta:
        model = GroupSubscription

    alert_group = factory.SubFactory(AlertGroupFactory)
    target_group = factory.SubFactory(WalletGroupFactory)
    target_key = None
    owner = factory.LazyAttribute(lambda obj: obj.alert_group.owner)
    settings = factory.LazyFunction(lambda: {})
    is_active = True

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        target_key = kwargs.get("target_key")
        if target_key:
            kwargs["target_group"] = None
        return super()._create(model_class, *args, **kwargs)


# Utility functions

def create_group_with_members(owner=None, group_type=GroupType.WALLET, member_count=5):
    """Create a group with the specified number of members."""
    if owner is None:
        owner = UserFactory()

    group = GenericGroupFactory(
        owner=owner,
        group_type=group_type
    )

    for i in range(member_count):
        member_key = f"ETH:mainnet:0x{fake.sha256()[:40]}"
        group.add_member_local(
            member_key=member_key,
            added_by=str(owner.id),
            label=f"Wallet {i}",
            tags=["test", f"batch-{i % 2}"],
            metadata={"index": i}
        )

    return group


def create_subscription_chain(owner=None, target_group_count=3):
    """Create an alert group with multiple target group subscriptions."""
    if owner is None:
        owner = UserFactory()

    alert_group = AlertGroupFactory(owner=owner)

    subscriptions = []
    for _ in range(target_group_count):
        target_group = WalletGroupFactory(owner=owner)
        subscription = GroupSubscriptionFactory(
            alert_group=alert_group,
            target_group=target_group,
            owner=owner
        )
        subscriptions.append(subscription)

    return alert_group, subscriptions
