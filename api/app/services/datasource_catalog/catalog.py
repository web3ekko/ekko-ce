from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class DatasourceParam:
    name: str
    type: str
    required: bool = True


@dataclass(frozen=True)
class DatasourceRouting:
    table: str

    def as_dict(self) -> Dict[str, Any]:
        return {"table": self.table}


@dataclass(frozen=True)
class DatasourceResultColumn:
    name: str
    type: str


@dataclass(frozen=True)
class DatasourceResultSchema:
    key_columns: List[str]
    columns: List[DatasourceResultColumn]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "key_columns": list(self.key_columns),
            "columns": [{"name": c.name, "type": c.type} for c in self.columns],
        }


@dataclass(frozen=True)
class DatasourceSQL:
    dialect: str
    query: str
    param_order: List[str]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "dialect": self.dialect,
            "query": self.query,
            "param_order": list(self.param_order),
        }


@dataclass(frozen=True)
class DatasourceCatalogEntry:
    catalog_id: str
    type: str
    enabled: bool
    description: str
    routing: DatasourceRouting
    sql: Optional[DatasourceSQL]
    params: List[DatasourceParam]
    result_schema: DatasourceResultSchema
    cache_policy: Dict[str, Any]
    timeouts: Dict[str, Any]

    def compiler_view(self) -> Dict[str, Any]:
        """
        Public surface visible to the NLP compiler.

        Per PRD: the compiler sees only catalog_id, description, params, result_schema.
        """

        return {
            "catalog_id": self.catalog_id,
            "description": self.description,
            "params": [{"name": p.name, "type": p.type, "required": p.required} for p in self.params],
            "result_schema": self.result_schema.as_dict(),
        }

    def runtime_view(self) -> Dict[str, Any]:
        """
        Full runtime surface (includes SQL) projected into Redis for wasmCloud runtime.
        """

        return {
            "catalog_id": self.catalog_id,
            "type": self.type,
            "enabled": self.enabled,
            "description": self.description,
            "routing": self.routing.as_dict(),
            "sql": self.sql.as_dict() if self.sql else None,
            "params": [{"name": p.name, "type": p.type, "required": p.required} for p in self.params],
            "result_schema": self.result_schema.as_dict(),
            "cache_policy": dict(self.cache_policy),
            "timeouts": dict(self.timeouts),
        }


def list_catalog_entries() -> List[DatasourceCatalogEntry]:
    """
    Return the allowlisted DatasourceCatalog entries (v1).

    Operational note: maintained inside the Django API (author-reviewed).
    """

    return [
        DatasourceCatalogEntry(
            catalog_id="ducklake.wallet_balance_latest",
            type="ducklake_query",
            enabled=True,
            description="Latest wallet balance per target_key at or before as_of",
            routing=DatasourceRouting(table="wallet_balance_latest"),
            sql=DatasourceSQL(
                dialect="duckdb",
                query=(
                    "SELECT target_key, balance_latest "
                    "FROM wallet_balance_latest "
                    "WHERE target_key IN (SELECT * FROM UNNEST(string_split(?, ','))) AND as_of <= ?"
                ),
                param_order=["target_keys", "as_of"],
            ),
            params=[
                DatasourceParam(name="target_keys", type="target_keys_csv", required=True),
                DatasourceParam(name="as_of", type="timestamp", required=True),
            ],
            result_schema=DatasourceResultSchema(
                key_columns=["target_key"],
                columns=[
                    DatasourceResultColumn(name="target_key", type="string"),
                    DatasourceResultColumn(name="balance_latest", type="decimal"),
                ],
            ),
            cache_policy={"default_ttl_secs": 30, "max_ttl_secs": 3600},
            timeouts={"default_timeout_ms": 1500, "max_timeout_ms": 10000},
        ),
        DatasourceCatalogEntry(
            catalog_id="ducklake.wallet_balance_window",
            type="ducklake_query",
            enabled=True,
            description="Latest and window-change wallet balance metrics per target_key",
            routing=DatasourceRouting(table="wallet_balance_window"),
            sql=DatasourceSQL(
                dialect="duckdb",
                query=(
                    "SELECT target_key, balance_latest, pct_change_window "
                    "FROM wallet_balance_window "
                    "WHERE target_key IN (SELECT * FROM UNNEST(string_split(?, ','))) AND as_of <= ? AND window_duration = ?"
                ),
                param_order=["target_keys", "as_of", "window_duration"],
            ),
            params=[
                DatasourceParam(name="target_keys", type="target_keys_csv", required=True),
                DatasourceParam(name="as_of", type="timestamp", required=True),
                DatasourceParam(name="window_duration", type="duration", required=True),
            ],
            result_schema=DatasourceResultSchema(
                key_columns=["target_key"],
                columns=[
                    DatasourceResultColumn(name="target_key", type="string"),
                    DatasourceResultColumn(name="balance_latest", type="decimal"),
                    DatasourceResultColumn(name="pct_change_window", type="decimal"),
                ],
            ),
            cache_policy={"default_ttl_secs": 30, "max_ttl_secs": 3600},
            timeouts={"default_timeout_ms": 2000, "max_timeout_ms": 10000},
        ),
        DatasourceCatalogEntry(
            catalog_id="ducklake.address_transactions_count_24h",
            type="ducklake_query",
            enabled=True,
            description="Transaction count per wallet over the last 24 hours",
            routing=DatasourceRouting(table="address_transactions"),
            sql=DatasourceSQL(
                dialect="duckdb",
                query=(
                    "WITH targets AS ("
                    "  SELECT "
                    "    t AS target_key, "
                    "    lower(split_part(t, ':', 3)) AS address "
                    "  FROM UNNEST(string_split(?, ',')) AS u(t)"
                    "), chain_scope AS ("
                    "  SELECT "
                    "    (CASE ? "
                    "      WHEN 1 THEN 'ethereum' "
                    "      WHEN 43114 THEN 'avalanche' "
                    "      ELSE 'ethereum' "
                    "    END) || '_' || ? AS chain_id"
                    ") "
                    "SELECT "
                    "  targets.target_key, "
                    "  COUNT(atx.transaction_hash) AS tx_count_24h "
                    "FROM targets "
                    "LEFT JOIN address_transactions atx "
                    "  ON atx.address = targets.address "
                    " AND atx.chain_id = (SELECT chain_id FROM chain_scope) "
                    # NOTE: address_transactions.block_timestamp is a Timestamp(us) in DuckLake, but
                    # some writers have historically emitted seconds. We filter on block_date (Date32)
                    # to keep this query resilient while the write-path units are normalized.
                    " AND atx.block_date >= CAST(? AS DATE) - INTERVAL '1 day' "
                    " AND atx.block_date <= CAST(? AS DATE) "
                    "GROUP BY targets.target_key"
                ),
                param_order=["target_keys", "chain_id", "subnet", "as_of", "as_of"],
            ),
            params=[
                DatasourceParam(name="target_keys", type="target_keys_csv", required=True),
                DatasourceParam(name="chain_id", type="integer", required=True),
                DatasourceParam(name="subnet", type="string", required=True),
                DatasourceParam(name="as_of", type="timestamp", required=True),
            ],
            result_schema=DatasourceResultSchema(
                key_columns=["target_key"],
                columns=[
                    DatasourceResultColumn(name="target_key", type="string"),
                    DatasourceResultColumn(name="tx_count_24h", type="integer"),
                ],
            ),
            cache_policy={"default_ttl_secs": 30, "max_ttl_secs": 300},
            timeouts={"default_timeout_ms": 1500, "max_timeout_ms": 10000},
        ),
    ]


def get_catalog_entry(catalog_id: str) -> Optional[DatasourceCatalogEntry]:
    for entry in list_catalog_entries():
        if entry.catalog_id == catalog_id:
            return entry
    return None


def list_compiler_catalog_entries() -> List[Dict[str, Any]]:
    return [e.compiler_view() for e in list_catalog_entries() if e.enabled]


def list_runtime_catalog_entries() -> List[Dict[str, Any]]:
    return [e.runtime_view() for e in list_catalog_entries() if e.enabled]
