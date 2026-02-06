"""
Management command to seed realistic test data for E2E Playwright testing.

Usage:
    python manage.py seed_realistic_data
    python manage.py seed_realistic_data --users 5 --wallets-per-user 50 --alerts-per-user 20
    python manage.py seed_realistic_data --clear --verbose

Creates realistic test data:
- Multiple test users with different personas
- Wallets across blockchains (ETH, Polygon, Arbitrum, BTC, Solana)
- Alert templates (public/private)
- Alert instances subscribed to wallets
- Wallet subscriptions
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
import random
import hashlib
import uuid

User = get_user_model()


class Command(BaseCommand):
    help = 'Seed realistic test data for E2E Playwright testing'

    # Realistic blockchain configurations
    BLOCKCHAINS = [
        {'name': 'Ethereum', 'symbol': 'eth', 'chain_type': 'EVM', 'subnets': ['mainnet', 'sepolia', 'goerli']},
        {'name': 'Polygon', 'symbol': 'matic', 'chain_type': 'EVM', 'subnets': ['mainnet', 'mumbai']},
        {'name': 'Arbitrum', 'symbol': 'arb', 'chain_type': 'EVM', 'subnets': ['mainnet', 'goerli']},
        {'name': 'Base', 'symbol': 'base', 'chain_type': 'EVM', 'subnets': ['mainnet']},
        {'name': 'Optimism', 'symbol': 'op', 'chain_type': 'EVM', 'subnets': ['mainnet']},
        {'name': 'Bitcoin', 'symbol': 'btc', 'chain_type': 'Bitcoin', 'subnets': ['mainnet', 'testnet']},
        {'name': 'Solana', 'symbol': 'sol', 'chain_type': 'Solana', 'subnets': ['mainnet-beta', 'devnet']},
    ]

    # Test user personas for different use cases
    USER_PERSONAS = [
        {
            'email': 'investor@test.ekko.zone',
            'first_name': 'Alex',
            'last_name': 'Investor',
            'persona': 'crypto_investor',
        },
        {
            'email': 'developer@test.ekko.zone',
            'first_name': 'Sam',
            'last_name': 'Protocol',
            'persona': 'protocol_developer',
        },
        {
            'email': 'analyst@test.ekko.zone',
            'first_name': 'Jordan',
            'last_name': 'Analyst',
            'persona': 'blockchain_analyst',
        },
        {
            'email': 'teamlead@test.ekko.zone',
            'first_name': 'Morgan',
            'last_name': 'Leader',
            'persona': 'team_lead',
        },
        {
            'email': 'provider@test.ekko.zone',
            'first_name': 'Casey',
            'last_name': 'Wallet',
            'persona': 'wallet_provider',
        },
    ]

    # Alert template configurations
    ALERT_TEMPLATES = [
        {
            'name': 'Large Transfer Alert',
            'description': 'Alert when transfers exceed threshold',
            'event_type': 'ACCOUNT_EVENT',
            'sub_event': 'BALANCE_THRESHOLD',
            'is_public': True,
        },
        {
            'name': 'Token Swap Alert',
            'description': 'Alert on DEX swaps for specific tokens',
            'event_type': 'CONTRACT_INTERACTION',
            'sub_event': 'SWAP',
            'is_public': True,
        },
        {
            'name': 'Whale Movement Alert',
            'description': 'Track large wallet movements',
            'event_type': 'ACCOUNT_EVENT',
            'sub_event': 'NATIVE_SEND',
            'is_public': True,
        },
        {
            'name': 'Liquidation Alert',
            'description': 'Alert on DeFi liquidations',
            'event_type': 'PROTOCOL_EVENT',
            'sub_event': 'LIQUIDATION',
            'is_public': True,
        },
        {
            'name': 'NFT Purchase Alert',
            'description': 'Alert on NFT marketplace purchases',
            'event_type': 'CONTRACT_INTERACTION',
            'sub_event': 'TOKEN_TRANSFER',
            'is_public': False,
        },
    ]

    # Realistic wallet names
    WALLET_NAMES = [
        'Main Trading', 'Cold Storage', 'DeFi Yield', 'Staking Rewards',
        'NFT Collection', 'DAOs Treasury', 'Research Fund', 'Development',
        'Marketing', 'Operations', 'Personal', 'Team Vesting',
        'Liquidity Pool', 'Bridge Funds', 'Gas Reserve', 'Emergency',
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            '--users',
            type=int,
            default=5,
            help='Number of test users to create (default: 5)',
        )
        parser.add_argument(
            '--wallets-per-user',
            type=int,
            default=50,
            help='Number of wallets per user (default: 50)',
        )
        parser.add_argument(
            '--alerts-per-user',
            type=int,
            default=20,
            help='Number of alert instances per user (default: 20)',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing test data before seeding',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed progress',
        )

    def handle(self, *args, **options):
        user_count = options['users']
        wallets_per_user = options['wallets_per_user']
        alerts_per_user = options['alerts_per_user']
        verbose = options['verbose']

        self.stdout.write(self.style.HTTP_INFO('\n🌱 Ekko E2E Test Data Seeder'))
        self.stdout.write(f'   Users: {user_count}')
        self.stdout.write(f'   Wallets per user: {wallets_per_user}')
        self.stdout.write(f'   Alerts per user: {alerts_per_user}')
        self.stdout.write('')

        # Import models here to avoid circular imports
        from blockchain.models import Blockchain, Wallet, WalletSubscription
        from app.models.alerts import AlertTemplate, AlertInstance

        # Clear existing test data if requested
        if options['clear']:
            self._clear_test_data(verbose)

        with transaction.atomic():
            # Step 1: Create blockchains
            blockchains = self._create_blockchains(Blockchain, verbose)

            # Step 2: Create users
            users = self._create_users(user_count, verbose)

            # Step 3: Create alert templates
            templates = self._create_alert_templates(AlertTemplate, users[0], verbose)

            # Step 4: Create wallets for each user
            all_wallets = []
            for user in users:
                wallets = self._create_wallets(
                    Wallet, user, blockchains, wallets_per_user, verbose
                )
                all_wallets.extend(wallets)

                # Create wallet subscriptions
                self._create_wallet_subscriptions(
                    WalletSubscription, user, wallets, verbose
                )

            # Step 5: Create alert instances for each user
            for user in users:
                user_wallets = [w for w in all_wallets if w.created_by_id == user.id] if hasattr(Wallet, 'created_by') else all_wallets[:wallets_per_user]
                self._create_alert_instances(
                    AlertInstance, user, templates, user_wallets, alerts_per_user, verbose
                )

        # Summary
        self._print_summary(users, all_wallets, templates, alerts_per_user)

    def _clear_test_data(self, verbose):
        """Clear existing test data"""
        from blockchain.models import Wallet, WalletSubscription
        from app.models.alerts import AlertTemplate, AlertInstance

        if verbose:
            self.stdout.write('Clearing existing test data...')

        # Clear test alerts
        deleted_alerts = AlertInstance.objects.filter(
            user__email__endswith='@test.ekko.zone'
        ).delete()[0]

        # Clear test templates
        deleted_templates = AlertTemplate.objects.filter(
            created_by__email__endswith='@test.ekko.zone'
        ).delete()[0]

        # Clear test wallet subscriptions
        deleted_subs = WalletSubscription.objects.filter(
            user__email__endswith='@test.ekko.zone'
        ).delete()[0]

        # Clear test wallets (only if they have a name that matches our patterns)
        deleted_wallets = Wallet.objects.filter(
            name__in=self.WALLET_NAMES
        ).delete()[0]

        # Clear test users
        deleted_users = User.objects.filter(
            email__endswith='@test.ekko.zone'
        ).delete()[0]

        self.stdout.write(self.style.WARNING(
            f'Cleared: {deleted_users} users, {deleted_wallets} wallets, '
            f'{deleted_subs} subscriptions, {deleted_alerts} alerts, {deleted_templates} templates'
        ))

    def _create_blockchains(self, Blockchain, verbose):
        """Create or get blockchains"""
        if verbose:
            self.stdout.write('Creating blockchains...')

        blockchains = []
        for bc_config in self.BLOCKCHAINS:
            blockchain, created = Blockchain.objects.get_or_create(
                symbol=bc_config['symbol'],
                defaults={
                    'name': bc_config['name'],
                    'chain_type': bc_config['chain_type'],
                }
            )
            blockchain._subnets = bc_config['subnets']  # Store subnets for later use
            blockchains.append(blockchain)
            if verbose and created:
                self.stdout.write(f'  + {bc_config["name"]}')

        return blockchains

    def _create_users(self, count, verbose):
        """Create test users"""
        if verbose:
            self.stdout.write('Creating users...')

        users = []
        for i, persona in enumerate(self.USER_PERSONAS[:count]):
            user, created = User.objects.get_or_create(
                email=persona['email'],
                defaults={
                    'username': persona['email'],
                    'first_name': persona['first_name'],
                    'last_name': persona['last_name'],
                    'is_active': True,
                    'is_email_verified': True,
                    'firebase_uid': f'test_{uuid.uuid4().hex[:12]}',
                }
            )
            if created:
                user.set_unusable_password()
                user.save()
                if verbose:
                    self.stdout.write(f'  + {persona["email"]} ({persona["persona"]})')
            users.append(user)

        # Create additional generic users if needed
        for i in range(count - len(self.USER_PERSONAS)):
            email = f'testuser{i+1}@test.ekko.zone'
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'username': email,
                    'first_name': f'Test{i+1}',
                    'last_name': 'User',
                    'is_active': True,
                    'is_email_verified': True,
                    'firebase_uid': f'test_{uuid.uuid4().hex[:12]}',
                }
            )
            if created:
                user.set_unusable_password()
                user.save()
            users.append(user)

        return users

    def _create_alert_templates(self, AlertTemplate, creator, verbose):
        """Create alert templates"""
        if verbose:
            self.stdout.write('Creating alert templates...')

        templates = []
        for tmpl_config in self.ALERT_TEMPLATES:
            event_type = str(tmpl_config.get("event_type") or "ACCOUNT_EVENT").strip()
            alert_type = self._infer_alert_type_from_event_type(event_type)
            template, created = AlertTemplate.objects.get_or_create(
                name=tmpl_config['name'],
                created_by=creator,
                defaults={
                    'description': tmpl_config['description'],
                    'event_type': tmpl_config['event_type'],
                    'sub_event': tmpl_config['sub_event'],
                    'is_public': tmpl_config['is_public'],
                    'is_verified': tmpl_config['is_public'],
                    'nl_template': f'Alert me when {tmpl_config["name"].lower()} triggers',
                    'spec': self._generate_template_spec_v1(tmpl_config),
                    'alert_type': alert_type,
                    'scope_chain': 'ethereum',
                    'scope_network': 'mainnet',
                    'version': 1,
                    'usage_count': random.randint(10, 500) if tmpl_config['is_public'] else 0,
                }
            )
            templates.append(template)
            if verbose and created:
                self.stdout.write(f'  + {tmpl_config["name"]}')

        return templates

    def _infer_alert_type_from_event_type(self, event_type: str) -> str:
        event_type = (event_type or "").strip().upper()
        if event_type == "CONTRACT_INTERACTION":
            return "contract"
        if event_type in {"PROTOCOL_EVENT", "ANOMALY_EVENT"}:
            return "network"
        if event_type == "ASSET_EVENT":
            return "token"
        return "wallet"

    def _generate_template_spec_v1(self, tmpl_config: dict) -> dict:
        """Generate an AlertTemplateIR v1 execution spec for a seed template."""
        name = str(tmpl_config.get("name") or "Seed Alert Template").strip()
        description = str(tmpl_config.get("description") or name).strip()
        threshold_default = random.randint(1_000, 250_000)

        return {
            "version": "v1",
            "name": name,
            "description": description,
            "variables": [
                {
                    "id": "threshold",
                    "type": "decimal",
                    "label": "Threshold",
                    "description": "Threshold value for triggering the alert",
                    "required": True,
                    "default": threshold_default,
                    "validation": {"min": 0},
                }
            ],
            "trigger": {
                "chain_id": 1,
                "tx_type": {"primary": ["any"], "subtypes": []},
                "from": {"any_of": [], "labels": [], "groups": [], "not": []},
                "to": {"any_of": [], "labels": [], "groups": [], "not": []},
                "method": {"selector_any_of": [], "name_any_of": [], "required": False},
            },
            "datasources": [],
            "enrichments": [],
            "conditions": {
                "all": [{"op": "gt", "left": "$.tx.value_native", "right": "{{threshold}}"}],
                "any": [],
                "not": [],
            },
            "action": {"cooldown_secs": 60},
            "warnings": ["seed_data"],
        }

    def _create_wallets(self, Wallet, user, blockchains, count, verbose):
        """Create wallets for a user"""
        if verbose:
            self.stdout.write(f'Creating {count} wallets for {user.email}...')

        wallets = []
        for i in range(count):
            blockchain = random.choice(blockchains)
            subnet = random.choice(getattr(blockchain, '_subnets', ['mainnet']))
            name = f'{random.choice(self.WALLET_NAMES)} {i+1}'

            # Generate realistic address based on chain type
            address = self._generate_address(blockchain.chain_type)

            wallet = Wallet.objects.create(
                blockchain=blockchain,
                address=address,
                name=name,
                subnet=subnet,
                status=random.choice(['active', 'active', 'active', 'monitoring']),
                balance=str(random.randint(0, 10**18)),
                description=f'Test wallet for {user.email}',
                recommended=random.random() < 0.1,  # 10% chance
            )
            wallets.append(wallet)

        return wallets

    def _generate_address(self, chain_type):
        """Generate a realistic blockchain address"""
        random_bytes = hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()

        if chain_type == 'EVM':
            return f'0x{random_bytes[:40]}'
        elif chain_type == 'Bitcoin':
            # Bitcoin P2PKH style
            return f'1{random_bytes[:33]}'
        elif chain_type == 'Solana':
            # Solana base58-style (simplified)
            import base64
            return base64.b64encode(bytes.fromhex(random_bytes[:32])).decode()[:44]
        else:
            return f'0x{random_bytes[:40]}'

    def _create_wallet_subscriptions(self, WalletSubscription, user, wallets, verbose):
        """Create wallet subscriptions for a user"""
        # Subscribe to 60% of wallets
        subscribed_wallets = random.sample(wallets, int(len(wallets) * 0.6))

        for wallet in subscribed_wallets:
            WalletSubscription.objects.get_or_create(
                wallet=wallet,
                user=user,
                defaults={
                    'name': f'{wallet.name} Subscription',
                    'notifications_count': random.randint(0, 50),
                }
            )

    def _create_alert_instances(self, AlertInstance, user, templates, wallets, count, verbose):
        """Create alert instances for a user"""
        if verbose:
            self.stdout.write(f'Creating {count} alerts for {user.email}...')

        trigger_types = ['event_driven', 'periodic', 'one_time']
        cron_expressions = ['*/5 * * * *', '0 * * * *', '0 0 * * *', '0 9 * * 1']

        for i in range(count):
            template = random.choice(templates) if templates else None
            trigger_type = random.choice(trigger_types)
            wallet = random.choice(wallets) if wallets else None

            trigger_config = self._generate_trigger_config(trigger_type, cron_expressions)

            spec = {
                'scope': {
                    'chains': ['ethereum-mainnet'],
                    'addresses': [wallet.address] if wallet else [],
                },
                'trigger': {
                    'mode': 'event' if trigger_type == 'event_driven' else 'schedule',
                    'events': ['transfer', 'swap'] if trigger_type == 'event_driven' else [],
                },
                'condition': {
                    'type': 'threshold',
                    'field': 'value',
                    'operator': '>',
                    'value': str(random.randint(1000, 1000000)),
                }
            }

            AlertInstance.objects.create(
                name=f'Alert {i+1} - {trigger_type.replace("_", " ").title()}',
                nl_description=f'Alert for {wallet.name if wallet else "any wallet"} activity',
                user=user,
                template=template if random.random() < 0.7 else None,  # 70% use templates
                template_params={
                    'wallet': wallet.address if wallet else '0x0',
                    'threshold': str(random.randint(1000, 1000000)),
                    'chain': 'ethereum-mainnet',
                } if template else None,
                trigger_type=trigger_type,
                trigger_config=trigger_config,
                enabled=random.random() < 0.8,  # 80% enabled
                event_type=template.event_type if template else 'ACCOUNT_EVENT',
                sub_event=template.sub_event if template else 'BALANCE_THRESHOLD',
                sub_event_confidence=random.uniform(0.7, 1.0),
                version=1,
            )

    def _generate_trigger_config(self, trigger_type, cron_expressions):
        """Generate trigger config based on type"""
        if trigger_type == 'event_driven':
            return {
                'chains': ['ethereum', 'polygon'],
                'event_types': ['transfer', 'swap', 'liquidity_add'],
                'priority': random.choice(['normal', 'high']),
                'dedup_window_seconds': 300,
            }
        elif trigger_type == 'periodic':
            return {
                'cron_expression': random.choice(cron_expressions),
                'timezone': 'UTC',
                'interval_seconds': random.choice([60, 300, 900, 3600]),
            }
        elif trigger_type == 'one_time':
            scheduled_time = timezone.now() + timedelta(hours=random.randint(1, 48))
            return {
                'scheduled_time': scheduled_time.isoformat(),
                'timezone': 'UTC',
                'reset_allowed': True,
            }
        return {}

    def _print_summary(self, users, wallets, templates, alerts_per_user):
        """Print seeding summary"""
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('✅ Data seeding complete!'))
        self.stdout.write('')
        self.stdout.write(f'  📊 Summary:')
        self.stdout.write(f'     Users created: {len(users)}')
        self.stdout.write(f'     Wallets created: {len(wallets)}')
        self.stdout.write(f'     Alert templates: {len(templates)}')
        self.stdout.write(f'     Alert instances: ~{len(users) * alerts_per_user}')
        self.stdout.write('')
        self.stdout.write('  🔑 Test users:')
        for user in users:
            self.stdout.write(f'     - {user.email}')
        self.stdout.write('')
        self.stdout.write(self.style.HTTP_INFO(
            '  💡 Run E2E tests with: pytest tests/e2e/ -v'
        ))
