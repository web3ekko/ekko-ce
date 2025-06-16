#!/usr/bin/env python3
"""
Test script for DSPy Job Specification Generator

This script tests the DSPy-based job specification generation
to ensure it's working correctly for converting natural language
alert queries into Polars code.
"""

import asyncio
import json
import os
import sys

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

async def test_dspy_generator():
    """Test the DSPy job specification generator"""
    
    print("🧪 Testing DSPy Job Specification Generator")
    print("=" * 50)
    
    try:
        from app.dspy_job_generator import generate_job_specification_async, configure_dspy
        
        # Check if DSPy can be configured
        print("1. Configuring DSPy...")
        if not configure_dspy():
            print("❌ Failed to configure DSPy - check AKASH_API_KEY")
            return False
        print("✅ DSPy configured successfully")
        
        # Test queries
        test_queries = [
            "Alert when average transaction value > 1000 AVAX in last 24 hours",
            "Notify me when swap volume exceeds 50000 in the last 7 days",
            "Alert if gas price is above 100 gwei for more than 1 hour",
            "Warn when wallet balance drops below 10 AVAX"
        ]
        
        print(f"\n2. Testing {len(test_queries)} queries...")
        
        for i, query in enumerate(test_queries, 1):
            print(f"\n--- Test {i}: {query[:50]}... ---")
            
            try:
                # Generate job specification
                job_spec = await generate_job_specification_async(query, f"test-alert-{i}")
                
                # Validate the result
                if validate_job_spec(job_spec):
                    print(f"✅ Test {i} passed")
                    print(f"   Job name: {job_spec.get('job_name')}")
                    print(f"   Sources: {len(job_spec.get('sources', []))}")
                    print(f"   Has Polars code: {'polars_code' in job_spec}")
                else:
                    print(f"❌ Test {i} failed validation")
                    
            except Exception as e:
                print(f"❌ Test {i} failed with error: {e}")
        
        print("\n3. Testing backward compatibility...")
        try:
            from app.dspy_job_generator import generate_job_specification
            
            # Test the synchronous wrapper
            result = generate_job_specification("Test backward compatibility query")
            job_spec = json.loads(result)
            
            if validate_job_spec(job_spec):
                print("✅ Backward compatibility test passed")
            else:
                print("❌ Backward compatibility test failed")
                
        except Exception as e:
            print(f"❌ Backward compatibility test failed: {e}")
        
        print("\n🎉 DSPy Generator Testing Complete!")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure DSPy is installed: pip install dspy-ai")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def validate_job_spec(job_spec):
    """Validate that a job specification has the required structure"""
    
    required_fields = ['job_name', 'schedule', 'time_window', 'sources', 'polars_code']
    
    # Check required fields
    for field in required_fields:
        if field not in job_spec:
            print(f"   Missing required field: {field}")
            return False
    
    # Check sources structure
    sources = job_spec.get('sources', [])
    if not isinstance(sources, list) or len(sources) == 0:
        print(f"   Invalid sources: {sources}")
        return False
    
    # Check Polars code
    polars_code = job_spec.get('polars_code', '')
    if not polars_code.startswith('import polars as pl'):
        print(f"   Polars code doesn't start with import: {polars_code[:50]}...")
        return False
    
    if '.collect()' not in polars_code:
        print(f"   Polars code doesn't end with .collect(): {polars_code}")
        return False
    
    return True

def test_environment():
    """Test the environment setup"""
    
    print("🔧 Testing Environment Setup")
    print("=" * 30)
    
    # Check environment variables
    akash_key = os.getenv("AKASH_API_KEY")
    akash_url = os.getenv("AKASH_BASE_URL", "https://chatapi.akash.network/api/v1")
    akash_model = os.getenv("AKASH_MODEL", "Meta-Llama-3-1-8B-Instruct-FP8")
    
    print(f"AKASH_API_KEY: {'✅ Set' if akash_key else '❌ Not set'}")
    print(f"AKASH_BASE_URL: {akash_url}")
    print(f"AKASH_MODEL: {akash_model}")
    
    # Check DSPy installation
    try:
        import dspy
        print(f"✅ DSPy installed: {dspy.__version__}")
    except ImportError:
        print("❌ DSPy not installed")
        return False
    
    return bool(akash_key)

async def main():
    """Main test function"""
    
    print("🚀 DSPy Job Generator Test Suite")
    print("=" * 40)
    
    # Test environment
    if not test_environment():
        print("\n❌ Environment setup failed")
        print("Please set AKASH_API_KEY environment variable")
        return
    
    print("\n" + "=" * 40)
    
    # Test DSPy generator
    success = await test_dspy_generator()
    
    if success:
        print("\n🎉 All tests passed!")
    else:
        print("\n❌ Some tests failed")

if __name__ == "__main__":
    asyncio.run(main())
