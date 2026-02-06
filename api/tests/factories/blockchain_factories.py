"""
Django model factories for blockchain models
Uses factory_boy for consistent test data generation
"""
import factory
import uuid
from datetime import datetime, timedelta
from faker import Faker
from django.utils import timezone

from blockchain.models import (
    Chain,
    SubChain,
    Blockchain,
    Wallet,
    Token,
    Dao,
    WalletSubscription,
    DaoSubscription,
    DaoWallet,
    Category,
    Story,
    Tag,
    WalletBalance,
    BlockchainStory,
    Image,
)

fake = Faker()


class ChainFactory(factory.django.DjangoModelFactory):
    """Factory for Chain model (new alert system chain registry)."""

    class Meta:
        model = Chain
        django_get_or_create = ("name",)

    name = factory.Sequence(lambda n: f"chain_{n}")
    display_name = factory.LazyAttribute(lambda o: o.name.replace("_", " ").title())
    chain_id = factory.Sequence(lambda n: 1000 + n)
    rpc_url = factory.LazyAttribute(lambda o: f"https://rpc.{o.name}.example")
    explorer_url = factory.LazyAttribute(lambda o: f"https://explorer.{o.name}.example")
    native_token = "TKN"
    enabled = True


class SubChainFactory(factory.django.DjangoModelFactory):
    """Factory for SubChain model (network/subnet within a Chain)."""

    class Meta:
        model = SubChain
        django_get_or_create = ("chain", "name")

    chain = factory.SubFactory(ChainFactory)
    name = "mainnet"
    display_name = "Mainnet"
    network_id = None
    rpc_url = factory.LazyAttribute(lambda o: o.chain.rpc_url)
    explorer_url = factory.LazyAttribute(lambda o: o.chain.explorer_url)
    is_testnet = False
    enabled = True


class BlockchainFactory(factory.django.DjangoModelFactory):
    """Factory for Blockchain model"""
    
    class Meta:
        model = Blockchain
        django_get_or_create = ('symbol',)
    
    name = factory.Faker("word")
    symbol = factory.LazyAttribute(lambda obj: obj.name.lower()[:10] if obj.name else "eth")
    chain_type = "EVM"


class CategoryFactory(factory.django.DjangoModelFactory):
    """Factory for Category model"""
    
    class Meta:
        model = Category
        django_get_or_create = ('name',)
    
    name = factory.Faker("word")


class DaoFactory(factory.django.DjangoModelFactory):
    """Factory for Dao model"""
    
    class Meta:
        model = Dao
    
    name = factory.Faker("company")
    description = factory.Faker("text", max_nb_chars=500)
    recommended = factory.Faker("boolean", chance_of_getting_true=25)


class WalletFactory(factory.django.DjangoModelFactory):
    """Factory for Wallet model"""
    
    class Meta:
        model = Wallet
    
    blockchain = factory.SubFactory(BlockchainFactory)
    address = factory.LazyFunction(lambda: f"0x{fake.sha256()[:40]}")
    name = factory.Faker("word")
    derived_name = None  # Will be auto-generated
    domains = factory.LazyFunction(
        lambda: {"ens": [f"{fake.word()}.eth"]} if fake.boolean(chance_of_getting_true=30) else None
    )
    recommended = factory.Faker("boolean", chance_of_getting_true=10)
    balance = factory.LazyFunction(
        lambda: str(fake.random_int(min=0, max=1000000000000000000))
    )
    status = factory.Iterator(["active", "inactive", "monitoring"])
    subnet = factory.Iterator(["mainnet", "testnet", "goerli", "sepolia"])
    description = factory.Faker("text", max_nb_chars=200)
    
    @factory.post_generation
    def generate_derived_name(self, create, extracted, **kwargs):
        """Generate derived name after creation"""
        if create and not self.derived_name:
            self.derived_name = self.generate_derived_name()
            self.save()


class TokenFactory(factory.django.DjangoModelFactory):
    """Factory for Token model"""
    
    class Meta:
        model = Token
    
    chain = factory.SubFactory(ChainFactory)
    name = factory.Faker("word")
    symbol = factory.LazyAttribute(lambda obj: obj.name.upper()[:10] if obj.name else "TKN")
    decimals = 18
    is_native = False
    contract_address = factory.LazyFunction(lambda: f"0x{fake.sha256()[:40]}")


class DaoSubscriptionFactory(factory.django.DjangoModelFactory):
    """Factory for DaoSubscription model"""
    
    class Meta:
        model = DaoSubscription
    
    name = factory.Faker("word")
    dao = factory.SubFactory(DaoFactory)
    user = factory.SubFactory('tests.factories.auth_factories.UserFactory')
    notifications_count = factory.Faker("random_int", min=0, max=100)


class WalletSubscriptionFactory(factory.django.DjangoModelFactory):
    """Factory for WalletSubscription model"""
    
    class Meta:
        model = WalletSubscription
    
    wallet = factory.SubFactory(WalletFactory)
    name = factory.Faker("word")
    user = factory.SubFactory('tests.factories.auth_factories.UserFactory')
    notifications_count = factory.Faker("random_int", min=0, max=100)


class DaoWalletFactory(factory.django.DjangoModelFactory):
    """Factory for DaoWallet model"""
    
    class Meta:
        model = DaoWallet
    
    dao = factory.SubFactory(DaoFactory)
    wallet = factory.SubFactory(WalletFactory)


class ImageFactory(factory.django.DjangoModelFactory):
    """Factory for Image model"""
    
    class Meta:
        model = Image
    
    url = factory.Faker("image_url")


class StoryFactory(factory.django.DjangoModelFactory):
    """Factory for Story model"""
    
    class Meta:
        model = Story
    
    title = factory.Faker("sentence", nb_words=6)
    description = factory.Faker("text", max_nb_chars=300)
    content = factory.Faker("text", max_nb_chars=1000)
    publication_date = factory.Faker("date_time_this_year", tzinfo=timezone.get_current_timezone())
    image_url = factory.Faker("image_url")
    url = factory.Faker("url")


class BlockchainStoryFactory(factory.django.DjangoModelFactory):
    """Factory for BlockchainStory model"""
    
    class Meta:
        model = BlockchainStory
    
    story = factory.SubFactory(StoryFactory)
    blockchain = factory.SubFactory(BlockchainFactory)


class TagFactory(factory.django.DjangoModelFactory):
    """Factory for Tag model"""
    
    class Meta:
        model = Tag
        django_get_or_create = ('name',)
    
    name = factory.Faker("word")


class WalletBalanceFactory(factory.django.DjangoModelFactory):
    """Factory for WalletBalance model"""
    
    class Meta:
        model = WalletBalance
    
    wallet = factory.SubFactory(WalletFactory)
    balance = factory.LazyFunction(
        lambda: str(fake.random_int(min=0, max=1000000000000000000))
    )
    token_price = factory.LazyFunction(
        lambda: str(fake.random_int(min=1000, max=5000))
    )
    fiat_value = factory.LazyFunction(
        lambda: str(fake.random_int(min=100, max=10000))
    )
    timestamp = factory.Faker("date_time_this_year", tzinfo=timezone.get_current_timezone())


# Utility functions for creating related objects
def create_wallet_with_balance_history(blockchain=None, **wallet_kwargs):
    """Create a wallet with balance history"""
    if blockchain is None:
        blockchain = BlockchainFactory()
    
    wallet = WalletFactory(blockchain=blockchain, **wallet_kwargs)
    
    # Create balance history
    balances = []
    for i in range(5):
        balance = WalletBalanceFactory(
            wallet=wallet,
            timestamp=timezone.now() - timedelta(days=i)
        )
        balances.append(balance)
    
    return wallet, balances


def create_dao_with_wallets(wallet_count=3, **dao_kwargs):
    """Create a DAO with associated wallets"""
    dao = DaoFactory(**dao_kwargs)
    
    wallets = []
    for _ in range(wallet_count):
        wallet = WalletFactory()
        DaoWalletFactory(dao=dao, wallet=wallet)
        wallets.append(wallet)
    
    return dao, wallets


def create_blockchain_ecosystem(blockchain_name="Ethereum"):
    """Create a complete blockchain ecosystem"""
    blockchain = BlockchainFactory(name=blockchain_name, symbol=blockchain_name.lower()[:3])
    chain = ChainFactory(name=blockchain_name.lower(), display_name=blockchain_name)
    
    # Create tokens
    tokens = [
        TokenFactory(chain=chain, name="USD Coin", symbol="USDC", decimals=6),
        TokenFactory(chain=chain, name="Wrapped Bitcoin", symbol="WBTC", decimals=8),
    ]
    
    # Create wallets
    wallets = [WalletFactory(blockchain=blockchain) for _ in range(3)]
    
    # Create DAOs
    daos = [DaoFactory() for _ in range(2)]
    
    # Associate DAOs with wallets
    for dao in daos:
        for wallet in wallets[:2]:  # Each DAO gets 2 wallets
            DaoWalletFactory(dao=dao, wallet=wallet)
    
    return {
        'blockchain': blockchain,
        'tokens': tokens,
        'wallets': wallets,
        'daos': daos,
    }


def create_story_with_blockchains(blockchain_count=2, **story_kwargs):
    """Create a story associated with multiple blockchains"""
    story = StoryFactory(**story_kwargs)
    
    blockchains = []
    for _ in range(blockchain_count):
        blockchain = BlockchainFactory()
        BlockchainStoryFactory(story=story, blockchain=blockchain)
        blockchains.append(blockchain)
    
    return story, blockchains
