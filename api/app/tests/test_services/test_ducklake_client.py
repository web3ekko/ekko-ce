import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.ducklake_client import DuckLakeClient


class TestDuckLakeClient(unittest.TestCase):
    def test_query_rows_delegates_to_query(self):
        client = DuckLakeClient(nats_url="nats://test")

        async def run():
            with patch.object(client, "_query", new=AsyncMock(return_value=[{"ok": 1}])) as mock_query:
                rows = await client.query_rows(query="select 1", table="transactions")
                self.assertEqual(rows, [{"ok": 1}])
                mock_query.assert_awaited_once()

        asyncio.run(run())

    def test_connect_reinitializes_on_loop_change(self):
        client = DuckLakeClient(nats_url="nats://test")

        first_nc = MagicMock()
        first_nc.is_connected = True
        first_nc.close = AsyncMock()

        async def first_connect():
            with patch("app.services.ducklake_client.nats.connect", new=AsyncMock(return_value=first_nc)):
                await client.connect()

        asyncio.run(first_connect())
        self.assertIs(client._nc, first_nc)

        second_nc = MagicMock()
        second_nc.is_connected = True
        second_nc.close = AsyncMock()

        async def second_connect():
            with patch("app.services.ducklake_client.nats.connect", new=AsyncMock(return_value=second_nc)) as connect_mock:
                await client.connect()
                connect_mock.assert_awaited_once()

        asyncio.run(second_connect())
        self.assertIs(client._nc, second_nc)
