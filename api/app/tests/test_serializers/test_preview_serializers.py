"""Tests for Preview Serializers.

Unit tests for the alert preview/dry-run serializers including:
- PreviewConfigSerializer - Request validation
- PreviewResultSerializer - Response formatting
"""

import pytest
from uuid import uuid4
from datetime import datetime

from app.serializers import PreviewConfigSerializer, PreviewResultSerializer


class TestPreviewConfigSerializer:
    """Test PreviewConfigSerializer validation."""

    def test_valid_config_with_defaults(self):
        """Test validation with default values."""
        data = {}
        serializer = PreviewConfigSerializer(data=data)

        assert serializer.is_valid()
        assert serializer.validated_data["time_range"] == "7d"
        assert serializer.validated_data["limit"] == 1000
        assert serializer.validated_data["include_near_misses"] is False
        assert serializer.validated_data["explain_mode"] is False
        assert serializer.validated_data["parameters"] == {}
        assert serializer.validated_data["addresses"] == []

    def test_valid_config_with_custom_values(self):
        """Test validation with custom values."""
        data = {
            "parameters": {"threshold": 1000, "wallet": "0xabc"},
            "time_range": "24h",
            "limit": 500,
            "include_near_misses": True,
            "explain_mode": True,
            "addresses": ["0xabc", "0xdef"],
            "chain": "ethereum",
        }
        serializer = PreviewConfigSerializer(data=data)

        assert serializer.is_valid()
        assert serializer.validated_data["time_range"] == "24h"
        assert serializer.validated_data["limit"] == 500
        assert serializer.validated_data["include_near_misses"] is True
        assert len(serializer.validated_data["addresses"]) == 2

    def test_valid_time_ranges(self):
        """Test all valid time range options."""
        valid_ranges = ["1h", "24h", "7d", "30d"]

        for time_range in valid_ranges:
            data = {"time_range": time_range}
            serializer = PreviewConfigSerializer(data=data)
            assert serializer.is_valid(), f"Time range {time_range} should be valid"

    def test_invalid_time_range(self):
        """Test invalid time range validation."""
        data = {"time_range": "invalid"}
        serializer = PreviewConfigSerializer(data=data)

        assert not serializer.is_valid()
        assert "time_range" in serializer.errors

    def test_limit_minimum_validation(self):
        """Test limit minimum value validation."""
        data = {"limit": 0}
        serializer = PreviewConfigSerializer(data=data)

        assert not serializer.is_valid()
        assert "limit" in serializer.errors

    def test_limit_maximum_validation(self):
        """Test limit maximum value validation."""
        data = {"limit": 20000}
        serializer = PreviewConfigSerializer(data=data)

        assert not serializer.is_valid()
        assert "limit" in serializer.errors

    def test_limit_valid_range(self):
        """Test limit valid range."""
        data = {"limit": 5000}
        serializer = PreviewConfigSerializer(data=data)

        assert serializer.is_valid()
        assert serializer.validated_data["limit"] == 5000

    def test_parameters_accepts_dict(self):
        """Test parameters field accepts dictionary."""
        data = {
            "parameters": {
                "wallet_address": "0xabc",
                "threshold": 1000,
                "operator": ">",
            }
        }
        serializer = PreviewConfigSerializer(data=data)

        assert serializer.is_valid()
        assert serializer.validated_data["parameters"]["threshold"] == 1000

    def test_addresses_accepts_list(self):
        """Test addresses field accepts list of strings."""
        data = {
            "addresses": [
                "0x742d35Cc6634C0532925a3b8D4C9db96c4b4d8b",
                "0x123456789abcdef123456789abcdef12345678",
            ]
        }
        serializer = PreviewConfigSerializer(data=data)

        assert serializer.is_valid()
        assert len(serializer.validated_data["addresses"]) == 2

    def test_chain_optional(self):
        """Test chain field is optional."""
        data = {}
        serializer = PreviewConfigSerializer(data=data)

        assert serializer.is_valid()

    def test_chain_accepts_string(self):
        """Test chain field accepts string."""
        data = {"chain": "ethereum"}
        serializer = PreviewConfigSerializer(data=data)

        assert serializer.is_valid()
        assert serializer.validated_data["chain"] == "ethereum"


class TestPreviewResultSerializer:
    """Test PreviewResultSerializer output formatting."""

    def test_valid_success_result(self):
        """Test serialization of successful result."""
        data = {
            "success": True,
            "preview_id": str(uuid4()),
            "summary": {
                "total_events_evaluated": 1000,
                "would_have_triggered": 15,
                "trigger_rate": 0.015,
                "estimated_daily_triggers": 2.14,
                "evaluation_time_ms": 45.5,
            },
            "sample_triggers": [
                {
                    "timestamp": "2024-01-01T12:00:00Z",
                    "data": {"value_usd": 1500, "tx_hash": "0x123"},
                    "matched_condition": "value_usd > 1000",
                }
            ],
            "near_misses": [],
            "evaluation_mode": "per_row",
            "expression": "value_usd > 1000",
            "data_source": "transactions",
            "time_range": "7d",
            "requires_wasmcloud": False,
        }
        serializer = PreviewResultSerializer(data=data)

        assert serializer.is_valid()

    def test_valid_failure_result(self):
        """Test serialization of failure result."""
        data = {
            "success": False,
            "summary": {
                "total_events_evaluated": 0,
                "would_have_triggered": 0,
                "trigger_rate": 0.0,
                "estimated_daily_triggers": 0.0,
                "evaluation_time_ms": 0.0,
            },
            "evaluation_mode": "aggregate",
            "requires_wasmcloud": True,
            "wasmcloud_reason": "Expression contains aggregate function: col().last()",
            "error": "Expression requires wasmCloud evaluation",
        }
        serializer = PreviewResultSerializer(data=data)

        assert serializer.is_valid()

    def test_valid_evaluation_modes(self):
        """Test all valid evaluation mode options."""
        valid_modes = ["per_row", "aggregate", "window", "unknown"]

        for mode in valid_modes:
            data = {
                "success": True,
                "summary": {
                    "total_events_evaluated": 100,
                    "would_have_triggered": 10,
                    "trigger_rate": 0.1,
                    "estimated_daily_triggers": 1.0,
                    "evaluation_time_ms": 10.0,
                },
                "evaluation_mode": mode,
            }
            serializer = PreviewResultSerializer(data=data)
            assert serializer.is_valid(), f"Mode {mode} should be valid"

    def test_invalid_evaluation_mode(self):
        """Test invalid evaluation mode validation."""
        data = {
            "success": True,
            "summary": {
                "total_events_evaluated": 100,
                "would_have_triggered": 10,
                "trigger_rate": 0.1,
                "estimated_daily_triggers": 1.0,
                "evaluation_time_ms": 10.0,
            },
            "evaluation_mode": "invalid_mode",
        }
        serializer = PreviewResultSerializer(data=data)

        assert not serializer.is_valid()
        assert "evaluation_mode" in serializer.errors

    def test_sample_triggers_serialization(self):
        """Test sample triggers list serialization."""
        data = {
            "success": True,
            "summary": {
                "total_events_evaluated": 1000,
                "would_have_triggered": 3,
                "trigger_rate": 0.003,
                "estimated_daily_triggers": 0.43,
                "evaluation_time_ms": 50.0,
            },
            "sample_triggers": [
                {
                    "timestamp": "2024-01-01T12:00:00Z",
                    "data": {"value_usd": 1500},
                    "matched_condition": "value_usd > 1000",
                },
                {
                    "timestamp": "2024-01-02T14:30:00Z",
                    "data": {"value_usd": 2000},
                    "matched_condition": "value_usd > 1000",
                },
                {
                    "timestamp": "2024-01-03T09:15:00Z",
                    "data": {"value_usd": 3000},
                    "matched_condition": "value_usd > 1000",
                },
            ],
            "evaluation_mode": "per_row",
        }
        serializer = PreviewResultSerializer(data=data)

        assert serializer.is_valid()

    def test_near_misses_serialization(self):
        """Test near misses list serialization."""
        data = {
            "success": True,
            "summary": {
                "total_events_evaluated": 1000,
                "would_have_triggered": 10,
                "trigger_rate": 0.01,
                "estimated_daily_triggers": 1.43,
                "evaluation_time_ms": 50.0,
            },
            "near_misses": [
                {
                    "timestamp": "2024-01-01T12:00:00Z",
                    "data": {"value_usd": 950},
                    "threshold_distance": 5.0,
                    "explanation": "value_usd was 5% below threshold of 1000",
                },
            ],
            "evaluation_mode": "per_row",
        }
        serializer = PreviewResultSerializer(data=data)

        assert serializer.is_valid()

    def test_optional_fields(self):
        """Test optional fields can be omitted."""
        data = {
            "success": True,
            "summary": {
                "total_events_evaluated": 100,
                "would_have_triggered": 5,
                "trigger_rate": 0.05,
                "estimated_daily_triggers": 0.71,
                "evaluation_time_ms": 25.0,
            },
            "evaluation_mode": "per_row",
            # Optional fields omitted: preview_id, expression, data_source, time_range, error
        }
        serializer = PreviewResultSerializer(data=data)

        assert serializer.is_valid()

    def test_summary_required(self):
        """Test summary field is required."""
        data = {
            "success": True,
            "evaluation_mode": "per_row",
        }
        serializer = PreviewResultSerializer(data=data)

        assert not serializer.is_valid()
        assert "summary" in serializer.errors


class TestPreviewSummaryFields:
    """Test PreviewSummarySerializer nested fields."""

    def test_summary_all_fields_required(self):
        """Test all summary fields are required."""
        required_fields = [
            "total_events_evaluated",
            "would_have_triggered",
            "trigger_rate",
            "estimated_daily_triggers",
            "evaluation_time_ms",
        ]

        for field_to_skip in required_fields:
            summary = {
                "total_events_evaluated": 100,
                "would_have_triggered": 10,
                "trigger_rate": 0.1,
                "estimated_daily_triggers": 1.0,
                "evaluation_time_ms": 10.0,
            }
            del summary[field_to_skip]

            data = {
                "success": True,
                "summary": summary,
                "evaluation_mode": "per_row",
            }
            serializer = PreviewResultSerializer(data=data)

            assert not serializer.is_valid(), f"Missing {field_to_skip} should fail"

    def test_summary_numeric_validation(self):
        """Test summary fields accept numeric values."""
        data = {
            "success": True,
            "summary": {
                "total_events_evaluated": 10000,
                "would_have_triggered": 150,
                "trigger_rate": 0.015,
                "estimated_daily_triggers": 21.43,
                "evaluation_time_ms": 125.75,
            },
            "evaluation_mode": "per_row",
        }
        serializer = PreviewResultSerializer(data=data)

        assert serializer.is_valid()

    def test_summary_zero_values_valid(self):
        """Test summary accepts zero values."""
        data = {
            "success": True,
            "summary": {
                "total_events_evaluated": 0,
                "would_have_triggered": 0,
                "trigger_rate": 0.0,
                "estimated_daily_triggers": 0.0,
                "evaluation_time_ms": 0.0,
            },
            "evaluation_mode": "per_row",
        }
        serializer = PreviewResultSerializer(data=data)

        assert serializer.is_valid()
