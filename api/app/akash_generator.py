#!/usr/bin/env python3
# working!
"""
robust_akash_generator.py - A more robust version of the multi-source job spec generator

This script improves error handling and robustness when dealing with API responses,
while maintaining the strict Polars syntax requirements.

Usage:
    python robust_akash_generator.py "Alert when average swap value > 500 last 7d" --pretty
    
Requirements:
    pip install openai
"""

import json
import textwrap
import re
import sys
import os



from openai import OpenAI

# ═══════════════════════════════════════════════════════════════════════════════
# Configuration - AKASH API Integration
# ═══════════════════════════════════════════════════════════════════════════════

# Akash API Configuration from environment variables
AKASH_API_KEY = os.getenv("AKASH_API_KEY", "")  # Get API key from environment
if not AKASH_API_KEY:
    print("Warning: AKASH_API_KEY environment variable is not set!")
    
AKASH_BASE_URL = os.getenv("AKASH_BASE_URL", "https://chatapi.akash.network/api/v1")
DEFAULT_MODEL = os.getenv("AKASH_MODEL", "Meta-Llama-3-1-8B-Instruct-FP8")

# Create OpenAI client
client = OpenAI(
    api_key=AKASH_API_KEY,
    base_url=AKASH_BASE_URL
)

# ═══════════════════════════════════════════════════════════════════════════════
# Example job spec template for reference
# ═══════════════════════════════════════════════════════════════════════════════

EXAMPLE_JOB_SPEC = {
    "job_name": "average_swap_alert",
    "schedule": "RRULE:FREQ=DAILY;INTERVAL=1",
    "time_window": "-7d..now",
    "sources": [
        {
            "type": "database",
            "handle": "swap_data",
            "stream": "swaps",
            "subject": "values",
            "time_window": "-1d..now"
        }
    ],
    "polars_code": "import polars as pl\n\nresult = swap_data.filter(pl.col('value') > 500).select(pl.col('value').mean()).collect()"
}

# ═══════════════════════════════════════════════════════════════════════════════
# Prompt Templates
# ═══════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = textwrap.dedent("""
You are an expert in creating job specifications for data analytics pipelines using Polars - a high-performance DataFrame library in Rust and Python.
I need a valid JSON job specification to monitor blockchain data and alert when specific conditions are met.
This job spec will be run by a Rust microservice that will first fetch the data and then run the polars code against the data.

Your job is to generate a complete job specification JSON with the following structure:
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
    },
    {
      "type": "database",
      "handle": "user_data",
      "stream": "users",
      "subject": "activity",
      "time_window": "-30d..now"
    }
  ],
  "polars_code": "import polars as pl\\n\\nresult = tx_data.join(user_data, on='user_id').filter(pl.col('value') > 500).collect()"
}

STRICT POLARS SYNTAX REQUIREMENTS:
- Always start with "import polars as pl" on the first line
- For column references, always use pl.col('column_name')
- For filtering, use DataFrame.filter(condition), never DataFrame.where()
- For boolean operations, use & (not 'and' or '&&') and | (not 'or' or '||')
  Example: df.filter((pl.col('x') > 10) & (pl.col('y') < 20))
- For aggregations, use proper Polars methods like .mean(), .sum(), .count() on column expressions
  Example: df.select(pl.col('value').mean())
- Use pl.datetime or pl.date functions for date operations
- Always end chains with .collect() to execute the query

In the polars_code, treat each handle (e.g., tx_data, user_data) as a DIRECT VARIABLE NAME representing a DataFrame.

DO NOT use:
- pl.read_csv(tx_data) (no need to load data)
- tx_data["stream"] or tx_data.stream (accessing as dictionary)
- JavaScript operators (&&, ||) or Python keywords (and, or)
- Do not include a "notify" field in the job specification

Return ONLY THE VALID JSON - no explanations or markdown formatting.
""")

# ═══════════════════════════════════════════════════════════════════════════════
# API Functions
# ═══════════════════════════════════════════════════════════════════════════════

def call_akash_api(prompt: str, model: str = DEFAULT_MODEL) -> str:
    """Call the Akash API and return the response."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt}
    ]
    
    print(f"Sending request to Akash API using model: {model}...")
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.1,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error calling Akash API: {str(e)}")
        raise

def sanitize_and_extract_json(text: str) -> str:
    """
    Carefully sanitize and extract JSON from text, handling control characters and other issues.
    """
    # Strip out any markdown code blocks
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    
    # Find and extract JSON content
    if "{" in text and "}" in text:
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            json_text = text[start:end]
            
            # Replace any problematic control characters
            json_text = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', json_text)
            
            # Replace JavaScript-style logical operators
            json_text = json_text.replace("&&", "&").replace("||", "|")
            
            # Make sure escape sequences in strings are valid
            json_text = re.sub(r'(?<!\\)\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', json_text)
            
            # Test if it parses
            json.loads(json_text)
            return json_text
        except json.JSONDecodeError as e:
            print(f"Warning: Could not parse extracted JSON: {e}")
            print("Attempting alternative extraction method...")
    
    # Try a regex-based approach if the above failed
    try:
        pattern = r'(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})'
        matches = re.findall(pattern, text)
        for potential_json in matches:
            try:
                # Clean up control characters
                cleaned = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', potential_json)
                # Replace JavaScript-style operators
                cleaned = cleaned.replace("&&", "&").replace("||", "|")
                # Parse to verify it's valid JSON
                json.loads(cleaned)
                return cleaned
            except:
                continue
    except:
        pass
    
    # If we still don't have valid JSON, return a minimal template
    print("Warning: Could not extract valid JSON from API response. Using template.")
    return json.dumps(EXAMPLE_JOB_SPEC)

def validate_polars_code(polars_code: str) -> (bool, str):
    """Validate Polars code syntax and structure."""
    issues = []
    
    # Check for required import
    if not polars_code.startswith("import polars as pl"):
        issues.append("Code should start with 'import polars as pl'")
    
    # Check for JavaScript-style logical operators
    if "&&" in polars_code or "||" in polars_code:
        issues.append("JavaScript operators (&&, ||) found - use & and | instead")
    
    # Check for Python logical keywords
    logical_keywords = re.findall(r'\b(and|or|not)\b', polars_code)
    if logical_keywords:
        issues.append(f"Python logical keywords found: {', '.join(logical_keywords)}. Use &, |, ~ instead")
    
    # Check for collect() at the end of operations
    if ".collect()" not in polars_code:
        issues.append("Operations should end with .collect()")
    
    # Check column references
    if "pl.col" not in polars_code:
        issues.append("Column references should use pl.col()")
    
    if issues:
        return False, "\n".join(issues)
    return True, "Polars code looks valid"

def fix_common_issues(job_spec: dict) -> dict:
    """Fix common issues in the generated job specification."""
    fixed_spec = job_spec.copy()
    
    # Ensure polars_code has proper import
    if "polars_code" in fixed_spec:
        polars_code = fixed_spec["polars_code"]
        if not polars_code.startswith("import polars as pl"):
            fixed_spec["polars_code"] = "import polars as pl\n\n" + polars_code
        
        # Fix JavaScript logical operators
        polars_code = fixed_spec["polars_code"]
        fixed_spec["polars_code"] = polars_code.replace("&&", "&").replace("||", "|")
    
    # Remove notify field if present
    if "notify" in fixed_spec:
        del fixed_spec["notify"]
        print("Removed notify field from job specification.")
    
    # Ensure proper job_name format
    if "job_name" in fixed_spec and not re.match(r'^[a-z][a-z0-9_]*$', fixed_spec["job_name"]):
        original_name = fixed_spec["job_name"]
        fixed_name = re.sub(r'[^a-z0-9_]', '_', original_name.lower())
        if not fixed_name[0].isalpha():
            fixed_name = "job_" + fixed_name
        fixed_spec["job_name"] = fixed_name
        print(f"Fixed job_name format: '{original_name}' → '{fixed_name}'")
    
    return fixed_spec

# ═══════════════════════════════════════════════════════════════════════════════
# Main Function
# ═══════════════════════════════════════════════════════════════════════════════

def generate_job_specification(question: str, model: str = DEFAULT_MODEL) -> str:
    """Generate a job specification from a natural language question with robust error handling."""
    # Enhance the prompt with specific requirements based on the query
    prompt = f"Create a job specification for this analytics requirement: {question}\n\nRemember to strictly follow Polars syntax rules and JSON format."
    
    print(f"Generating job spec for: {question}")
    response = call_akash_api(prompt, model=model)
    
    # Extract and sanitize JSON
    job_json_str = sanitize_and_extract_json(response)
    
    try:
        # Parse JSON
        job_spec = json.loads(job_json_str)
        
        # Check required fields
        required_fields = ["job_name", "schedule", "time_window", "sources", "polars_code"]
        missing_fields = [field for field in required_fields if field not in job_spec]
        
        if missing_fields:
            print(f"Warning: Missing required fields: {', '.join(missing_fields)}")
            # Add missing fields from the template
            for field in missing_fields:
                job_spec[field] = EXAMPLE_JOB_SPEC[field]
                print(f"Added default value for {field} from template")
        
        # Check sources structure
        if not isinstance(job_spec.get("sources", []), list) or len(job_spec.get("sources", [])) == 0:
            print("Warning: sources must be a non-empty array. Adding default source.")
            job_spec["sources"] = EXAMPLE_JOB_SPEC["sources"]
        
        # Validate Polars code
        if "polars_code" in job_spec:
            valid, issues = validate_polars_code(job_spec["polars_code"])
            if not valid:
                print(f"Warning: Issues with Polars code:\n{issues}")
        
        # Fix common issues
        job_spec = fix_common_issues(job_spec)
        
        # Final validation
        handles = [source.get("handle", "") for source in job_spec.get("sources", [])]
        any_handle_referenced = any(handle in job_spec.get("polars_code", "") for handle in handles if handle)
        
        if not any_handle_referenced and handles:
            print(f"Warning: polars_code does not reference any source handles: {', '.join(handles)}")
        
        print("Job specification generated and validated successfully!")
        return json.dumps(job_spec)
        
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse JSON: {str(e)}")
        return job_json_str  # Return the raw sanitized string
    except Exception as e:
        print(f"Error during job spec validation: {str(e)}")
        return job_json_str  # Return the raw sanitized string

# ═══════════════════════════════════════════════════════════════════════════════
# CLI Interface
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate a robust job specification using AKASH API")
    parser.add_argument("text", type=str, nargs="+", help="Natural language description of the job")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help=f"Model to use (default: {DEFAULT_MODEL})")
    parser.add_argument("--output", "-o", type=str, help="Output file (default: stdout)")
    parser.add_argument("--pretty", "-p", action="store_true", help="Pretty print the JSON output")
    
    args = parser.parse_args()
    
    # Join text arguments
    text = " ".join(args.text)
    
    try:
        # Generate job specification
        jobspec_json = generate_job_specification(text, args.model)
        
        # Format the JSON if pretty printing is requested
        if args.pretty:
            try:
                parsed_json = json.loads(jobspec_json)
                jobspec_json = json.dumps(parsed_json, indent=2)
            except:
                print("Warning: Could not pretty-print JSON. Returning raw string.")
        
        # Output to file or stdout
        if args.output:
            with open(args.output, "w") as f:
                f.write(jobspec_json)
            print(f"Job specification written to {args.output}")
        else:
            print("\nGenerated Job Specification:")
            print(jobspec_json)
            
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)