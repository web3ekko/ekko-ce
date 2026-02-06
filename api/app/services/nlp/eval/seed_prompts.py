from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class NLPEvalCase:
    """
    Seed evaluation case for the NLP compiler.

    Notes:
    - `nl_description` must be end-user intent only (no internal IDs like catalog_ids).
    - `context` models the non-text hints we provide in the UI (e.g. preferred_network).
    - `expected_catalog_ids_any_of` is used by the offline evaluator to sanity-check datasource selection.
    """

    case_id: str
    nl_description: str
    context: Dict[str, Any]
    expected_catalog_ids_any_of: Optional[List[str]] = None
    expected_no_catalog_ids: bool = False
    expected_trigger_modes_any_of: Optional[List[str]] = None
    expected_missing_info_codes_any_of: Optional[List[str]] = None
    expected_variable_ids_all: Optional[List[str]] = None


def seed_prompt_cases() -> List[NLPEvalCase]:
    """
    Initial prompt set (no user data).

    This list is intentionally scoped to current allowlisted datasources and
    current runtime capabilities so we can gate pipeline promotion deterministically.
    """

    return [
        # Tx-only: should compile without DuckLake datasources.
        NLPEvalCase(
            case_id="tx_native_send_gt_1_eth",
            nl_description="Alert me whenever one of my monitored wallets sends more than 1 ETH in a single transaction.",
            context={"preferred_network": "ETH:mainnet"},
            expected_no_catalog_ids=True,
            expected_trigger_modes_any_of=["event_driven", "hybrid"],
        ),
        NLPEvalCase(
            case_id="tx_native_send_gt_0_2_eth",
            nl_description="Alert me whenever one of my monitored wallets sends more than 0.2 ETH in a single transaction.",
            context={"preferred_network": "ETH:mainnet"},
            expected_no_catalog_ids=True,
            expected_trigger_modes_any_of=["event_driven", "hybrid"],
        ),
        NLPEvalCase(
            case_id="tx_native_receive_any",
            nl_description="Alert me whenever one of my monitored wallets receives any ETH transfer.",
            context={"preferred_network": "ETH:mainnet"},
            expected_no_catalog_ids=True,
            expected_trigger_modes_any_of=["event_driven", "hybrid"],
        ),
        NLPEvalCase(
            case_id="tx_native_receive_gt_2_eth",
            nl_description="Alert me whenever one of my monitored wallets receives more than 2 ETH in a single transaction.",
            context={"preferred_network": "ETH:mainnet"},
            expected_no_catalog_ids=True,
            expected_trigger_modes_any_of=["event_driven", "hybrid"],
        ),
        NLPEvalCase(
            case_id="tx_gas_fee_gt_0_02_eth",
            nl_description="Alert me whenever one of my monitored wallets pays more than 0.02 ETH in gas for a single transaction.",
            context={"preferred_network": "ETH:mainnet"},
            expected_no_catalog_ids=True,
            expected_trigger_modes_any_of=["event_driven", "hybrid"],
        ),
        NLPEvalCase(
            case_id="tx_erc20_approve_any",
            nl_description="Alert me whenever one of my monitored wallets approves a token allowance.",
            context={"preferred_network": "ETH:mainnet"},
            expected_no_catalog_ids=True,
            expected_trigger_modes_any_of=["event_driven", "hybrid"],
        ),
        NLPEvalCase(
            case_id="tx_erc20_transfer_any",
            nl_description="Alert me whenever one of my monitored wallets transfers tokens.",
            context={"preferred_network": "ETH:mainnet"},
            expected_no_catalog_ids=True,
            expected_trigger_modes_any_of=["event_driven", "hybrid"],
        ),
        NLPEvalCase(
            case_id="tx_native_receive_any_unspecified_network",
            nl_description="Alert me whenever one of my monitored wallets receives any native token transfer.",
            context={},
            expected_no_catalog_ids=True,
            expected_trigger_modes_any_of=["event_driven", "hybrid"],
            expected_missing_info_codes_any_of=["network_required"],
        ),
        # DuckLake-backed balance checks.
        NLPEvalCase(
            case_id="balance_latest_below_threshold_eth",
            nl_description="Alert me when a monitored wallet balance drops below 0.5 ETH.",
            context={"preferred_network": "ETH:mainnet"},
            expected_catalog_ids_any_of=["ducklake.wallet_balance_latest"],
            expected_trigger_modes_any_of=["periodic", "hybrid"],
        ),
        NLPEvalCase(
            case_id="balance_latest_above_threshold_eth",
            nl_description="Alert me when a monitored wallet balance goes above 5 ETH.",
            context={"preferred_network": "ETH:mainnet"},
            expected_catalog_ids_any_of=["ducklake.wallet_balance_latest"],
            expected_trigger_modes_any_of=["periodic", "hybrid"],
        ),
        NLPEvalCase(
            case_id="balance_latest_zero_eth",
            nl_description="Alert me when a monitored wallet balance hits zero.",
            context={"preferred_network": "ETH:mainnet"},
            expected_catalog_ids_any_of=["ducklake.wallet_balance_latest"],
            expected_trigger_modes_any_of=["periodic", "hybrid"],
        ),
        NLPEvalCase(
            case_id="balance_latest_below_threshold_needs_network",
            nl_description="Alert me when a monitored wallet balance drops below 0.5.",
            context={},
            expected_catalog_ids_any_of=["ducklake.wallet_balance_latest"],
            expected_trigger_modes_any_of=["periodic", "hybrid"],
            expected_missing_info_codes_any_of=["network_required"],
        ),
        NLPEvalCase(
            case_id="balance_latest_above_threshold_avax",
            nl_description="Alert me when a monitored wallet balance goes above 10 AVAX.",
            context={"preferred_network": "AVAX:mainnet"},
            expected_catalog_ids_any_of=["ducklake.wallet_balance_latest"],
            expected_trigger_modes_any_of=["periodic", "hybrid"],
        ),
        NLPEvalCase(
            case_id="balance_latest_below_threshold_avax",
            nl_description="Alert me when a monitored wallet balance drops below 2 AVAX.",
            context={"preferred_network": "AVAX:mainnet"},
            expected_catalog_ids_any_of=["ducklake.wallet_balance_latest"],
            expected_trigger_modes_any_of=["periodic", "hybrid"],
        ),
        NLPEvalCase(
            case_id="balance_window_pct_drop_24h",
            nl_description="Alert me if a monitored wallet balance drops more than 10% over the last 24 hours.",
            context={"preferred_network": "ETH:mainnet"},
            expected_catalog_ids_any_of=["ducklake.wallet_balance_window"],
            expected_trigger_modes_any_of=["periodic", "hybrid"],
            expected_variable_ids_all=["window_duration"],
        ),
        NLPEvalCase(
            case_id="balance_window_pct_drop_1h",
            nl_description="Alert me if a monitored wallet balance drops more than 3% in the last hour.",
            context={"preferred_network": "ETH:mainnet"},
            expected_catalog_ids_any_of=["ducklake.wallet_balance_window"],
            expected_trigger_modes_any_of=["periodic", "hybrid"],
            expected_variable_ids_all=["window_duration"],
        ),
        NLPEvalCase(
            case_id="balance_window_pct_rise_7d",
            nl_description="Alert me if a monitored wallet balance increases more than 25% over the last 7 days.",
            context={"preferred_network": "ETH:mainnet"},
            expected_catalog_ids_any_of=["ducklake.wallet_balance_window"],
            expected_trigger_modes_any_of=["periodic", "hybrid"],
            expected_variable_ids_all=["window_duration"],
        ),
        NLPEvalCase(
            case_id="balance_window_pct_rise_30d",
            nl_description="Alert me if a monitored wallet balance increases more than 50% over the last 30 days.",
            context={"preferred_network": "ETH:mainnet"},
            expected_catalog_ids_any_of=["ducklake.wallet_balance_window"],
            expected_trigger_modes_any_of=["periodic", "hybrid"],
            expected_variable_ids_all=["window_duration"],
        ),
        NLPEvalCase(
            case_id="balance_window_and_floor",
            nl_description="Alert me if a monitored wallet drops more than 10% over 24 hours and is below 0.5 ETH.",
            context={"preferred_network": "ETH:mainnet"},
            expected_catalog_ids_any_of=["ducklake.wallet_balance_window"],
            expected_trigger_modes_any_of=["periodic", "hybrid"],
            expected_variable_ids_all=["window_duration"],
        ),
        NLPEvalCase(
            case_id="balance_window_pct_drop_7d_avax",
            nl_description="Alert me if a monitored wallet balance drops more than 20% over the last 7 days on Avalanche.",
            context={"preferred_network": "AVAX:mainnet"},
            expected_catalog_ids_any_of=["ducklake.wallet_balance_window"],
            expected_trigger_modes_any_of=["periodic", "hybrid"],
            expected_variable_ids_all=["window_duration"],
        ),
        # DuckLake-backed activity checks.
        NLPEvalCase(
            case_id="tx_count_24h_gt_5",
            nl_description="Alert me if a monitored wallet has more than 5 transactions in the last 24 hours.",
            context={"preferred_network": "ETH:mainnet"},
            expected_catalog_ids_any_of=["ducklake.address_transactions_count_24h"],
            expected_trigger_modes_any_of=["periodic", "hybrid"],
        ),
        NLPEvalCase(
            case_id="tx_count_24h_gt_50_avax",
            nl_description="Alert me if a monitored wallet has more than 50 transactions in the last 24 hours.",
            context={"preferred_network": "AVAX:mainnet"},
            expected_catalog_ids_any_of=["ducklake.address_transactions_count_24h"],
            expected_trigger_modes_any_of=["periodic", "hybrid"],
        ),
        NLPEvalCase(
            case_id="tx_count_24h_gt_100",
            nl_description="Alert me if a monitored wallet has more than 100 transactions in the last 24 hours.",
            context={"preferred_network": "ETH:mainnet"},
            expected_catalog_ids_any_of=["ducklake.address_transactions_count_24h"],
            expected_trigger_modes_any_of=["periodic", "hybrid"],
        ),
        NLPEvalCase(
            case_id="tx_count_24h_eq_0",
            nl_description="Alert me if a monitored wallet has zero transactions in the last 24 hours.",
            context={"preferred_network": "ETH:mainnet"},
            expected_catalog_ids_any_of=["ducklake.address_transactions_count_24h"],
            expected_trigger_modes_any_of=["periodic", "hybrid"],
        ),
        NLPEvalCase(
            case_id="tx_count_24h_gt_5_needs_network",
            nl_description="Alert me if a monitored wallet has more than 5 transactions in the last 24 hours.",
            context={},
            expected_catalog_ids_any_of=["ducklake.address_transactions_count_24h"],
            expected_trigger_modes_any_of=["periodic", "hybrid"],
            expected_missing_info_codes_any_of=["network_required"],
        ),
    ]


def seed_prompt_cases_as_dicts() -> List[Dict[str, Any]]:
    return [
        {
            "case_id": c.case_id,
            "nl_description": c.nl_description,
            "context": dict(c.context),
            "expected_catalog_ids_any_of": list(c.expected_catalog_ids_any_of or []),
            "expected_no_catalog_ids": bool(c.expected_no_catalog_ids),
            "expected_trigger_modes_any_of": list(c.expected_trigger_modes_any_of or []),
            "expected_missing_info_codes_any_of": list(c.expected_missing_info_codes_any_of or []),
            "expected_variable_ids_all": list(c.expected_variable_ids_all or []),
        }
        for c in seed_prompt_cases()
    ]
