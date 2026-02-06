"""
Unit tests for Alert Cache Manager service

Tests the Redis caching operations for AlertInstance data including:
- Pipelined JSON index operations
- Batch cache warming
- SCAN-based migration (non-blocking)
- TTL management
"""

import pytest
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call
from uuid import uuid4

from app.services.alert_cache import (
    AlertCacheManager,
    ALERT_HASH_TTL,
    INDEX_KEY_TTL,
    BATCH_SIZE,
)


class MockPipeline:
    """Mock Redis pipeline for testing batched operations"""

    def __init__(self):
        self.commands = []
        self._results = []

    def get(self, key):
        self.commands.append(('get', key))
        return self

    def set(self, key, value):
        self.commands.append(('set', key, value))
        return self

    def hset(self, key, mapping=None):
        self.commands.append(('hset', key, mapping))
        return self

    def expire(self, key, ttl):
        self.commands.append(('expire', key, ttl))
        return self

    def sadd(self, key, *values):
        self.commands.append(('sadd', key, values))
        return self

    def srem(self, key, *values):
        self.commands.append(('srem', key, values))
        return self

    def zadd(self, key, mapping):
        self.commands.append(('zadd', key, mapping))
        return self

    def zrem(self, key, *values):
        self.commands.append(('zrem', key, values))
        return self

    def delete(self, key):
        self.commands.append(('delete', key))
        return self

    def hgetall(self, key):
        self.commands.append(('hgetall', key))
        return self

    def execute(self):
        return self._results

    def set_results(self, results):
        self._results = results

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class MockAlertInstance:
    """Mock AlertInstance for testing"""

    def __init__(
        self,
        id=None,
        trigger_type='event_driven',
        trigger_config=None,
        spec=None,
        user_id=None,
        enabled=True,
        version=1,
        created_at=None,
        last_job_created_at=None,
        job_creation_count=0,
        name='Test Alert',
        alert_type='wallet',
        target_keys=None,
    ):
        self.id = id or uuid4()
        self.trigger_type = trigger_type
        self.trigger_config = trigger_config or {}
        self.spec = spec or {}
        self.user_id = user_id or uuid4()
        self.enabled = enabled
        self.version = version
        self.created_at = created_at or datetime.now(timezone.utc)
        self.last_job_created_at = last_job_created_at
        self.job_creation_count = job_creation_count
        self.name = name
        self.alert_type = alert_type
        self.target_keys = target_keys or []
        self.template_params = {}
        self.template_id = uuid4()
        self.template = type("T", (), {"spec": {"version": "v1", "name": "t", "description": "d", "trigger": {"chain_id": 1}, "conditions": {"all": [], "any": [], "not": []}, "action": {"cooldown_secs": 0}}})()

    def get_effective_targets(self):
        return self.target_keys


class TestAlertCacheManager:
    """Test AlertCacheManager functionality"""

    def test_collect_index_keys_with_addresses(self):
        """Test collecting index keys from explicit target keys (wallet alerts)."""
        manager = AlertCacheManager.__new__(AlertCacheManager)
        manager.redis_client = MagicMock()

        alert = MockAlertInstance(
            alert_type='wallet',
            target_keys=[
                'ETH:mainnet:0xaddr1',
                'POLYGON:mainnet:0xAddr2',  # Mixed case should be lowered in index key
            ],
        )

        keys = manager._collect_index_keys(
            alert_instance=alert,
            expanded_targets=alert.get_effective_targets(),
            fallback_spec={},
        )

        assert len(keys) == 2
        assert 'alerts:address:ETH:mainnet:0xaddr1' in keys
        assert 'alerts:address:MATIC:mainnet:0xaddr2' in keys

    def test_collect_index_keys_with_contracts(self):
        """Test collecting index keys from explicit target keys (contract/token alerts)."""
        manager = AlertCacheManager.__new__(AlertCacheManager)
        manager.redis_client = MagicMock()

        alert = MockAlertInstance(
            alert_type='token',
            target_keys=['ETH:mainnet:0xcontract1'],
        )

        keys = manager._collect_index_keys(
            alert_instance=alert,
            expanded_targets=alert.get_effective_targets(),
            fallback_spec={},
        )

        assert len(keys) == 1
        assert 'alerts:contract:ETH:mainnet:0xcontract1' in keys

    def test_collect_index_keys_empty(self):
        """Test collecting index keys when no targets and no legacy scope."""
        manager = AlertCacheManager.__new__(AlertCacheManager)
        manager.redis_client = MagicMock()

        alert = MockAlertInstance(
            target_keys=[],
            spec={},
        )

        keys = manager._collect_index_keys(
            alert_instance=alert,
            expanded_targets=alert.get_effective_targets(),
            fallback_spec=alert.spec,
        )

        assert len(keys) == 0

    def test_parse_json_index_valid(self):
        """Test parsing valid JSON array index"""
        manager = AlertCacheManager.__new__(AlertCacheManager)

        result = manager._parse_json_index('["id1", "id2", "id3"]')

        assert result == ['id1', 'id2', 'id3']

    def test_parse_json_index_empty_string(self):
        """Test parsing empty string"""
        manager = AlertCacheManager.__new__(AlertCacheManager)

        result = manager._parse_json_index('')

        assert result == []

    def test_parse_json_index_none(self):
        """Test parsing None value"""
        manager = AlertCacheManager.__new__(AlertCacheManager)

        result = manager._parse_json_index(None)

        assert result == []

    def test_parse_json_index_invalid_json(self):
        """Test parsing invalid JSON"""
        manager = AlertCacheManager.__new__(AlertCacheManager)

        result = manager._parse_json_index('not json')

        assert result == []

    def test_parse_json_index_non_array(self):
        """Test parsing JSON that isn't an array"""
        manager = AlertCacheManager.__new__(AlertCacheManager)

        result = manager._parse_json_index('"single_id"')

        assert result == ['single_id']

    def test_sync_alert_to_redis_uses_pipelines(self):
        """Test that sync_alert_to_redis uses pipelined operations"""
        manager = AlertCacheManager.__new__(AlertCacheManager)
        mock_redis = MagicMock()
        manager.redis_client = mock_redis

        # Track pipeline calls
        pipeline_calls = []

        def mock_pipeline():
            pipe = MockPipeline()
            pipe.set_results([None])  # For GET pipeline
            pipeline_calls.append(pipe)
            return pipe

        mock_redis.pipeline.return_value.__enter__ = lambda s: mock_pipeline()
        mock_redis.pipeline.return_value.__exit__ = lambda s, *args: None

        # Create pipeline mock that tracks all operations
        get_pipe = MockPipeline()
        get_pipe.set_results([None])  # No existing index value
        set_pipe = MockPipeline()
        set_pipe.set_results([True] * 10)

        call_count = [0]

        def pipeline_context():
            pipe = get_pipe if call_count[0] == 0 else set_pipe
            call_count[0] += 1
            return pipe

        mock_redis.pipeline.side_effect = lambda: MagicMock(
            __enter__=lambda s: pipeline_context(),
            __exit__=lambda s, *args: None,
        )

        alert = MockAlertInstance(target_keys=['ETH:mainnet:0xabc'])

        # Patch logger to suppress output
        with patch('app.services.alert_cache.logger'):
            manager.sync_alert_to_redis(alert)

        # Should have called pipeline() at least twice (GET phase and SET phase)
        assert mock_redis.pipeline.call_count >= 2

    def test_serialize_alert_for_redis(self):
        """Test alert serialization for Redis hash"""
        manager = AlertCacheManager.__new__(AlertCacheManager)

        alert = MockAlertInstance(
            trigger_type='periodic',
            trigger_config={'interval_hours': 24},
            enabled=True,
            version=3,
            job_creation_count=42,
            name='Daily Summary',
            alert_type='wallet',
            target_keys=['ETH:mainnet:0xabc'],
        )

        result = manager._serialize_alert_for_redis(
            alert_instance=alert,
            execution_spec=alert.template.spec,
            expanded_targets=alert.get_effective_targets(),
        )

        assert result['trigger_type'] == 'periodic'
        assert result['enabled'] == '1'
        assert result['version'] == '3'
        assert result['job_creation_count'] == '42'
        assert result['name'] == 'Daily Summary'
        assert result['alert_type'] == 'wallet'
        assert json.loads(result['target_keys']) == ['ETH:mainnet:0xabc']
        assert result['template_id'] != ""
        assert 'trigger_config' in result
        assert 'spec' in result
        assert json.loads(result['trigger_config']) == {'interval_hours': 24}

    def test_serialize_alert_disabled(self):
        """Test serialization of disabled alert"""
        manager = AlertCacheManager.__new__(AlertCacheManager)

        alert = MockAlertInstance(enabled=False)

        result = manager._serialize_alert_for_redis(
            alert_instance=alert,
            execution_spec=alert.template.spec,
            expanded_targets=alert.get_effective_targets(),
        )

        assert result['enabled'] == '0'

    def test_extract_chain_events_event_driven(self):
        """Test chain event extraction for event-driven alerts"""
        manager = AlertCacheManager.__new__(AlertCacheManager)

        alert = MockAlertInstance(
            trigger_type='event_driven',
            trigger_config={'event_types': ['transfer', 'swap']},
            target_keys=[
                'ETH:mainnet:0xaddr1',
                'POLYGON:mainnet:0xaddr2',
            ],
        )

        chain_events = manager._extract_chain_events(alert)

        assert len(chain_events) == 4
        assert ('ETH:mainnet', 'transfer') in chain_events
        assert ('ETH:mainnet', 'swap') in chain_events
        assert ('MATIC:mainnet', 'transfer') in chain_events
        assert ('MATIC:mainnet', 'swap') in chain_events

    def test_extract_chain_events_periodic(self):
        """Test chain event extraction for periodic alerts (should be empty)"""
        manager = AlertCacheManager.__new__(AlertCacheManager)

        alert = MockAlertInstance(
            trigger_type='periodic',
            trigger_config={'interval_hours': 24},
            target_keys=['ETH:mainnet:0xaddr1'],
        )

        chain_events = manager._extract_chain_events(alert)

        assert len(chain_events) == 0


class TestBatchOperations:
    """Test batch cache operations"""

    def test_sync_batch_to_redis_empty(self):
        """Test batch sync with empty list"""
        manager = AlertCacheManager.__new__(AlertCacheManager)
        manager.redis_client = MagicMock()

        with patch('app.services.alert_cache.logger'):
            result = manager._sync_batch_to_redis([])

        assert result == {'synced': 0, 'failed': 0}

    def test_sync_batch_aggregates_index_keys(self):
        """Test that batch sync aggregates index keys across alerts"""
        manager = AlertCacheManager.__new__(AlertCacheManager)
        mock_redis = MagicMock()
        manager.redis_client = mock_redis

        # Create two alerts monitoring the same address
        alert1 = MockAlertInstance(
            id=uuid4(),
            alert_type='wallet',
            target_keys=['ETH:mainnet:0xshared'],
        )
        alert2 = MockAlertInstance(
            id=uuid4(),
            alert_type='wallet',
            target_keys=['ETH:mainnet:0xshared'],
        )

        # Track pipeline operations
        get_results = [None]  # No existing index value
        set_pipe = MockPipeline()
        set_pipe.set_results([True] * 20)

        call_count = [0]

        def pipeline_context():
            if call_count[0] == 0:
                pipe = MockPipeline()
                pipe.set_results(get_results)
                call_count[0] += 1
                return pipe
            else:
                call_count[0] += 1
                return set_pipe

        mock_redis.pipeline.side_effect = lambda: MagicMock(
            __enter__=lambda s: pipeline_context(),
            __exit__=lambda s, *args: None,
        )

        with patch('app.services.alert_cache.logger'):
            result = manager._sync_batch_to_redis([alert1, alert2])

        assert result['synced'] == 2
        assert result['failed'] == 0

        # Verify only one GET was done for the shared key
        # (both alerts share alerts:address:ETH:mainnet:0xshared)


class TestMigration:
    """Test migration from SETs to JSON arrays"""

    def test_migrate_uses_scan_not_keys(self):
        """Test that migration uses SCAN instead of blocking KEYS"""
        manager = AlertCacheManager.__new__(AlertCacheManager)
        mock_redis = MagicMock()
        manager.redis_client = mock_redis

        # Mock SCAN to return empty results
        mock_redis.scan.return_value = (0, [])

        with patch('app.services.alert_cache.logger'):
            manager.migrate_sets_to_json()

        # Should use scan, not keys
        mock_redis.scan.assert_called()
        mock_redis.keys.assert_not_called()

    def test_migrate_iterates_with_cursor(self):
        """Test that migration properly iterates using cursor"""
        manager = AlertCacheManager.__new__(AlertCacheManager)
        mock_redis = MagicMock()
        manager.redis_client = mock_redis

        # Mock SCAN to return results in multiple iterations
        mock_redis.scan.side_effect = [
            (100, ['alerts:address:ETH:mainnet:0x1']),  # First call
            (0, ['alerts:address:ETH:mainnet:0x2']),  # Second call (cursor 0 = done)
            (0, []),  # For contract pattern
        ]
        mock_redis.type.return_value = 'string'
        mock_redis.get.return_value = '["alert1"]'

        with patch('app.services.alert_cache.logger'):
            result = manager.migrate_sets_to_json()

        # Should have made 3 scan calls (2 for addresses pattern, 1 for contracts)
        assert mock_redis.scan.call_count >= 2

    def test_migrate_converts_set_to_json(self):
        """Test that migration converts SET to JSON array"""
        manager = AlertCacheManager.__new__(AlertCacheManager)
        mock_redis = MagicMock()
        manager.redis_client = mock_redis

        mock_redis.scan.side_effect = [
            (0, ['alerts:address:ETH:mainnet:0x1']),
            (0, []),
        ]
        mock_redis.type.return_value = 'set'
        mock_redis.smembers.return_value = {'alert1', 'alert2'}

        with patch('app.services.alert_cache.logger'):
            result = manager.migrate_sets_to_json()

        # Should delete the SET
        mock_redis.delete.assert_called_with('alerts:address:ETH:mainnet:0x1')

        # Should write JSON array with TTL
        mock_redis.set.assert_called()
        mock_redis.expire.assert_called_with(
            'alerts:address:ETH:mainnet:0x1', INDEX_KEY_TTL
        )

        assert result['migrated'] == 1


class TestCacheStats:
    """Test cache statistics retrieval"""

    def test_get_cache_stats(self):
        """Test getting cache statistics"""
        manager = AlertCacheManager.__new__(AlertCacheManager)
        mock_redis = MagicMock()
        manager.redis_client = mock_redis

        mock_redis.scard.return_value = 100
        mock_redis.zcard.side_effect = [50, 10]  # periodic, onetime
        mock_redis.scan.side_effect = [
            (0, ['addr1', 'addr2', 'addr3']),  # address keys
            (0, ['contract1']),  # contract keys
        ]

        stats = manager.get_cache_stats()

        assert stats['active_alerts'] == 100
        assert stats['periodic_scheduled'] == 50
        assert stats['onetime_scheduled'] == 10
        assert stats['address_indexes'] == 3
        assert stats['contract_indexes'] == 1


class TestTTLs:
    """Test TTL configuration"""

    def test_ttl_constants(self):
        """Test TTL constants are set correctly"""
        assert ALERT_HASH_TTL == 7 * 24 * 3600  # 7 days
        assert INDEX_KEY_TTL == 24 * 3600  # 24 hours
        assert BATCH_SIZE == 500


class TestBatchRemoveFromIndexes:
    """Test batch removal from indexes"""

    def test_batch_remove_empty_keys(self):
        """Test batch remove with empty keys list"""
        manager = AlertCacheManager.__new__(AlertCacheManager)
        manager.redis_client = MagicMock()

        # Should return without error
        manager._batch_remove_from_indexes([], 'alert1')

        manager.redis_client.pipeline.assert_not_called()

    def test_batch_remove_deletes_empty_indexes(self):
        """Test that batch remove deletes indexes when they become empty"""
        manager = AlertCacheManager.__new__(AlertCacheManager)
        mock_redis = MagicMock()
        manager.redis_client = mock_redis

        get_pipe = MockPipeline()
        get_pipe.set_results(['["alert1"]'])  # Only one alert

        set_pipe = MockPipeline()
        set_pipe.set_results([True])

        call_count = [0]

        def pipeline_context():
            if call_count[0] == 0:
                call_count[0] += 1
                return get_pipe
            else:
                call_count[0] += 1
                return set_pipe

        mock_redis.pipeline.side_effect = lambda: MagicMock(
            __enter__=lambda s: pipeline_context(),
            __exit__=lambda s, *args: None,
        )

        manager._batch_remove_from_indexes(
            ['alerts:address:ETH:mainnet:0x1'], 'alert1'
        )

        # Should have issued a delete since index becomes empty
        delete_cmd = [cmd for cmd in set_pipe.commands if cmd[0] == 'delete']
        assert len(delete_cmd) == 1
