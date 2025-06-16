"""
Alert to Job Specification Utility

This module provides utilities to generate job specifications from alerts using DSPy.
"""

from typing import Dict, Any, Optional
import traceback

from .dspy_job_generator import generate_job_specification_async, DEFAULT_MODEL
from .logging_config import job_spec_logger as logger

async def generate_job_spec_from_alert(alert: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Generate a job specification from an alert using DSPy.

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
        logger.info(f"[ALERT:{alert_id}] Starting DSPy job spec generation with query: '{query}'")

        # Use the DSPy generator to create a job spec from the query
        logger.debug(f"[ALERT:{alert_id}] Calling DSPy Job Generator with model: {DEFAULT_MODEL}")
        job_spec = await generate_job_specification_async(query, alert_id)

        # Log job spec details
        job_name = job_spec.get('job_name', 'unnamed')
        sources_count = len(job_spec.get('sources', []))
        schedule = job_spec.get('schedule', 'unspecified')
        generation_success = job_spec.get('generation_success', True)

        if generation_success:
            logger.info(f"[ALERT:{alert_id}] Successfully generated job spec '{job_name}' with {sources_count} sources and schedule '{schedule}'")
        else:
            logger.warning(f"[ALERT:{alert_id}] Job spec generated with fallback: '{job_name}'")

        return job_spec

    except Exception as e:
        logger.error(f"[ALERT:{alert_id}] Error generating job spec with DSPy: {str(e)}")
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

        schedule = job_spec.get('schedule', '')
        logger.debug(f"Checking schedule: {schedule} at time: {current_time}")

        # Default to run the job every time (for testing)
        # TODO: Implement proper scheduling logic based on job_spec['schedule']
        return True

    except Exception as e:
        logger.error(f"Error checking job schedule: {str(e)}")
        return False
