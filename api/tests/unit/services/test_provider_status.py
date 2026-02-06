"""Tests for ProviderStatusService."""
import pytest
import json
from unittest.mock import patch, MagicMock


class TestProviderStatusService:
    """Tests for ProviderStatusService."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        with patch('app.services.provider_status.redis') as mock_redis_module:
            mock_client = MagicMock()
            mock_redis_module.from_url.return_value = mock_client
            yield mock_client

    def test_list_providers_success(self, mock_redis):
        """Test listing providers from registry."""
        from app.services.provider_status import ProviderStatusService
        mock_redis.hgetall.return_value = {'newheads-evm-pod1': 'evm'}

        service = ProviderStatusService()
        providers = service.list_providers()

        assert providers == [('newheads-evm-pod1', 'evm')]
        mock_redis.hgetall.assert_called_once_with('provider:registry')

    def test_list_providers_empty(self, mock_redis):
        """Test listing providers when none registered."""
        from app.services.provider_status import ProviderStatusService
        mock_redis.hgetall.return_value = {}

        service = ProviderStatusService()
        providers = service.list_providers()

        assert providers == []

    def test_list_providers_redis_error(self, mock_redis):
        """Test graceful handling of Redis errors."""
        from app.services.provider_status import ProviderStatusService
        mock_redis.hgetall.side_effect = Exception("Connection refused")

        service = ProviderStatusService()
        providers = service.list_providers()

        assert providers == []

    def test_get_provider_status_success(self, mock_redis):
        """Test getting a provider's status."""
        from app.services.provider_status import ProviderStatusService
        mock_status = {
            'provider_id': 'newheads-evm-pod1',
            'provider_type': 'evm',
            'overall_health': 'healthy',
            'subscriptions': {}
        }
        mock_redis.get.return_value = json.dumps(mock_status)

        service = ProviderStatusService()
        status = service.get_provider_status('newheads-evm-pod1')

        assert status == mock_status
        mock_redis.get.assert_called_once_with('provider:status:newheads-evm-pod1')

    def test_get_provider_status_not_found(self, mock_redis):
        """Test handling of missing provider status."""
        from app.services.provider_status import ProviderStatusService
        mock_redis.get.return_value = None

        service = ProviderStatusService()
        status = service.get_provider_status('nonexistent')

        assert status is None

    def test_get_provider_status_redis_error(self, mock_redis):
        """Test graceful handling of Redis errors when getting status."""
        from app.services.provider_status import ProviderStatusService
        mock_redis.get.side_effect = Exception("Connection refused")

        service = ProviderStatusService()
        status = service.get_provider_status('newheads-evm-pod1')

        assert status is None

    def test_get_all_provider_statuses(self, mock_redis):
        """Test getting all provider statuses."""
        from app.services.provider_status import ProviderStatusService

        # Mock registry response
        mock_redis.hgetall.return_value = {
            'newheads-evm-pod1': 'evm',
            'newheads-evm-pod2': 'evm'
        }

        # Mock status responses
        mock_status1 = {
            'provider_id': 'newheads-evm-pod1',
            'provider_type': 'evm',
            'overall_health': 'healthy',
            'subscriptions': {}
        }
        mock_status2 = {
            'provider_id': 'newheads-evm-pod2',
            'provider_type': 'evm',
            'overall_health': 'degraded',
            'subscriptions': {}
        }

        def get_side_effect(key):
            if key == 'provider:status:newheads-evm-pod1':
                return json.dumps(mock_status1)
            elif key == 'provider:status:newheads-evm-pod2':
                return json.dumps(mock_status2)
            return None

        mock_redis.get.side_effect = get_side_effect

        service = ProviderStatusService()
        statuses = service.get_all_provider_statuses()

        assert len(statuses) == 2
        assert mock_status1 in statuses
        assert mock_status2 in statuses


class TestDashboardNetworkStatusView:
    """Tests for DashboardNetworkStatusView helper methods."""

    def test_calculate_health_score_active(self):
        """Test health score for active subscription."""
        from app.views.dashboard_views import DashboardNetworkStatusView

        view = DashboardNetworkStatusView()
        sub = {'state': 'active', 'metrics': {'connection_errors': 0, 'processing_errors': 0}}

        score = view._calculate_health_score(sub)
        assert score == 100

    def test_calculate_health_score_reconnecting(self):
        """Test health score for reconnecting subscription."""
        from app.views.dashboard_views import DashboardNetworkStatusView

        view = DashboardNetworkStatusView()
        sub = {'state': 'reconnecting', 'metrics': {'connection_errors': 0, 'processing_errors': 0}}

        score = view._calculate_health_score(sub)
        assert score == 70

    def test_calculate_health_score_error(self):
        """Test health score for error subscription."""
        from app.views.dashboard_views import DashboardNetworkStatusView

        view = DashboardNetworkStatusView()
        sub = {'state': 'error', 'metrics': {'connection_errors': 0, 'processing_errors': 0}}

        score = view._calculate_health_score(sub)
        assert score == 0

    def test_calculate_health_score_with_errors(self):
        """Test health score is reduced by errors."""
        from app.views.dashboard_views import DashboardNetworkStatusView

        view = DashboardNetworkStatusView()
        sub = {'state': 'active', 'metrics': {'connection_errors': 5, 'processing_errors': 3}}

        score = view._calculate_health_score(sub)
        # 100 base - (5+3)*2 = 100 - 16 = 84
        assert score == 84

    def test_calculate_health_score_max_penalty(self):
        """Test health score penalty is capped at 30."""
        from app.views.dashboard_views import DashboardNetworkStatusView

        view = DashboardNetworkStatusView()
        sub = {'state': 'active', 'metrics': {'connection_errors': 50, 'processing_errors': 50}}

        score = view._calculate_health_score(sub)
        # 100 base - 30 max penalty = 70
        assert score == 70

    def test_transform_subscription(self):
        """Test transformation of subscription to network format."""
        from app.views.dashboard_views import DashboardNetworkStatusView

        view = DashboardNetworkStatusView()
        provider = {
            'provider_id': 'newheads-evm-pod1',
            'provider_type': 'evm'
        }
        sub = {
            'chain_name': 'Ethereum Mainnet',
            'state': 'active',
            'last_block': {
                'number': 19283746,
                'received_at': '2024-01-15T10:30:45Z'
            },
            'metrics': {
                'avg_latency_ms': 245.3,
                'blocks_received': 12847,
                'connection_errors': 2,
                'processing_errors': 0
            }
        }

        result = view._transform_subscription(provider, 'ethereum-mainnet', sub)

        assert result['id'] == 'ethereum-mainnet'
        assert result['name'] == 'Ethereum Mainnet'
        assert result['status'] == 'operational'
        assert result['provider_id'] == 'newheads-evm-pod1'
        assert result['provider_type'] == 'evm'
        assert result['block_height'] == 19283746
        assert result['avg_latency_ms'] == 245.3
        assert result['blocks_received'] == 12847
        assert result['connection_errors'] == 2
        assert result['health_score'] == 96  # 100 - 2*2 = 96
