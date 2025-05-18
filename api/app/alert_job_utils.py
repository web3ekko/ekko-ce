"""
Alert to Job Specification Utility

This module provides utilities to generate job specifications from alerts using the Akash Generator.
"""

import json
from typing import Dict, Any, Optional
import traceback

from .akash_generator import generate_job_specification, DEFAULT_MODEL
from .logging_config import job_spec_logger as logger

async def generate_job_spec_from_alert(alert: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Generate a job specification from an alert.
    
    Args:
        alert: The alert data, should contain a query field
        
    Returns:
        Optional[Dict[str, Any]]: The generated job specification or None if generation fails
    """
    alert_id = alert.get('id', 'unknown')
    
    if not alert.get('query'):
        logger.warning(f"[ALERT:{alert_id}] No query provided for alert, skipping job spec generation")
        return None
    
    try:
        query = alert.get('query')
        logger.info(f"[ALERT:{alert_id}] Starting job spec generation with query: '{query}'")
        
        # Use the akash_generator to create a job spec from the query
        logger.debug(f"[ALERT:{alert_id}] Calling Akash Generator API with model: {DEFAULT_MODEL}")
        job_spec_json = generate_job_specification(query, DEFAULT_MODEL)
        
        # Log receipt of response
        logger.debug(f"[ALERT:{alert_id}] Received job spec response of length {len(job_spec_json)} characters")
        
        # Parse the returned JSON string into a dictionary
        job_spec = json.loads(job_spec_json)
        
        # Add alert ID to job spec for reference
        job_spec['alert_id'] = alert_id
        job_spec['generated_at'] = alert.get('time')
        
        # Log job spec details
        job_name = job_spec.get('job_name', 'unnamed')
        sources_count = len(job_spec.get('sources', []))
        schedule = job_spec.get('schedule', 'unspecified')
        
        logger.info(f"[ALERT:{alert_id}] Successfully generated job spec '{job_name}' with {sources_count} sources and schedule '{schedule}'")
        return job_spec
        
    except json.JSONDecodeError as je:
        logger.error(f"[ALERT:{alert_id}] JSON parsing error in job spec: {str(je)}")
        logger.debug(f"[ALERT:{alert_id}] Problematic JSON response: {job_spec_json[:500]}...")
        return None
    except Exception as e:
        logger.error(f"[ALERT:{alert_id}] Error generating job spec: {str(e)}")
        logger.debug(f"[ALERT:{alert_id}] Exception details: {traceback.format_exc()}")
        return None

async def should_run_job_spec(job_spec: Dict[str, Any], current_time: str) -> bool:
    """
    Determine if a job specification should be run based on its schedule.
    
    Args:
        job_spec: The job specification with a schedule
        current_time: Current time in ISO format
        
    Returns:
        bool: True if the job should be run, False otherwise
    """
    try:
        # For now, implement a simple scheduling check
        # In a production system, you'd want to implement a proper RRULE parser
        
        # Default to run the job every time (for testing)
        # Implement proper scheduling logic based on job_spec['schedule']
        return True
        
    except Exception as e:
        logger.error(f"Error checking job schedule: {str(e)}")
        return False
