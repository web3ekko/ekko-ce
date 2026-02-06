"""
Simple Django Evaluator

Evaluates simple alert conditions in Django without requiring wasmCloud.
Handles per-row expressions like comparisons and boolean logic.
Complex aggregate expressions (col().last(), sum(), etc.) are rejected
and should be routed to wasmCloud Polars Evaluator.
"""

import ast
import logging
import operator
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class EvaluationMode(Enum):
    """Expression evaluation mode."""
    PER_ROW = "per_row"  # Simple per-row evaluation (Django handles)
    AGGREGATE = "aggregate"  # Aggregate functions (requires wasmCloud)
    WINDOW = "window"  # Window functions (requires wasmCloud)
    UNKNOWN = "unknown"


@dataclass
class EvaluationResult:
    """Result from expression evaluation."""
    success: bool
    matched_rows: List[Dict[str, Any]] = field(default_factory=list)
    total_evaluated: int = 0
    match_count: int = 0
    near_misses: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    evaluation_time_ms: float = 0.0
    mode: EvaluationMode = EvaluationMode.PER_ROW
    expression_parsed: Optional[str] = None


@dataclass
class ExpressionAnalysis:
    """Analysis of an expression to determine evaluation mode."""
    mode: EvaluationMode
    is_simple: bool
    requires_wasmcloud: bool
    reason: Optional[str] = None
    parsed_expression: Optional[str] = None


class ExpressionParser:
    """
    Parses and classifies alert condition expressions.

    Determines whether an expression can be evaluated in Django (simple per-row)
    or requires wasmCloud Polars Evaluator (aggregate/window functions).
    """

    # Patterns that indicate aggregate/window functions (require wasmCloud)
    AGGREGATE_PATTERNS = [
        r"\.last\(\)",
        r"\.first\(\)",
        r"\.sum\(\)",
        r"\.mean\(\)",
        r"\.avg\(\)",
        r"\.count\(\)",
        r"\.max\(\)",
        r"\.min\(\)",
        r"\.std\(\)",
        r"\.var\(\)",
        r"pct_change\(",
        r"rolling_\w+\(",
        r"\.over\(",
        r"\.group_by\(",
        r"col\(['\"]",
        r"pl\.col\(",
    ]

    # Simple comparison operators we can handle
    SIMPLE_OPERATORS = {
        ">": operator.gt,
        "<": operator.lt,
        ">=": operator.ge,
        "<=": operator.le,
        "==": operator.eq,
        "!=": operator.ne,
    }

    # Logical operators
    LOGICAL_OPERATORS = {
        "and": lambda a, b: a and b,
        "or": lambda a, b: a or b,
        "not": lambda a: not a,
    }

    def analyze(self, expression: str) -> ExpressionAnalysis:
        """
        Analyze an expression to determine its evaluation mode.

        Args:
            expression: Condition expression string

        Returns:
            ExpressionAnalysis with mode classification
        """
        expression = expression.strip()

        # Check for aggregate patterns
        for pattern in self.AGGREGATE_PATTERNS:
            if re.search(pattern, expression, re.IGNORECASE):
                return ExpressionAnalysis(
                    mode=EvaluationMode.AGGREGATE,
                    is_simple=False,
                    requires_wasmcloud=True,
                    reason=f"Expression contains aggregate/Polars function: {pattern}",
                    parsed_expression=expression,
                )

        # Check for window function indicators
        if "over(" in expression.lower() or "partition" in expression.lower():
            return ExpressionAnalysis(
                mode=EvaluationMode.WINDOW,
                is_simple=False,
                requires_wasmcloud=True,
                reason="Expression contains window function",
                parsed_expression=expression,
            )

        # If we get here, it should be a simple per-row expression
        return ExpressionAnalysis(
            mode=EvaluationMode.PER_ROW,
            is_simple=True,
            requires_wasmcloud=False,
            parsed_expression=expression,
        )

    def extract_field_references(self, expression: str) -> List[str]:
        """
        Extract field references from an expression.

        Supports formats:
        - field_name
        - $.tx.field_name (JSONPath-like)
        - row['field_name']
        - row.field_name

        Args:
            expression: Condition expression string

        Returns:
            List of field names referenced
        """
        fields = set()

        # Pattern: $.tx.field_name or $.enrichment.field_name
        jsonpath_pattern = r"\$\.(?:tx|enrichment|datasources)\.(\w+)"
        for match in re.finditer(jsonpath_pattern, expression):
            fields.add(match.group(1))

        # Pattern: row['field_name'] or row["field_name"]
        bracket_pattern = r"row\[['\"](\w+)['\"]\]"
        for match in re.finditer(bracket_pattern, expression):
            fields.add(match.group(1))

        # Pattern: row.field_name
        dot_pattern = r"row\.(\w+)"
        for match in re.finditer(dot_pattern, expression):
            fields.add(match.group(1))

        # Pattern: bare field names in comparisons (e.g., value_usd > 1000)
        # This is trickier - look for word characters followed by comparison
        comparison_pattern = r"(\w+)\s*[><=!]+"
        for match in re.finditer(comparison_pattern, expression):
            field_name = match.group(1)
            # Filter out keywords and numbers
            if field_name not in ("and", "or", "not", "true", "false", "none", "null"):
                if not field_name.isdigit():
                    fields.add(field_name)

        return list(fields)


class SimpleDjangoEvaluator:
    """
    Evaluates simple per-row alert conditions in Django.

    Handles expressions like:
    - value_usd > 1000
    - status == 'success'
    - value_usd > 1000 and status == 'success'
    - from_address == '0x...' or to_address == '0x...'

    Complex aggregate expressions are rejected with a clear error.
    """

    # Near-miss threshold (percentage within threshold for near-miss detection)
    NEAR_MISS_THRESHOLD_PERCENT = 10.0

    def __init__(self, near_miss_limit: int = 10):
        """
        Initialize SimpleDjangoEvaluator.

        Args:
            near_miss_limit: Maximum number of near-miss results to return
        """
        self.parser = ExpressionParser()
        self.near_miss_limit = near_miss_limit

    def evaluate(
        self,
        expression: str,
        data: List[Dict[str, Any]],
        include_near_misses: bool = False,
    ) -> EvaluationResult:
        """
        Evaluate expression against data rows.

        Args:
            expression: Condition expression string
            data: List of data rows (dictionaries)
            include_near_misses: Whether to track near-miss results

        Returns:
            EvaluationResult with matched rows and statistics
        """
        import time
        start = time.time()

        # Analyze expression
        analysis = self.parser.analyze(expression)

        # Reject complex expressions
        if analysis.requires_wasmcloud:
            return EvaluationResult(
                success=False,
                error=f"Expression requires wasmCloud evaluation: {analysis.reason}",
                mode=analysis.mode,
                expression_parsed=expression,
            )

        matched_rows = []
        near_misses = []

        try:
            # Parse the expression once
            condition_func, threshold_info = self._compile_expression(expression)

            for row in data:
                try:
                    result = condition_func(row)
                    if result:
                        matched_rows.append(row)
                    elif include_near_misses and threshold_info:
                        # Check for near-misses
                        near_miss = self._check_near_miss(row, threshold_info)
                        if near_miss and len(near_misses) < self.near_miss_limit:
                            near_misses.append(near_miss)
                except (KeyError, TypeError, ValueError) as e:
                    # Skip rows that can't be evaluated (missing fields, etc.)
                    logger.debug(f"Skipped row during evaluation: {e}")
                    continue

            evaluation_time_ms = (time.time() - start) * 1000

            return EvaluationResult(
                success=True,
                matched_rows=matched_rows,
                total_evaluated=len(data),
                match_count=len(matched_rows),
                near_misses=near_misses,
                evaluation_time_ms=evaluation_time_ms,
                mode=EvaluationMode.PER_ROW,
                expression_parsed=expression,
            )

        except Exception as e:
            evaluation_time_ms = (time.time() - start) * 1000
            logger.error(f"Expression evaluation failed: {e}")
            return EvaluationResult(
                success=False,
                total_evaluated=len(data),
                error=str(e),
                evaluation_time_ms=evaluation_time_ms,
                mode=EvaluationMode.PER_ROW,
                expression_parsed=expression,
            )

    def _compile_expression(
        self,
        expression: str,
    ) -> Tuple[Callable[[Dict[str, Any]], bool], Optional[Dict[str, Any]]]:
        """
        Compile expression into a callable function.

        Args:
            expression: Condition expression string

        Returns:
            Tuple of (evaluation function, threshold info for near-miss detection)
        """
        threshold_info = None

        # Normalize the expression
        normalized = self._normalize_expression(expression)

        # Extract threshold for near-miss detection
        threshold_match = re.search(
            r"(\w+)\s*([><=!]+)\s*(\d+(?:\.\d+)?)", normalized
        )
        if threshold_match:
            field_name = threshold_match.group(1)
            op = threshold_match.group(2)
            threshold = float(threshold_match.group(3))
            threshold_info = {
                "field": field_name,
                "operator": op,
                "threshold": threshold,
            }

        # Create evaluation function
        def evaluate_row(row: Dict[str, Any]) -> bool:
            return self._evaluate_normalized(normalized, row)

        return evaluate_row, threshold_info

    def _normalize_expression(self, expression: str) -> str:
        """
        Normalize expression for evaluation.

        Converts various formats to a standard row-based format:
        - $.tx.field_name -> row['field_name']
        - $.enrichment.field_name -> row['field_name']
        - bare field_name -> row['field_name'] (in comparison context)

        Args:
            expression: Original expression string

        Returns:
            Normalized expression string
        """
        normalized = expression

        # Convert JSONPath-like references to row dict access
        # $.tx.field_name -> row['field_name']
        normalized = re.sub(
            r"\$\.(?:tx|enrichment|datasources)\.(\w+)",
            r"row['\1']",
            normalized,
        )

        # Convert {{placeholder}} to row dict access
        normalized = re.sub(r"\{\{(\w+)\}\}", r"row['\1']", normalized)

        # Convert bare field names in comparisons to row dict access
        # field_name > 1000 -> row['field_name'] > 1000
        # But be careful not to convert Python keywords
        keywords = {"and", "or", "not", "true", "false", "none", "True", "False", "None"}

        def replace_bare_field(match):
            field = match.group(1)
            rest = match.group(2)
            if field.lower() in keywords or field.isdigit():
                return match.group(0)
            # Check if already wrapped
            if match.start() > 0 and expression[match.start() - 1] == "'":
                return match.group(0)
            return f"row['{field}']{rest}"

        # Match bare identifiers followed by comparison operators
        normalized = re.sub(
            r"\b(\w+)\s*([><=!]+\s*\d)",
            replace_bare_field,
            normalized,
        )

        # Handle equality with strings: status == 'success'
        normalized = re.sub(
            r"\b(\w+)\s*(==|!=)\s*(['\"])",
            lambda m: f"row['{m.group(1)}'] {m.group(2)} {m.group(3)}"
            if m.group(1).lower() not in keywords
            else m.group(0),
            normalized,
        )

        return normalized

    def _evaluate_normalized(
        self,
        normalized_expression: str,
        row: Dict[str, Any],
    ) -> bool:
        """
        Evaluate a normalized expression against a row.

        Uses safe evaluation with limited builtins.

        Args:
            normalized_expression: Normalized expression string
            row: Data row dictionary

        Returns:
            Boolean result of evaluation
        """
        # Create safe evaluation context
        safe_builtins = {
            "True": True,
            "False": False,
            "None": None,
            "abs": abs,
            "min": min,
            "max": max,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "len": len,
        }

        # Evaluation namespace
        namespace = {"row": row, **safe_builtins}

        try:
            # Use ast.literal_eval for simple literals, eval for expressions
            # First try to parse and validate the expression
            tree = ast.parse(normalized_expression, mode="eval")

            # Validate it only contains safe operations
            self._validate_ast(tree)

            # Evaluate
            result = eval(compile(tree, "<expression>", "eval"), {"__builtins__": {}}, namespace)
            return bool(result)

        except (SyntaxError, ValueError) as e:
            logger.warning(f"Expression parse error: {e}")
            raise ValueError(f"Invalid expression syntax: {e}")

    def _validate_ast(self, tree: ast.AST) -> None:
        """
        Validate AST to ensure only safe operations are used.

        Args:
            tree: AST tree to validate

        Raises:
            ValueError: If unsafe operations are detected
        """
        allowed_nodes = (
            ast.Expression,
            ast.BoolOp,
            ast.Compare,
            ast.BinOp,
            ast.UnaryOp,
            ast.Name,
            ast.Constant,
            ast.Subscript,
            ast.Index,
            ast.Slice,
            ast.Load,
            ast.And,
            ast.Or,
            ast.Not,
            ast.Eq,
            ast.NotEq,
            ast.Lt,
            ast.LtE,
            ast.Gt,
            ast.GtE,
            ast.In,
            ast.NotIn,
            ast.Add,
            ast.Sub,
            ast.Mult,
            ast.Div,
            ast.Mod,
            ast.Str,  # For Python 3.7 compatibility
            ast.Num,  # For Python 3.7 compatibility
        )

        for node in ast.walk(tree):
            if not isinstance(node, allowed_nodes):
                raise ValueError(f"Unsafe operation in expression: {type(node).__name__}")

    def _check_near_miss(
        self,
        row: Dict[str, Any],
        threshold_info: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Check if a row is a near-miss (close to triggering).

        Args:
            row: Data row dictionary
            threshold_info: Threshold information from expression parsing

        Returns:
            Near-miss info dict if row is near threshold, None otherwise
        """
        field = threshold_info["field"]
        op = threshold_info["operator"]
        threshold = threshold_info["threshold"]

        try:
            value = float(row.get(field, 0))
        except (TypeError, ValueError):
            return None

        # Calculate distance from threshold
        if threshold == 0:
            return None

        distance_percent = abs((value - threshold) / threshold) * 100

        # Check if within near-miss threshold
        if distance_percent <= self.NEAR_MISS_THRESHOLD_PERCENT:
            # Verify it didn't actually match
            matched = self._check_condition(value, op, threshold)
            if not matched:
                return {
                    **row,
                    "_near_miss_info": {
                        "field": field,
                        "value": value,
                        "threshold": threshold,
                        "distance_percent": round(distance_percent, 2),
                        "operator": op,
                    },
                }

        return None

    def _check_condition(
        self,
        value: float,
        op: str,
        threshold: float,
    ) -> bool:
        """
        Check a single numeric condition.

        Args:
            value: Actual value
            op: Comparison operator string
            threshold: Threshold value

        Returns:
            Boolean result of comparison
        """
        operators = {
            ">": operator.gt,
            "<": operator.lt,
            ">=": operator.ge,
            "<=": operator.le,
            "==": operator.eq,
            "!=": operator.ne,
        }
        op_func = operators.get(op)
        if op_func:
            return op_func(value, threshold)
        return False

    def can_evaluate(self, expression: str) -> Tuple[bool, Optional[str]]:
        """
        Check if an expression can be evaluated by this evaluator.

        Args:
            expression: Condition expression string

        Returns:
            Tuple of (can_evaluate, reason if cannot)
        """
        analysis = self.parser.analyze(expression)
        if analysis.requires_wasmcloud:
            return False, analysis.reason
        return True, None


# Convenience function for quick evaluations
def evaluate_simple_condition(
    expression: str,
    data: List[Dict[str, Any]],
    include_near_misses: bool = False,
) -> EvaluationResult:
    """
    Evaluate a simple condition expression against data.

    Args:
        expression: Condition expression string
        data: List of data rows
        include_near_misses: Whether to track near-miss results

    Returns:
        EvaluationResult with matched rows and statistics
    """
    evaluator = SimpleDjangoEvaluator()
    return evaluator.evaluate(expression, data, include_near_misses)
