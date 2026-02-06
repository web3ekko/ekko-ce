"""
Preview Service Module

Provides alert dry-run/preview functionality to test alert conditions
against historical blockchain data before subscribing.

Components:
- PreviewDataFetcher: Queries DuckLake for historical transaction data
- SimpleDjangoEvaluator: Evaluates simple expressions in Django (no wasmCloud)
- PreviewService: Orchestrates preview requests
"""

from .data_fetcher import PreviewDataFetcher, PreviewDataResult, TimeRange
from .evaluator import SimpleDjangoEvaluator, EvaluationResult, EvaluationMode

__all__ = [
    "PreviewDataFetcher",
    "PreviewDataResult",
    "TimeRange",
    "SimpleDjangoEvaluator",
    "EvaluationResult",
    "EvaluationMode",
]
