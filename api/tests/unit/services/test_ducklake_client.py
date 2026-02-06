import pytest

from app.services.ducklake_client import DuckLakeClient


def test_resolve_chain_subnet_defaults():
    client = DuckLakeClient(nats_url="nats://test", timeout=1)
    assert client._resolve_chain_subnet(None, None) == ("ekko", "default")
    assert client._resolve_chain_subnet("", "") == ("ekko", "default")
    assert client._resolve_chain_subnet("ethereum", "mainnet") == ("ethereum", "mainnet")


def test_build_query_subject():
    client = DuckLakeClient(nats_url="nats://test", timeout=1)
    subject = client._build_query_subject("notification_content", "ekko", "default")
    assert subject == "ducklake.notification_content.ekko.default.query"
