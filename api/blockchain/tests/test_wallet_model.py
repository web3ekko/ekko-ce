"""
Tests for the Wallet model normalization and uniqueness.
"""

from django.test import TestCase
from django.db.utils import IntegrityError

from blockchain.models import Blockchain, Wallet


class WalletModelTest(TestCase):
    def setUp(self):
        self.blockchain = Blockchain.objects.create(
            symbol="eth",
            name="ethereum",
            chain_type="EVM",
        )

    def test_normalizes_evm_address_and_subnet(self):
        wallet = Wallet.objects.create(
            blockchain=self.blockchain,
            subnet=" MainNet ",
            address=f" 0x{'A' * 40} ",
            name="Test Wallet",
        )
        wallet.refresh_from_db()

        self.assertEqual(wallet.subnet, "mainnet")
        self.assertEqual(wallet.address, f"0x{'a' * 40}")

    def test_wallet_unique_per_network_subnet_address(self):
        address_mixed_case = f"0x{'A' * 40}"

        Wallet.objects.create(
            blockchain=self.blockchain,
            subnet="mainnet",
            address=address_mixed_case,
            name="Mainnet Wallet",
        )

        # Same address on a different subnet is allowed.
        Wallet.objects.create(
            blockchain=self.blockchain,
            subnet="testnet",
            address=address_mixed_case,
            name="Testnet Wallet",
        )

        # Same address on the same subnet is rejected (even if case differs).
        with self.assertRaises(IntegrityError):
            Wallet.objects.create(
                blockchain=self.blockchain,
                subnet=" MainNet ",
                address=f"0x{'a' * 40}",
                name="Duplicate Mainnet Wallet",
            )

