"""Tests for BlockchainSyncService."""
import pytest
import json
from unittest.mock import patch, MagicMock


class TestBlockchainSyncService:
    """Tests for BlockchainSyncService."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        from app.services.blockchain_sync_service import BlockchainSyncService
        BlockchainSyncService.reset_client()

        mock_client = MagicMock()
        with patch.object(BlockchainSyncService, 'get_redis_client', return_value=mock_client):
            yield mock_client

    @pytest.fixture
    def mock_node(self):
        """Create a mock BlockchainNode instance."""
        node = MagicMock()
        node.chain_id = "1"
        node.chain_name = "Ethereum Mainnet"
        node.network = "ethereum"
        node.subnet = "mainnet"
        node.vm_type = "EVM"
        node.rpc_url = "https://mainnet.infura.io/v3/test"
        node.ws_url = "wss://mainnet.infura.io/ws/v3/test"
        node.enabled = True
        node.get_provider_config.return_value = {
            "provider_name": "newheads-evm",
            "chain_id": "1",
            "chain_name": "Ethereum Mainnet",
            "network": "ethereum",
            "subnet": "mainnet",
            "vm_type": "evm",
            "rpc_url": "https://mainnet.infura.io/v3/test",
            "ws_url": "wss://mainnet.infura.io/ws/v3/test",
            "enabled": True,
        }
        return node

    def test_get_provider_config_key_evm(self):
        """Test Redis key generation for EVM chain."""
        from app.services.blockchain_sync_service import BlockchainSyncService

        key = BlockchainSyncService.get_provider_config_key("EVM", "1")
        assert key == "provider:config:newheads-evm:1"

    def test_get_provider_config_key_svm(self):
        """Test Redis key generation for SVM (Solana) chain."""
        from app.services.blockchain_sync_service import BlockchainSyncService

        key = BlockchainSyncService.get_provider_config_key("SVM", "mainnet-beta")
        assert key == "provider:config:newheads-svm:mainnet-beta"

    def test_get_provider_config_key_lowercase_conversion(self):
        """Test that VM type is converted to lowercase."""
        from app.services.blockchain_sync_service import BlockchainSyncService

        key = BlockchainSyncService.get_provider_config_key("COSMOS", "cosmoshub-4")
        assert key == "provider:config:newheads-cosmos:cosmoshub-4"

    def test_sync_node_to_redis_success(self, mock_redis, mock_node):
        """Test successful sync of node to Redis."""
        from app.services.blockchain_sync_service import BlockchainSyncService

        result = BlockchainSyncService.sync_node_to_redis(mock_node)

        assert result is True
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert call_args[0][0] == "provider:config:newheads-evm:1"

        # Verify the JSON payload contains expected fields
        stored_config = json.loads(call_args[0][1])
        assert stored_config["provider_name"] == "newheads-evm"
        assert stored_config["chain_id"] == "1"
        assert stored_config["enabled"] is True

    def test_sync_node_to_redis_redis_error(self, mock_redis, mock_node):
        """Test graceful handling of Redis errors during sync."""
        from app.services.blockchain_sync_service import BlockchainSyncService

        mock_redis.set.side_effect = Exception("Connection refused")

        result = BlockchainSyncService.sync_node_to_redis(mock_node)

        assert result is False

    def test_remove_node_from_redis_success(self, mock_redis):
        """Test successful removal of node from Redis."""
        from app.services.blockchain_sync_service import BlockchainSyncService

        result = BlockchainSyncService.remove_node_from_redis("EVM", "1")

        assert result is True
        mock_redis.delete.assert_called_once_with("provider:config:newheads-evm:1")

    def test_remove_node_from_redis_error(self, mock_redis):
        """Test graceful handling of Redis errors during removal."""
        from app.services.blockchain_sync_service import BlockchainSyncService

        mock_redis.delete.side_effect = Exception("Connection refused")

        result = BlockchainSyncService.remove_node_from_redis("EVM", "1")

        assert result is False

    def test_get_node_config_from_redis_success(self, mock_redis):
        """Test successful retrieval of config from Redis."""
        from app.services.blockchain_sync_service import BlockchainSyncService

        expected_config = {
            "provider_name": "newheads-evm",
            "chain_id": "1",
            "chain_name": "Ethereum Mainnet",
            "enabled": True,
        }
        mock_redis.get.return_value = json.dumps(expected_config)

        result = BlockchainSyncService.get_node_config_from_redis("EVM", "1")

        assert result == expected_config
        mock_redis.get.assert_called_once_with("provider:config:newheads-evm:1")

    def test_get_node_config_from_redis_not_found(self, mock_redis):
        """Test retrieval when config doesn't exist."""
        from app.services.blockchain_sync_service import BlockchainSyncService

        mock_redis.get.return_value = None

        result = BlockchainSyncService.get_node_config_from_redis("EVM", "999")

        assert result is None

    def test_get_node_config_from_redis_error(self, mock_redis):
        """Test graceful handling of Redis errors during retrieval."""
        from app.services.blockchain_sync_service import BlockchainSyncService

        mock_redis.get.side_effect = Exception("Connection refused")

        result = BlockchainSyncService.get_node_config_from_redis("EVM", "1")

        assert result is None

    def test_list_all_provider_configs_success(self, mock_redis):
        """Test listing all provider config keys."""
        from app.services.blockchain_sync_service import BlockchainSyncService

        mock_redis.keys.return_value = [
            "provider:config:newheads-evm:1",
            "provider:config:newheads-evm:137",
            "provider:config:newheads-svm:mainnet-beta",
        ]

        result = BlockchainSyncService.list_all_provider_configs()

        assert len(result) == 3
        assert "provider:config:newheads-evm:1" in result
        mock_redis.keys.assert_called_once_with("provider:config:newheads-*")

    def test_list_all_provider_configs_empty(self, mock_redis):
        """Test listing when no provider configs exist."""
        from app.services.blockchain_sync_service import BlockchainSyncService

        mock_redis.keys.return_value = []

        result = BlockchainSyncService.list_all_provider_configs()

        assert result == []

    def test_list_all_provider_configs_error(self, mock_redis):
        """Test graceful handling of Redis errors during listing."""
        from app.services.blockchain_sync_service import BlockchainSyncService

        mock_redis.keys.side_effect = Exception("Connection refused")

        result = BlockchainSyncService.list_all_provider_configs()

        assert result == []


class TestBlockchainSyncSignals:
    """Tests for blockchain sync signals."""

    @pytest.fixture
    def mock_sync_service(self):
        """Mock the BlockchainSyncService."""
        with patch('app.services.blockchain_sync_service.BlockchainSyncService') as mock_service:
            yield mock_service

    def test_signal_syncs_enabled_node_on_save(self, mock_sync_service):
        """Test that saving an enabled node triggers sync."""
        from app.signals.blockchain_sync_signals import sync_blockchain_node_to_redis

        mock_node = MagicMock()
        mock_node.enabled = True
        mock_node.chain_id = "1"
        mock_node.chain_name = "Ethereum Mainnet"

        sync_blockchain_node_to_redis(
            sender=MagicMock(),
            instance=mock_node,
            created=True
        )

        mock_sync_service.sync_node_to_redis.assert_called_once_with(mock_node)

    def test_signal_removes_disabled_node_on_save(self, mock_sync_service):
        """Test that saving a disabled node triggers removal."""
        from app.signals.blockchain_sync_signals import sync_blockchain_node_to_redis

        mock_node = MagicMock()
        mock_node.enabled = False
        mock_node.chain_id = "1"
        mock_node.chain_name = "Ethereum Mainnet"
        mock_node.vm_type = "EVM"

        sync_blockchain_node_to_redis(
            sender=MagicMock(),
            instance=mock_node,
            created=False
        )

        mock_sync_service.remove_node_from_redis.assert_called_once_with("EVM", "1")

    def test_signal_removes_node_on_delete(self, mock_sync_service):
        """Test that deleting a node triggers removal."""
        from app.signals.blockchain_sync_signals import remove_blockchain_node_from_redis

        mock_node = MagicMock()
        mock_node.chain_id = "1"
        mock_node.chain_name = "Ethereum Mainnet"
        mock_node.vm_type = "EVM"

        remove_blockchain_node_from_redis(
            sender=MagicMock(),
            instance=mock_node
        )

        mock_sync_service.remove_node_from_redis.assert_called_once_with("EVM", "1")

    def test_signal_handles_sync_error_gracefully(self, mock_sync_service):
        """Test that signal handles sync errors without raising."""
        from app.signals.blockchain_sync_signals import sync_blockchain_node_to_redis

        mock_sync_service.sync_node_to_redis.side_effect = Exception("Redis error")

        mock_node = MagicMock()
        mock_node.enabled = True
        mock_node.chain_id = "1"

        # Should not raise
        sync_blockchain_node_to_redis(
            sender=MagicMock(),
            instance=mock_node,
            created=True
        )


class TestBlockchainNodeModel:
    """Tests for BlockchainNode model provider config method."""

    def test_get_provider_config_returns_correct_format(self):
        """Test that get_provider_config returns correct format."""
        from app.models.blockchain import BlockchainNode

        node = BlockchainNode(
            chain_id="1",
            chain_name="Ethereum Mainnet",
            network="ethereum",
            subnet="mainnet",
            vm_type="EVM",
            rpc_url="https://mainnet.infura.io/v3/test",
            ws_url="wss://mainnet.infura.io/ws/v3/test",
            enabled=True,
        )

        config = node.get_provider_config()

        assert config["provider_name"] == "newheads-evm"
        assert config["chain_id"] == "1"
        assert config["chain_name"] == "Ethereum Mainnet"
        assert config["network"] == "ethereum"
        assert config["subnet"] == "mainnet"
        assert config["vm_type"] == "evm"  # lowercase
        assert config["rpc_url"] == "https://mainnet.infura.io/v3/test"
        assert config["ws_url"] == "wss://mainnet.infura.io/ws/v3/test"
        assert config["enabled"] is True

    def test_get_provider_config_vm_type_lowercase(self):
        """Test that VM type is converted to lowercase in config."""
        from app.models.blockchain import BlockchainNode

        node = BlockchainNode(
            chain_id="mainnet-beta",
            chain_name="Solana Mainnet",
            network="solana",
            subnet="mainnet",
            vm_type="SVM",
            rpc_url="https://api.mainnet-beta.solana.com",
            ws_url="wss://api.mainnet-beta.solana.com",
            enabled=True,
        )

        config = node.get_provider_config()

        assert config["provider_name"] == "newheads-svm"
        assert config["vm_type"] == "svm"
