"""
Unit tests for Analytics Newsfeed API endpoint.

Tests the newsfeed_transactions endpoint that returns blockchain transactions
for wallets that a user monitors via alerts.
"""
import pytest
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from app.models.alerts import AlertInstance, AlertType
from app.views.analytics_views import (
    _get_user_monitored_addresses,
    _parse_target_keys,
    CHAIN_CODE_TO_NAME,
)
from tests.factories.auth_factories import UserFactory
from tests.factories.alert_factories import AlertInstanceFactory


@pytest.fixture
def api_client():
    """Create an API client for testing."""
    return APIClient()


@pytest.fixture
def authenticated_client(api_client):
    """Create an authenticated API client."""
    user = UserFactory()
    api_client.force_authenticate(user=user)
    return api_client, user


@pytest.fixture
def mock_ducklake_service():
    """Mock the DuckLake service for testing."""
    with patch("app.views.analytics_views.get_ducklake_service") as mock:
        service = MagicMock()
        mock.return_value = service
        yield service


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestParseTargetKeys:
    """Tests for _parse_target_keys helper function."""

    def test_parse_single_ethereum_address(self):
        """Test parsing a single Ethereum address."""
        keys = ["ETH:mainnet:0x742d35cc6634c0532925a3b844bc9e7fe3c45bf3"]
        result = _parse_target_keys(keys)

        assert "ethereum_mainnet" in result
        assert len(result["ethereum_mainnet"]) == 1
        assert result["ethereum_mainnet"][0] == "0x742d35cc6634c0532925a3b844bc9e7fe3c45bf3"

    def test_parse_multiple_chains(self):
        """Test parsing addresses from multiple chains."""
        keys = [
            "ETH:mainnet:0x123",
            "SOL:mainnet:ABC123",
            "MATIC:mainnet:0x456",
        ]
        result = _parse_target_keys(keys)

        assert len(result) == 3
        assert "ethereum_mainnet" in result
        assert "solana_mainnet" in result
        assert "polygon_mainnet" in result

    def test_parse_with_chain_filter(self):
        """Test parsing with chain filter applied."""
        keys = [
            "ETH:mainnet:0x123",
            "SOL:mainnet:ABC123",
            "MATIC:mainnet:0x456",
        ]
        result = _parse_target_keys(keys, chain_filter="ethereum_mainnet,solana_mainnet")

        assert len(result) == 2
        assert "ethereum_mainnet" in result
        assert "solana_mainnet" in result
        assert "polygon_mainnet" not in result

    def test_parse_deduplicates_addresses(self):
        """Test that duplicate addresses are removed."""
        keys = [
            "ETH:mainnet:0x123",
            "ETH:mainnet:0x123",  # Duplicate
            "ETH:mainnet:0x456",
        ]
        result = _parse_target_keys(keys)

        assert len(result["ethereum_mainnet"]) == 2
        assert "0x123" in result["ethereum_mainnet"]
        assert "0x456" in result["ethereum_mainnet"]

    def test_parse_invalid_format_skipped(self):
        """Test that invalid format keys are skipped with warning."""
        keys = [
            "ETH:mainnet:0x123",
            "INVALID_KEY",  # Invalid - no colons
            "ETH:0x456",  # Invalid - only 2 parts
        ]
        result = _parse_target_keys(keys)

        assert len(result) == 1
        assert "ethereum_mainnet" in result
        assert len(result["ethereum_mainnet"]) == 1

    def test_parse_unknown_chain_code(self):
        """Test that unknown chain codes use lowercase as-is."""
        keys = ["UNKNOWN:testnet:0x123"]
        result = _parse_target_keys(keys)

        assert "unknown_testnet" in result

    def test_chain_code_mapping(self):
        """Test all supported chain code mappings."""
        expected_mappings = {
            "ETH": "ethereum",
            "SOL": "solana",
            "BTC": "bitcoin",
            "AVAX": "avalanche",
            "MATIC": "polygon",
            "ARB": "arbitrum",
            "OP": "optimism",
            "BASE": "base",
            "BSC": "bsc",
            "FTM": "fantom",
        }
        assert CHAIN_CODE_TO_NAME == expected_mappings


@pytest.mark.django_db
class TestGetUserMonitoredAddresses:
    """Tests for _get_user_monitored_addresses helper function."""

    def test_returns_empty_for_user_without_alerts(self):
        """Test returns empty list for user with no wallet alerts."""
        user = UserFactory()
        result = _get_user_monitored_addresses(user)
        assert result == []

    def test_returns_target_keys_from_wallet_alert(self):
        """Test returns target keys from enabled wallet alerts."""
        user = UserFactory()

        # Create wallet alert with target_keys
        AlertInstanceFactory(
            user=user,
            enabled=True,
            alert_type=AlertType.WALLET,
            target_keys=["ETH:mainnet:0x123", "SOL:mainnet:ABC"],
        )

        result = _get_user_monitored_addresses(user)

        assert len(result) == 2
        assert "ETH:mainnet:0x123" in result
        assert "SOL:mainnet:ABC" in result

    def test_ignores_disabled_alerts(self):
        """Test that disabled alerts are not included."""
        user = UserFactory()

        # Enabled alert
        AlertInstanceFactory(
            user=user,
            enabled=True,
            alert_type=AlertType.WALLET,
            target_keys=["ETH:mainnet:0x123"],
        )

        # Disabled alert - should be ignored
        AlertInstanceFactory(
            user=user,
            enabled=False,
            alert_type=AlertType.WALLET,
            target_keys=["SOL:mainnet:ABC"],
        )

        result = _get_user_monitored_addresses(user)

        assert len(result) == 1
        assert "ETH:mainnet:0x123" in result

    def test_ignores_non_wallet_alerts(self):
        """Test that non-wallet alerts are not included."""
        user = UserFactory()

        # Wallet alert - should be included
        AlertInstanceFactory(
            user=user,
            enabled=True,
            alert_type=AlertType.WALLET,
            target_keys=["ETH:mainnet:0x123"],
        )

        # Network alert - should be ignored
        AlertInstanceFactory(
            user=user,
            enabled=True,
            alert_type=AlertType.NETWORK,
            target_keys=["ETH:mainnet"],
        )

        result = _get_user_monitored_addresses(user)

        assert len(result) == 1
        assert "ETH:mainnet:0x123" in result

    def test_deduplicates_addresses_across_alerts(self):
        """Test that addresses are deduplicated across multiple alerts."""
        user = UserFactory()

        # Two alerts with overlapping addresses
        AlertInstanceFactory(
            user=user,
            enabled=True,
            alert_type=AlertType.WALLET,
            target_keys=["ETH:mainnet:0x123", "ETH:mainnet:0x456"],
        )
        AlertInstanceFactory(
            user=user,
            enabled=True,
            alert_type=AlertType.WALLET,
            target_keys=["ETH:mainnet:0x123", "SOL:mainnet:ABC"],  # 0x123 is duplicate
        )

        result = _get_user_monitored_addresses(user)

        assert len(result) == 3  # Not 4
        assert "ETH:mainnet:0x123" in result
        assert "ETH:mainnet:0x456" in result
        assert "SOL:mainnet:ABC" in result


# =============================================================================
# API Endpoint Tests
# =============================================================================


@pytest.mark.django_db
class TestNewsfeedTransactionsEndpoint:
    """Tests for the newsfeed_transactions API endpoint."""

    def test_requires_authentication(self, api_client):
        """Test that endpoint requires authentication."""
        url = reverse("alerts:analytics-newsfeed-transactions")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_returns_empty_when_no_alerts(self, authenticated_client, mock_ducklake_service):
        """Test returns empty response when user has no wallet alerts."""
        client, user = authenticated_client
        url = reverse("alerts:analytics-newsfeed-transactions")
        response = client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["transactions"] == []
        assert data["total"] == 0
        assert data["monitored_addresses"] == 0
        assert data["chains"] == []

        # DuckLake should not be called when no addresses
        mock_ducklake_service.query.assert_not_called()

    def test_returns_transactions_for_monitored_addresses(
        self, authenticated_client, mock_ducklake_service
    ):
        """Test returns transactions for user's monitored wallet addresses."""
        client, user = authenticated_client

        # Create wallet alert
        AlertInstanceFactory(
            user=user,
            enabled=True,
            alert_type=AlertType.WALLET,
            target_keys=["ETH:mainnet:0x123"],
        )

        # Mock DuckLake response
        mock_transactions = [
            {
                "transaction_hash": "0xabc",
                "block_timestamp": "2025-01-01T12:00:00Z",
                "chain_id": "ethereum_mainnet",
                "from_address": "0x123",
                "to_address": "0x456",
                "monitored_address": "0x123",
                "is_sender": True,
                "amount_native": "1.5",
                "amount_usd": 3000.0,
                "transaction_type": "TRANSFER",
                "transaction_subtype": "native",
                "decoded_function_name": None,
                "decoded_summary": "Transfer 1.5 ETH",
                "status": "SUCCESS",
            }
        ]
        mock_ducklake_service.query.side_effect = [
            mock_transactions,  # Main query
            [{"total": 1}],  # Count query
        ]

        url = reverse("alerts:analytics-newsfeed-transactions")
        response = client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["transactions"]) == 1
        assert data["transactions"][0]["transaction_hash"] == "0xabc"
        assert data["total"] == 1
        assert data["monitored_addresses"] == 1
        assert "ethereum_mainnet" in data["chains"]

    def test_pagination_parameters(self, authenticated_client, mock_ducklake_service):
        """Test that pagination parameters are passed correctly."""
        client, user = authenticated_client

        AlertInstanceFactory(
            user=user,
            enabled=True,
            alert_type=AlertType.WALLET,
            target_keys=["ETH:mainnet:0x123"],
        )

        mock_ducklake_service.query.side_effect = [[], [{"total": 0}]]

        url = reverse("alerts:analytics-newsfeed-transactions")
        response = client.get(url, {"limit": 25, "offset": 10})

        assert response.status_code == status.HTTP_200_OK

        # Check that query was called with correct params
        call_args = mock_ducklake_service.query.call_args_list[0]
        params = call_args[0][1]  # Second positional arg is params
        assert params["limit"] == 25
        assert params["offset"] == 10

    def test_limit_max_capped_at_500(self, authenticated_client, mock_ducklake_service):
        """Test that limit is capped at 500."""
        client, user = authenticated_client

        AlertInstanceFactory(
            user=user,
            enabled=True,
            alert_type=AlertType.WALLET,
            target_keys=["ETH:mainnet:0x123"],
        )

        mock_ducklake_service.query.side_effect = [[], [{"total": 0}]]

        url = reverse("alerts:analytics-newsfeed-transactions")
        response = client.get(url, {"limit": 1000})

        assert response.status_code == status.HTTP_200_OK

        call_args = mock_ducklake_service.query.call_args_list[0]
        params = call_args[0][1]
        assert params["limit"] == 500  # Capped at 500

    def test_chain_filter_applied(self, authenticated_client, mock_ducklake_service):
        """Test that chain filter is applied correctly."""
        client, user = authenticated_client

        AlertInstanceFactory(
            user=user,
            enabled=True,
            alert_type=AlertType.WALLET,
            target_keys=["ETH:mainnet:0x123", "SOL:mainnet:ABC"],
        )

        mock_ducklake_service.query.side_effect = [[], [{"total": 0}]]

        url = reverse("alerts:analytics-newsfeed-transactions")
        response = client.get(url, {"chains": "ethereum_mainnet"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Only ethereum_mainnet should be in chains
        assert "ethereum_mainnet" in data["chains"]
        assert "solana_mainnet" not in data["chains"]

    def test_transaction_type_filter(self, authenticated_client, mock_ducklake_service):
        """Test that transaction_type filter is applied."""
        client, user = authenticated_client

        AlertInstanceFactory(
            user=user,
            enabled=True,
            alert_type=AlertType.WALLET,
            target_keys=["ETH:mainnet:0x123"],
        )

        mock_ducklake_service.query.side_effect = [[], [{"total": 0}]]

        url = reverse("alerts:analytics-newsfeed-transactions")
        response = client.get(url, {"transaction_type": "CONTRACT_CALL"})

        assert response.status_code == status.HTTP_200_OK

        call_args = mock_ducklake_service.query.call_args_list[0]
        sql = call_args[0][0]
        params = call_args[0][1]

        assert "transaction_type" in params
        assert params["transaction_type"] == "CONTRACT_CALL"

    def test_start_date_parameter(self, authenticated_client, mock_ducklake_service):
        """Test that start_date parameter is parsed correctly."""
        client, user = authenticated_client

        AlertInstanceFactory(
            user=user,
            enabled=True,
            alert_type=AlertType.WALLET,
            target_keys=["ETH:mainnet:0x123"],
        )

        mock_ducklake_service.query.side_effect = [[], [{"total": 0}]]

        url = reverse("alerts:analytics-newsfeed-transactions")
        response = client.get(url, {"start_date": "2025-01-01T00:00:00Z"})

        assert response.status_code == status.HTTP_200_OK

        call_args = mock_ducklake_service.query.call_args_list[0]
        params = call_args[0][1]
        assert params["start_date"] is not None

    def test_invalid_start_date_returns_400(self, authenticated_client, mock_ducklake_service):
        """Test that invalid start_date returns 400 error."""
        client, user = authenticated_client

        AlertInstanceFactory(
            user=user,
            enabled=True,
            alert_type=AlertType.WALLET,
            target_keys=["ETH:mainnet:0x123"],
        )

        url = reverse("alerts:analytics-newsfeed-transactions")
        response = client.get(url, {"start_date": "not-a-date"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "start_date" in response.json()["error"].lower()

    def test_cross_chain_aggregation(self, authenticated_client, mock_ducklake_service):
        """Test that transactions from multiple chains are aggregated."""
        client, user = authenticated_client

        AlertInstanceFactory(
            user=user,
            enabled=True,
            alert_type=AlertType.WALLET,
            target_keys=["ETH:mainnet:0x123", "SOL:mainnet:ABC", "MATIC:mainnet:0x456"],
        )

        mock_ducklake_service.query.side_effect = [[], [{"total": 0}]]

        url = reverse("alerts:analytics-newsfeed-transactions")
        response = client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["monitored_addresses"] == 3
        assert len(data["chains"]) == 3
        assert "ethereum_mainnet" in data["chains"]
        assert "solana_mainnet" in data["chains"]
        assert "polygon_mainnet" in data["chains"]

    def test_ducklake_error_returns_500(self, authenticated_client, mock_ducklake_service):
        """Test that DuckLake errors return 500 response."""
        client, user = authenticated_client

        AlertInstanceFactory(
            user=user,
            enabled=True,
            alert_type=AlertType.WALLET,
            target_keys=["ETH:mainnet:0x123"],
        )

        mock_ducklake_service.query.side_effect = Exception("DuckLake connection error")

        url = reverse("alerts:analytics-newsfeed-transactions")
        response = client.get(url)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "error" in response.json()

    def test_default_start_date_is_24h_ago(self, authenticated_client, mock_ducklake_service):
        """Test that default start_date is 24 hours ago."""
        client, user = authenticated_client

        AlertInstanceFactory(
            user=user,
            enabled=True,
            alert_type=AlertType.WALLET,
            target_keys=["ETH:mainnet:0x123"],
        )

        mock_ducklake_service.query.side_effect = [[], [{"total": 0}]]

        now = timezone.now()
        url = reverse("alerts:analytics-newsfeed-transactions")
        response = client.get(url)

        assert response.status_code == status.HTTP_200_OK

        call_args = mock_ducklake_service.query.call_args_list[0]
        params = call_args[0][1]
        start_date = params["start_date"]

        # Should be approximately 24 hours ago (within a few seconds tolerance)
        expected = now - timedelta(hours=24)
        assert abs((start_date - expected).total_seconds()) < 10
