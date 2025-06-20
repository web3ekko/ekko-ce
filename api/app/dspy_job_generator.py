"""
DSPy-based Job Specification Generator

This module uses DSPy for structured prompting to generate job specifications
from natural language queries. It provides better error handling, optimization
capabilities, and more robust prompt engineering than the previous OpenAI implementation.
"""

import json
import os
import asyncio
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime

import dspy
from pydantic import BaseModel, Field

from .logging_config import job_spec_logger as logger

# ═══════════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════════

# Akash API Configuration from environment variables
AKASH_API_KEY = os.getenv("AKASH_API_KEY", "")
AKASH_BASE_URL = os.getenv("AKASH_BASE_URL", "https://chatapi.akash.network/api/v1")
DEFAULT_MODEL = os.getenv("AKASH_MODEL", "Meta-Llama-3-1-8B-Instruct-FP8")

# ═══════════════════════════════════════════════════════════════════════════════
# Pydantic Models for Type Safety
# ═══════════════════════════════════════════════════════════════════════════════

class DataSource(BaseModel):
    """Data source specification for job"""
    type: str = Field(default="database", description="Source type")
    handle: str = Field(description="Variable name for the data in Polars code")
    stream: str = Field(description="Data stream name")
    subject: str = Field(description="Subject within the stream")
    time_window: str = Field(description="Time window for data retrieval")

class JobSpecification(BaseModel):
    """Complete job specification"""
    job_name: str = Field(description="Snake case job name")
    schedule: str = Field(description="RRULE schedule specification")
    time_window: str = Field(description="Overall time window for the job")
    sources: List[DataSource] = Field(description="List of data sources")
    polars_code: str = Field(description="Polars code to execute")
    alert_id: Optional[str] = Field(default=None, description="Associated alert ID")
    generated_at: Optional[str] = Field(default=None, description="Generation timestamp")

# ═══════════════════════════════════════════════════════════════════════════════
# DSPy Signatures
# ═══════════════════════════════════════════════════════════════════════════════

class AlertTemplateGenerationSignature(dspy.Signature):
    """Generate an alert-specific template from a natural language query"""

    query: str = dspy.InputField(description="Natural language description of the alert requirement")
    alert_template: str = dspy.OutputField(
        description="Complete JSON alert template with Polars DSL, parameter schema, and output mapping"
    )

class PolarsSyntaxValidationSignature(dspy.Signature):
    """Validate and fix Polars code syntax"""
    
    polars_code: str = dspy.InputField(description="Polars code to validate")
    fixed_code: str = dspy.OutputField(description="Corrected Polars code with proper syntax")
    issues_found: str = dspy.OutputField(description="List of issues found and fixed")

# ═══════════════════════════════════════════════════════════════════════════════
# DSPy Modules
# ═══════════════════════════════════════════════════════════════════════════════

class AlertTemplateGenerator(dspy.Module):
    """DSPy module for generating alert-specific templates"""

    def __init__(self):
        super().__init__()
        self.generate_template = dspy.ChainOfThought(AlertTemplateGenerationSignature)
        self.validate_polars = dspy.ChainOfThought(PolarsSyntaxValidationSignature)

    def forward(self, query: str) -> dspy.Prediction:
        """Generate an alert template from a query"""

        # Enhanced prompt with context and examples
        enhanced_query = self._enhance_query(query)

        # Generate the alert template
        template_result = self.generate_template(query=enhanced_query)

        try:
            # Parse the generated JSON
            template_data = json.loads(template_result.alert_template)

            # Validate and fix Polars DSL if present
            polars_issues = ""
            if "polars_template" in template_data:
                polars_result = self.validate_polars(polars_code=template_data["polars_template"])
                template_data["polars_template"] = polars_result.fixed_code
                polars_issues = polars_result.issues_found

                # Log any issues found
                if polars_result.issues_found.strip():
                    logger.info(f"Polars DSL issues fixed: {polars_result.issues_found}")

            # Validate the complete template
            validated_template = self._validate_and_fix_template(template_data)

            return dspy.Prediction(
                alert_template=json.dumps(validated_template),
                polars_issues=polars_issues,
                success=True
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse generated JSON: {e}")
            # Return a fallback template
            fallback_template = self._get_fallback_template(query)
            return dspy.Prediction(
                alert_template=json.dumps(fallback_template),
                polars_issues="JSON parsing failed, using fallback",
                success=False
            )
    
    def _enhance_query(self, query: str) -> str:
        """Enhance the query with context and requirements"""

        context = """
You are an expert in generating Polars DSL templates for blockchain data analytics alerts.
Generate alert-specific templates with executable Polars DSL (Rust syntax) and parameter schemas.

AVAILABLE DATA STORES IN MINIO (Delta Lake format):

1. TRANSACTIONS:
   Location: s3://blockchain-events/transactions/
   Schema: hash(string), from(string), to(string), value(float), token_symbol(string),
           timestamp(timestamp), gas_price(float), network(string), subnet(string)
   Partitions: [network, subnet, date]

2. WALLET_BALANCES:
   Location: s3://blockchain-events/balances/
   Schema: address(string), balance(float), token_symbol(string), timestamp(timestamp), network(string)
   Partitions: [network, date]

3. PRICE_FEEDS:
   Location: s3://blockchain-events/prices/
   Schema: symbol(string), price(float), timestamp(timestamp), exchange(string), volume_24h(float)
   Partitions: [symbol, date]

4. DEFI_YIELDS:
   Location: s3://blockchain-events/yields/
   Schema: protocol(string), pool(string), apr(float), tvl(float), timestamp(timestamp)
   Partitions: [protocol, date]

REQUIRED JSON STRUCTURE:
{
  "alert_id": "descriptive_alert_identifier",
  "alert_type": "wallet_balance|transaction|price|defi_yield",
  "description": "Human readable description",
  "data_sources": ["wallet_balances"],
  "polars_template": "Multi-line Polars DSL with {{PARAMETER}} placeholders",
  "parameter_schema": {
    "PARAMETER_NAME": {
      "type": "string|float|integer|boolean|enum",
      "required": true,
      "description": "Parameter description",
      "pattern": "regex_pattern_for_strings",
      "allowed_values": ["for", "enums"],
      "min": 0,
      "max": 1000
    }
  },
  "output_mapping": {
    "result_column": "column_name_with_boolean_result",
    "value_column": "column_name_with_metric_value",
    "result_type": "boolean",
    "value_type": "float|string|integer"
  }
}

POLARS DSL SYNTAX (Rust):
- col("column_name") for column references
- lit(value) for literal values
- .filter(), .select(), .with_columns(), .sort(), .limit()
- Boolean operations: .and(), .or(), .not()
- Comparisons: .eq(), .lt(), .gt(), .lte(), .gte()
- Aggregations: .count(), .sum(), .avg(), .max(), .min()
- Use {{PARAMETER}} placeholders for dynamic values

TEMPLATE REQUIREMENTS:
1. Generate executable Polars DSL (Rust syntax, no imports)
2. Use {{PARAMETER}} placeholders for dynamic values
3. Always end with a DataFrame that has:
   - A boolean column for the alert condition (result_column)
   - A value column with the relevant metric (value_column)
4. Use proper column aliasing for result extraction
5. Multi-line format for readability

EXAMPLE TEMPLATES:

WALLET BALANCE ALERT:
```rust
let target_wallet = wallet_balances
  .filter(col("address").eq(lit("{{WALLET_ADDRESS}}")))
  .filter(col("token_symbol").eq(lit("{{TOKEN_SYMBOL}}")))
  .filter(col("network").eq(lit("{{NETWORK}}")));

let latest_balance = target_wallet
  .sort([col("timestamp")], [true])
  .limit(1)
  .select([col("balance")]);

let threshold_check = latest_balance
  .with_columns([
    col("balance").lt(lit({{THRESHOLD}})).alias("below_threshold"),
    col("balance").alias("current_value")
  ]);

threshold_check
```

TRANSACTION ALERT:
```rust
let wallet_transactions = transactions
  .filter(
    col("from").eq(lit("{{WALLET_ADDRESS}}"))
    .or(col("to").eq(lit("{{WALLET_ADDRESS}}")))
  )
  .filter(col("token_symbol").eq(lit("{{TOKEN_SYMBOL}}")))
  .filter(col("timestamp").gt(lit("{{TIME_WINDOW}}")));

let transaction_check = wallet_transactions
  .filter(col("value").gt(lit({{THRESHOLD}})))
  .agg([
    col("value").count().alias("transaction_count"),
    col("value").sum().alias("total_value")
  ])
  .with_columns([
    col("transaction_count").gt(lit(0)).alias("has_transactions"),
    col("total_value").alias("current_value")
  ]);

transaction_check
```

PRICE ALERT:
```rust
let latest_price = price_feeds
  .filter(col("symbol").eq(lit("{{ASSET_SYMBOL}}")))
  .sort([col("timestamp")], [true])
  .limit(1);

let price_check = latest_price
  .with_columns([
    col("price").{{COMPARISON}}(lit({{THRESHOLD}})).alias("price_triggered"),
    col("price").alias("current_value")
  ]);

price_check
```

PARAMETER TYPES:
- string: Wallet addresses, token symbols, network names
- float: Thresholds, prices, balances
- integer: Counts, limits
- enum: Comparison operators (lt, gt, eq, lte, gte), networks, tokens
- boolean: Enable/disable flags

Return ONLY valid JSON with the complete alert template, no explanations.
"""

        return f"{context}\n\nUser Query: {query}"
    
    def _validate_and_fix_template(self, template_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and fix common issues in alert template"""

        # Ensure required fields exist
        required_fields = {
            "alert_id": "generic_alert",
            "alert_type": "generic",
            "description": "Generic alert template",
            "data_sources": ["transactions"],
            "polars_template": "transactions.limit(1)",
            "parameter_schema": {},
            "output_mapping": {
                "result_column": "result",
                "value_column": "value",
                "result_type": "boolean",
                "value_type": "string"
            }
        }

        for field, default_value in required_fields.items():
            if field not in template_data:
                template_data[field] = default_value
                logger.warning(f"Added missing field '{field}' with default value")

        # Fix alert_id format
        if "alert_id" in template_data:
            alert_id = template_data["alert_id"]
            # Convert to snake_case
            import re
            fixed_id = re.sub(r'[^a-z0-9_]', '_', alert_id.lower())
            if not fixed_id[0].isalpha():
                fixed_id = "alert_" + fixed_id
            template_data["alert_id"] = fixed_id

        # Ensure data_sources is a list
        if not isinstance(template_data.get("data_sources"), list):
            template_data["data_sources"] = required_fields["data_sources"]
            logger.warning("Fixed data_sources field to be a list")

        # Ensure parameter_schema is a dict
        if not isinstance(template_data.get("parameter_schema"), dict):
            template_data["parameter_schema"] = {}
            logger.warning("Fixed parameter_schema field to be a dict")

        # Ensure output_mapping has required fields
        if not isinstance(template_data.get("output_mapping"), dict):
            template_data["output_mapping"] = required_fields["output_mapping"]
            logger.warning("Fixed output_mapping field")
        else:
            output_mapping = template_data["output_mapping"]
            for key, default in required_fields["output_mapping"].items():
                if key not in output_mapping:
                    output_mapping[key] = default
                    logger.warning(f"Added missing output_mapping field '{key}'")

        return template_data
    
    def _get_fallback_template(self, query: str) -> Dict[str, Any]:
        """Get a fallback alert template when generation fails"""

        # Try to infer alert type from query for better fallback
        query_lower = query.lower()

        if "balance" in query_lower and ("below" in query_lower or "above" in query_lower):
            # Wallet balance alert fallback
            threshold = 10  # Default threshold
            comparison = "below" if "below" in query_lower else "above"
            operator = "lt" if comparison == "below" else "gt"

            return {
                "alert_id": "wallet_balance_alert",
                "alert_type": "wallet_balance",
                "description": f"Alert when wallet balance is {comparison} {threshold}",
                "data_sources": ["wallet_balances"],
                "polars_template": f"""let target_wallet = wallet_balances
  .filter(col("address").eq(lit("{{{{WALLET_ADDRESS}}}}")))
  .filter(col("token_symbol").eq(lit("{{{{TOKEN_SYMBOL}}}}")))
  .filter(col("network").eq(lit("{{{{NETWORK}}}}")));

let latest_balance = target_wallet
  .sort([col("timestamp")], [true])
  .limit(1)
  .select([col("balance")]);

let threshold_check = latest_balance
  .with_columns([
    col("balance").{operator}(lit({{{{THRESHOLD}}}})).alias("below_threshold"),
    col("balance").alias("current_value")
  ]);

threshold_check""",
                "parameter_schema": {
                    "WALLET_ADDRESS": {
                        "type": "string",
                        "required": True,
                        "description": "Wallet address to monitor",
                        "pattern": "^0x[a-fA-F0-9]{40}$"
                    },
                    "TOKEN_SYMBOL": {
                        "type": "string",
                        "required": True,
                        "description": "Token symbol",
                        "allowed_values": ["AVAX", "ETH", "USDC"]
                    },
                    "THRESHOLD": {
                        "type": "float",
                        "required": True,
                        "description": "Balance threshold",
                        "min": 0
                    },
                    "NETWORK": {
                        "type": "string",
                        "required": True,
                        "description": "Blockchain network",
                        "allowed_values": ["avalanche", "ethereum"]
                    }
                },
                "output_mapping": {
                    "result_column": "below_threshold",
                    "value_column": "current_value",
                    "result_type": "boolean",
                    "value_type": "float"
                },
                "fallback_reason": f"Wallet balance fallback from query: {query[:100]}..."
            }

        elif "price" in query_lower and ("above" in query_lower or "below" in query_lower):
            # Price alert fallback
            threshold = 50  # Default price threshold
            comparison = "below" if "below" in query_lower else "above"
            operator = "<" if comparison == "below" else ">"

            return {
                "job_name": "price_alert",
                "schedule": "RRULE:FREQ=MINUTELY;INTERVAL=5",
                "time_window": "-5m..now",
                "sources": [
                    {
                        "type": "database",
                        "handle": "price_data",
                        "stream": "price_feeds",
                        "subject": "prices",
                        "time_window": "-5m..now"
                    }
                ],
                "polars_code": f"""import polars as pl

# Get latest price for AVAX
latest_price = price_data.filter(pl.col('symbol') == 'AVAX').sort(pl.col('timestamp').desc()).limit(1).collect()

# Check if price meets threshold condition
alert_triggered = len(latest_price) > 0 and latest_price[0, 'price'] {operator} {threshold}""",
                "fallback_reason": f"Price alert fallback from query: {query[:100]}..."
            }

        elif "transaction" in query_lower:
            # Transaction alert fallback
            threshold = 5  # Default transaction threshold

            return {
                "job_name": "transaction_alert",
                "schedule": "RRULE:FREQ=MINUTELY;INTERVAL=1",
                "time_window": "-1m..now",
                "sources": [
                    {
                        "type": "database",
                        "handle": "tx_data",
                        "stream": "transactions",
                        "subject": "values",
                        "time_window": "-1m..now"
                    }
                ],
                "polars_code": f"""import polars as pl

# Filter transactions for wallet and amount
filtered_txs = tx_data.filter(
    (pl.col('from') == 'WALLET_ADDRESS') | (pl.col('to') == 'WALLET_ADDRESS')
).filter(pl.col('value') > {threshold}).collect()

# Alert if any transactions found
alert_triggered = len(filtered_txs) > 0""",
                "fallback_reason": f"Transaction alert fallback from query: {query[:100]}..."
            }

        else:
            # Generic fallback
            return {
                "job_name": "generic_alert",
                "schedule": "RRULE:FREQ=DAILY;INTERVAL=1",
                "time_window": "-7d..now",
                "sources": [
                    {
                        "type": "database",
                        "handle": "tx_data",
                        "stream": "transactions",
                        "subject": "values",
                        "time_window": "-7d..now"
                    }
                ],
                "polars_code": """import polars as pl

# Generic alert - check for any activity
result = tx_data.filter(pl.col('value') > 0).collect()

# Alert if any data found
alert_triggered = len(result) > 0""",
                "fallback_reason": f"Generic fallback from query: {query[:100]}..."
            }

# ═══════════════════════════════════════════════════════════════════════════════
# DSPy Configuration and Initialization
# ═══════════════════════════════════════════════════════════════════════════════

def configure_dspy():
    """Configure DSPy with the Akash API"""

    if not AKASH_API_KEY:
        logger.warning("AKASH_API_KEY not set, DSPy configuration may fail")
        return False

    try:
        # Try different DSPy LM configurations based on available classes
        lm = None

        # Try modern DSPy LM configuration
        if hasattr(dspy, 'LM'):
            logger.info("Using dspy.LM for configuration")
            lm = dspy.LM(
                model=f"openai/{DEFAULT_MODEL}",
                api_key=AKASH_API_KEY,
                api_base=AKASH_BASE_URL,
                max_tokens=2048,
                temperature=0.1
            )
        elif hasattr(dspy, 'OpenAI'):
            logger.info("Using dspy.OpenAI for configuration")
            lm = dspy.OpenAI(
                api_key=AKASH_API_KEY,
                api_base=AKASH_BASE_URL,
                model=DEFAULT_MODEL,
                max_tokens=2048,
                temperature=0.1
            )
        elif hasattr(dspy, 'ChatOpenAI'):
            logger.info("Using dspy.ChatOpenAI for configuration")
            lm = dspy.ChatOpenAI(
                api_key=AKASH_API_KEY,
                api_base=AKASH_BASE_URL,
                model=DEFAULT_MODEL,
                max_tokens=2048,
                temperature=0.1
            )
        else:
            # Try using LiteLLM directly
            logger.info("Using LiteLLM configuration")
            import litellm

            # Configure LiteLLM for OpenAI-compatible API
            litellm.api_key = AKASH_API_KEY
            litellm.api_base = AKASH_BASE_URL

            # Create a simple wrapper
            class LiteLLMWrapper:
                def __init__(self):
                    self.model = DEFAULT_MODEL

                def __call__(self, messages, **kwargs):
                    response = litellm.completion(
                        model=self.model,
                        messages=messages,
                        api_key=AKASH_API_KEY,
                        api_base=AKASH_BASE_URL,
                        max_tokens=kwargs.get('max_tokens', 2048),
                        temperature=kwargs.get('temperature', 0.1)
                    )
                    return response

            lm = LiteLLMWrapper()

        if lm is None:
            raise RuntimeError("No compatible DSPy LM class found")

        dspy.settings.configure(lm=lm)
        logger.info(f"DSPy configured with Akash API using model: {DEFAULT_MODEL}")
        return True

    except Exception as e:
        logger.error(f"Failed to configure DSPy: {e}")
        logger.debug(f"Available dspy attributes: {[attr for attr in dir(dspy) if not attr.startswith('_')]}")
        return False

# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

# Global generator instance
_generator = None

def get_alert_template_generator() -> AlertTemplateGenerator:
    """Get or create the alert template generator"""
    global _generator

    if _generator is None:
        if not configure_dspy():
            raise RuntimeError("Failed to configure DSPy")
        _generator = AlertTemplateGenerator()
        logger.info("Alert template generator initialized")

    return _generator

async def generate_alert_template_async(query: str, alert_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Async wrapper for alert template generation

    Args:
        query: Natural language description of the alert requirement
        alert_id: Optional alert ID to associate with the template

    Returns:
        Dictionary containing the alert template

    Raises:
        RuntimeError: If generation fails completely
    """

    try:
        logger.info(f"Generating alert template for query: {query[:100]}...")
        start_time = datetime.now()

        # Get the generator
        generator = get_alert_template_generator()

        # Run the generation in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, generator.forward, query)

        # Parse the result
        alert_template = json.loads(result.alert_template)

        # Add metadata
        if alert_id:
            alert_template["alert_id"] = alert_id
        alert_template["generated_at"] = datetime.now().isoformat()
        alert_template["generation_success"] = result.success

        # Log timing
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"Alert template generated in {elapsed:.2f} seconds")

        return alert_template

    except Exception as e:
        logger.error(f"Alert template generation failed: {e}")
        raise RuntimeError(f"Failed to generate alert template: {e}")

# Backward compatibility - keep the old function name but use new implementation
async def generate_job_specification_async(query: str, alert_id: Optional[str] = None) -> Dict[str, Any]:
    """Backward compatibility wrapper"""
    return await generate_alert_template_async(query, alert_id)

# Backward compatibility function
def generate_job_specification(query: str, model: str = None) -> str:
    """
    Synchronous wrapper for backward compatibility
    
    Args:
        query: Natural language description
        model: Ignored (for compatibility)
        
    Returns:
        JSON string of the job specification
    """
    
    try:
        # Run the async version
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            job_spec = loop.run_until_complete(generate_job_specification_async(query))
            return json.dumps(job_spec)
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Synchronous job specification generation failed: {e}")
        # Return a minimal fallback
        fallback = {
            "job_name": "error_fallback",
            "schedule": "RRULE:FREQ=DAILY;INTERVAL=1",
            "time_window": "-7d..now", 
            "sources": [{"type": "database", "handle": "data", "stream": "transactions", "subject": "values", "time_window": "-7d..now"}],
            "polars_code": "import polars as pl\n\nresult = data.collect()",
            "error": str(e)
        }
        return json.dumps(fallback)
