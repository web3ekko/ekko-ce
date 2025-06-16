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

class JobSpecGenerationSignature(dspy.Signature):
    """Generate a job specification from a natural language query"""
    
    query: str = dspy.InputField(description="Natural language description of the analytics requirement")
    job_specification: str = dspy.OutputField(
        description="Complete JSON job specification following the required schema"
    )

class PolarsSyntaxValidationSignature(dspy.Signature):
    """Validate and fix Polars code syntax"""
    
    polars_code: str = dspy.InputField(description="Polars code to validate")
    fixed_code: str = dspy.OutputField(description="Corrected Polars code with proper syntax")
    issues_found: str = dspy.OutputField(description="List of issues found and fixed")

# ═══════════════════════════════════════════════════════════════════════════════
# DSPy Modules
# ═══════════════════════════════════════════════════════════════════════════════

class JobSpecGenerator(dspy.Module):
    """DSPy module for generating job specifications"""
    
    def __init__(self):
        super().__init__()
        self.generate_spec = dspy.ChainOfThought(JobSpecGenerationSignature)
        self.validate_polars = dspy.ChainOfThought(PolarsSyntaxValidationSignature)
    
    def forward(self, query: str) -> dspy.Prediction:
        """Generate a job specification from a query"""
        
        # Enhanced prompt with context and examples
        enhanced_query = self._enhance_query(query)
        
        # Generate the job specification
        spec_result = self.generate_spec(query=enhanced_query)
        
        try:
            # Parse the generated JSON
            job_data = json.loads(spec_result.job_specification)
            
            # Validate and fix Polars code if present
            if "polars_code" in job_data:
                polars_result = self.validate_polars(polars_code=job_data["polars_code"])
                job_data["polars_code"] = polars_result.fixed_code
                
                # Log any issues found
                if polars_result.issues_found.strip():
                    logger.info(f"Polars code issues fixed: {polars_result.issues_found}")
            
            # Validate the complete specification
            validated_spec = self._validate_and_fix_spec(job_data)
            
            return dspy.Prediction(
                job_specification=json.dumps(validated_spec),
                polars_issues=polars_result.issues_found if "polars_code" in job_data else "",
                success=True
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse generated JSON: {e}")
            # Return a fallback specification
            fallback_spec = self._get_fallback_spec(query)
            return dspy.Prediction(
                job_specification=json.dumps(fallback_spec),
                polars_issues="JSON parsing failed, using fallback",
                success=False
            )
    
    def _enhance_query(self, query: str) -> str:
        """Enhance the query with context and requirements"""
        
        context = """
You are an expert in creating job specifications for blockchain data analytics using Polars.

REQUIRED JSON STRUCTURE:
{
  "job_name": "snake_case_name",
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
  "polars_code": "import polars as pl\\n\\nresult = tx_data.filter(pl.col('value') > 500).collect()"
}

POLARS SYNTAX REQUIREMENTS:
- Always start with "import polars as pl"
- Use pl.col('column_name') for column references
- Use DataFrame.filter() not DataFrame.where()
- Use & and | for boolean operations (not && || and or)
- End with .collect() to execute queries
- Treat source handles as direct DataFrame variables

BLOCKCHAIN DATA CONTEXT:
- Common streams: transactions, swaps, transfers, blocks
- Common fields: value, from, to, hash, timestamp, gas_price
- Time windows: -1d..now, -7d..now, -30d..now
- Networks: avalanche, ethereum
- Subnets: mainnet, fuji, testnet

Return ONLY valid JSON, no explanations.
"""
        
        return f"{context}\n\nUser Query: {query}"
    
    def _validate_and_fix_spec(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and fix common issues in job specification"""
        
        # Ensure required fields exist
        required_fields = {
            "job_name": "blockchain_alert",
            "schedule": "RRULE:FREQ=DAILY;INTERVAL=1", 
            "time_window": "-7d..now",
            "sources": [{"type": "database", "handle": "data", "stream": "transactions", "subject": "values", "time_window": "-7d..now"}],
            "polars_code": "import polars as pl\n\nresult = data.collect()"
        }
        
        for field, default_value in required_fields.items():
            if field not in job_data:
                job_data[field] = default_value
                logger.warning(f"Added missing field '{field}' with default value")
        
        # Fix job name format
        if "job_name" in job_data:
            job_name = job_data["job_name"]
            # Convert to snake_case
            import re
            fixed_name = re.sub(r'[^a-z0-9_]', '_', job_name.lower())
            if not fixed_name[0].isalpha():
                fixed_name = "job_" + fixed_name
            job_data["job_name"] = fixed_name
        
        # Ensure sources is a list
        if not isinstance(job_data.get("sources"), list):
            job_data["sources"] = required_fields["sources"]
            logger.warning("Fixed sources field to be a list")
        
        # Remove any unwanted fields
        unwanted_fields = ["notify", "notification"]
        for field in unwanted_fields:
            if field in job_data:
                del job_data[field]
                logger.info(f"Removed unwanted field: {field}")
        
        return job_data
    
    def _get_fallback_spec(self, query: str) -> Dict[str, Any]:
        """Get a fallback job specification when generation fails"""
        
        return {
            "job_name": "fallback_alert",
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
            "polars_code": "import polars as pl\n\nresult = tx_data.filter(pl.col('value') > 0).collect()",
            "fallback_reason": f"Failed to generate from query: {query[:100]}..."
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
        # Configure DSPy to use OpenAI-compatible API (Akash)
        lm = dspy.OpenAI(
            api_key=AKASH_API_KEY,
            api_base=AKASH_BASE_URL,
            model=DEFAULT_MODEL,
            max_tokens=2048,
            temperature=0.1
        )
        
        dspy.settings.configure(lm=lm)
        logger.info(f"DSPy configured with Akash API using model: {DEFAULT_MODEL}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to configure DSPy: {e}")
        return False

# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

# Global generator instance
_generator = None

def get_job_generator() -> JobSpecGenerator:
    """Get or create the job specification generator"""
    global _generator
    
    if _generator is None:
        if not configure_dspy():
            raise RuntimeError("Failed to configure DSPy")
        _generator = JobSpecGenerator()
        logger.info("Job specification generator initialized")
    
    return _generator

async def generate_job_specification_async(query: str, alert_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Async wrapper for job specification generation
    
    Args:
        query: Natural language description of the analytics requirement
        alert_id: Optional alert ID to associate with the job spec
        
    Returns:
        Dictionary containing the job specification
        
    Raises:
        RuntimeError: If generation fails completely
    """
    
    try:
        logger.info(f"Generating job specification for query: {query[:100]}...")
        start_time = datetime.now()
        
        # Get the generator
        generator = get_job_generator()
        
        # Run the generation in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, generator.forward, query)
        
        # Parse the result
        job_spec = json.loads(result.job_specification)
        
        # Add metadata
        if alert_id:
            job_spec["alert_id"] = alert_id
        job_spec["generated_at"] = datetime.now().isoformat()
        job_spec["generation_success"] = result.success
        
        # Log timing
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"Job specification generated in {elapsed:.2f} seconds")
        
        return job_spec
        
    except Exception as e:
        logger.error(f"Job specification generation failed: {e}")
        raise RuntimeError(f"Failed to generate job specification: {e}")

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
