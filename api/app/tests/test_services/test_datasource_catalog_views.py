from app.services.datasource_catalog.catalog import (
    list_compiler_catalog_entries,
    list_runtime_catalog_entries,
)

from django.test import SimpleTestCase

class TestDatasourceCatalogViews(SimpleTestCase):
    def test_compiler_catalog_entries_hide_sql_and_routing(self):
        entries = list_compiler_catalog_entries()
        assert entries, "expected at least one catalog entry"
        for entry in entries:
            assert "catalog_id" in entry
            assert "description" in entry
            assert "params" in entry
            assert "result_schema" in entry
            assert "sql" not in entry
            assert "routing" not in entry

    def test_runtime_catalog_entries_include_sql_and_routing(self):
        entries = list_runtime_catalog_entries()
        assert entries, "expected at least one catalog entry"
        for entry in entries:
            assert entry.get("enabled") is True
            assert "catalog_id" in entry
            assert "routing" in entry and "table" in entry["routing"]
            assert "sql" in entry and entry["sql"] is not None
            assert "result_schema" in entry

    def test_address_transactions_count_24h_entry_is_allowlisted(self):
        runtime = list_runtime_catalog_entries()
        entry = next(
            (e for e in runtime if e.get("catalog_id") == "ducklake.address_transactions_count_24h"),
            None,
        )
        assert entry is not None, "expected ducklake.address_transactions_count_24h to be allowlisted"
        assert entry["routing"]["table"] == "address_transactions"
        assert entry["sql"]["dialect"] == "duckdb"
        assert entry["sql"]["param_order"] == ["target_keys", "chain_id", "subnet", "as_of", "as_of"]

        compiler = list_compiler_catalog_entries()
        compiler_entry = next(
            (e for e in compiler if e.get("catalog_id") == "ducklake.address_transactions_count_24h"),
            None,
        )
        assert compiler_entry is not None
        assert "sql" not in compiler_entry
        assert "routing" not in compiler_entry
