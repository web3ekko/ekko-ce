"""
Alert Template Processing Engine

This module provides utilities to process DSPy-generated alert templates
by substituting parameters and validating the resulting Polars DSL.
"""

import re
import json
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import logging

from .logging_config import job_spec_logger as logger

# ═══════════════════════════════════════════════════════════════════════════════
# Parameter Types and Validation
# ═══════════════════════════════════════════════════════════════════════════════

class ParameterValidationError(Exception):
    """Raised when parameter validation fails"""
    pass

class TemplateProcessingError(Exception):
    """Raised when template processing fails"""
    pass

def extract_placeholders(template: str) -> List[str]:
    """
    Extract all {{PARAMETER}} placeholders from template
    
    Args:
        template: Template string with placeholders
        
    Returns:
        List of unique parameter names
    """
    pattern = r'\{\{([A-Z_][A-Z0-9_]*)\}\}'
    matches = re.findall(pattern, template)
    return list(set(matches))  # Remove duplicates

def validate_parameter_value(param_name: str, param_value: Any, param_schema: Dict[str, Any]) -> None:
    """
    Validate a single parameter value against its schema
    
    Args:
        param_name: Name of the parameter
        param_value: Value to validate
        param_schema: Schema definition for the parameter
        
    Raises:
        ParameterValidationError: If validation fails
    """
    param_type = param_schema.get("type", "string")
    required = param_schema.get("required", False)
    
    # Check if required parameter is missing
    if required and param_value is None:
        raise ParameterValidationError(f"Required parameter '{param_name}' is missing")
    
    # Skip validation for optional parameters that are None
    if param_value is None:
        return
    
    # Type-specific validation
    if param_type == "string":
        if not isinstance(param_value, str):
            raise ParameterValidationError(f"Parameter '{param_name}' must be a string, got {type(param_value)}")
        
        # Pattern validation
        if "pattern" in param_schema:
            pattern = param_schema["pattern"]
            if not re.match(pattern, param_value):
                raise ParameterValidationError(f"Parameter '{param_name}' doesn't match pattern: {pattern}")
        
        # Allowed values validation
        if "allowed_values" in param_schema:
            allowed = param_schema["allowed_values"]
            if param_value not in allowed:
                raise ParameterValidationError(f"Parameter '{param_name}' must be one of {allowed}, got '{param_value}'")
    
    elif param_type in ["float", "integer"]:
        if param_type == "integer" and not isinstance(param_value, int):
            raise ParameterValidationError(f"Parameter '{param_name}' must be an integer, got {type(param_value)}")
        elif param_type == "float" and not isinstance(param_value, (int, float)):
            raise ParameterValidationError(f"Parameter '{param_name}' must be a number, got {type(param_value)}")
        
        # Range validation
        if "min" in param_schema and param_value < param_schema["min"]:
            raise ParameterValidationError(f"Parameter '{param_name}' must be >= {param_schema['min']}, got {param_value}")
        if "max" in param_schema and param_value > param_schema["max"]:
            raise ParameterValidationError(f"Parameter '{param_name}' must be <= {param_schema['max']}, got {param_value}")
    
    elif param_type == "boolean":
        if not isinstance(param_value, bool):
            raise ParameterValidationError(f"Parameter '{param_name}' must be a boolean, got {type(param_value)}")
    
    elif param_type == "enum":
        allowed_values = param_schema.get("allowed_values", [])
        if param_value not in allowed_values:
            raise ParameterValidationError(f"Parameter '{param_name}' must be one of {allowed_values}, got '{param_value}'")
    
    elif param_type == "array":
        if not isinstance(param_value, list):
            raise ParameterValidationError(f"Parameter '{param_name}' must be an array, got {type(param_value)}")
    
    else:
        raise ParameterValidationError(f"Unsupported parameter type '{param_type}' for parameter '{param_name}'")

def format_parameter_value(param_value: Any, param_schema: Dict[str, Any]) -> str:
    """
    Format parameter value for Polars DSL substitution
    
    Args:
        param_value: The parameter value
        param_schema: Schema definition for the parameter
        
    Returns:
        Formatted string for DSL substitution
    """
    param_type = param_schema.get("type", "string")
    
    if param_value is None:
        return "null"
    
    if param_type == "string":
        # Escape quotes and wrap in quotes for Polars DSL
        escaped = str(param_value).replace('"', '\\"')
        return f'"{escaped}"'
    
    elif param_type in ["float", "integer"]:
        # Direct numeric value
        return str(param_value)
    
    elif param_type == "boolean":
        # Rust boolean literals
        return "true" if param_value else "false"
    
    elif param_type == "enum":
        # Treat enums as strings for DSL
        escaped = str(param_value).replace('"', '\\"')
        return f'"{escaped}"'
    
    elif param_type == "array":
        # Format as Rust array literal
        formatted_items = []
        for item in param_value:
            if isinstance(item, str):
                escaped = item.replace('"', '\\"')
                formatted_items.append(f'"{escaped}"')
            else:
                formatted_items.append(str(item))
        return f"[{', '.join(formatted_items)}]"
    
    else:
        # Default to string formatting
        escaped = str(param_value).replace('"', '\\"')
        return f'"{escaped}"'

def validate_parameters(parameters: Dict[str, Any], parameter_schema: Dict[str, Dict[str, Any]]) -> None:
    """
    Validate all parameters against their schemas
    
    Args:
        parameters: Dictionary of parameter values
        parameter_schema: Dictionary of parameter schemas
        
    Raises:
        ParameterValidationError: If any validation fails
    """
    # Check that all required parameters are provided
    for param_name, schema in parameter_schema.items():
        if schema.get("required", False) and param_name not in parameters:
            raise ParameterValidationError(f"Required parameter '{param_name}' is missing")
    
    # Validate each provided parameter
    for param_name, param_value in parameters.items():
        if param_name not in parameter_schema:
            logger.warning(f"Unknown parameter '{param_name}' provided")
            continue
        
        validate_parameter_value(param_name, param_value, parameter_schema[param_name])

def substitute_template_parameters(template: str, parameters: Dict[str, Any], parameter_schema: Dict[str, Dict[str, Any]]) -> str:
    """
    Substitute parameters in template with actual values
    
    Args:
        template: Template string with {{PARAMETER}} placeholders
        parameters: Dictionary of parameter values
        parameter_schema: Dictionary of parameter schemas
        
    Returns:
        Template with parameters substituted
        
    Raises:
        TemplateProcessingError: If substitution fails
    """
    try:
        # Validate parameters first
        validate_parameters(parameters, parameter_schema)
        
        # Extract placeholders from template
        placeholders = extract_placeholders(template)
        
        # Substitute each placeholder
        result_template = template
        for placeholder in placeholders:
            if placeholder not in parameters:
                # Use default value if available
                schema = parameter_schema.get(placeholder, {})
                if "default" in schema:
                    param_value = schema["default"]
                else:
                    raise TemplateProcessingError(f"No value provided for placeholder '{placeholder}'")
            else:
                param_value = parameters[placeholder]
            
            # Format the value for DSL
            schema = parameter_schema.get(placeholder, {})
            formatted_value = format_parameter_value(param_value, schema)
            
            # Replace placeholder with formatted value
            placeholder_pattern = f"{{{{{placeholder}}}}}"
            result_template = result_template.replace(placeholder_pattern, formatted_value)
        
        return result_template
        
    except Exception as e:
        raise TemplateProcessingError(f"Failed to substitute template parameters: {str(e)}")

def validate_polars_dsl_syntax(dsl: str) -> List[str]:
    """
    Basic validation of Polars DSL syntax
    
    Args:
        dsl: Polars DSL string to validate
        
    Returns:
        List of validation warnings/issues found
    """
    issues = []
    
    # Check for common syntax issues
    if "import " in dsl:
        issues.append("DSL should not contain import statements")
    
    if ".collect()" in dsl:
        issues.append("DSL should not contain .collect() calls")
    
    # Check for balanced parentheses
    open_parens = dsl.count("(")
    close_parens = dsl.count(")")
    if open_parens != close_parens:
        issues.append(f"Unbalanced parentheses: {open_parens} open, {close_parens} close")
    
    # Check for balanced brackets
    open_brackets = dsl.count("[")
    close_brackets = dsl.count("]")
    if open_brackets != close_brackets:
        issues.append(f"Unbalanced brackets: {open_brackets} open, {close_brackets} close")
    
    # Check for remaining placeholders
    remaining_placeholders = extract_placeholders(dsl)
    if remaining_placeholders:
        issues.append(f"Unsubstituted placeholders found: {remaining_placeholders}")
    
    return issues

# ═══════════════════════════════════════════════════════════════════════════════
# Main Template Processing Functions
# ═══════════════════════════════════════════════════════════════════════════════

def process_alert_template(alert_template: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process an alert template by substituting parameters and validating the result

    Args:
        alert_template: DSPy-generated alert template
        parameters: Dictionary of parameter values to substitute

    Returns:
        Dictionary containing processed template with executable DSL

    Raises:
        TemplateProcessingError: If processing fails
    """
    try:
        logger.info(f"Processing alert template: {alert_template.get('alert_id', 'unknown')}")
        start_time = datetime.now()

        # Extract required components from template
        polars_template = alert_template.get("polars_template", "")
        parameter_schema = alert_template.get("parameter_schema", {})
        output_mapping = alert_template.get("output_mapping", {})

        if not polars_template:
            raise TemplateProcessingError("Alert template missing polars_template")

        # Substitute parameters in the template
        executable_dsl = substitute_template_parameters(polars_template, parameters, parameter_schema)

        # Validate the resulting DSL
        validation_issues = validate_polars_dsl_syntax(executable_dsl)
        if validation_issues:
            logger.warning(f"DSL validation issues found: {validation_issues}")

        # Build the processed result
        processed_template = {
            "alert_id": alert_template.get("alert_id"),
            "alert_type": alert_template.get("alert_type"),
            "description": alert_template.get("description"),
            "data_sources": alert_template.get("data_sources", []),
            "executable_dsl": executable_dsl,
            "output_mapping": output_mapping,
            "parameters_used": parameters,
            "validation_issues": validation_issues,
            "processed_at": datetime.now().isoformat(),
            "processing_time_ms": int((datetime.now() - start_time).total_seconds() * 1000)
        }

        logger.info(f"Template processed successfully in {processed_template['processing_time_ms']}ms")
        return processed_template

    except Exception as e:
        logger.error(f"Failed to process alert template: {str(e)}")
        raise TemplateProcessingError(f"Template processing failed: {str(e)}")

def create_executable_alert(alert_template: Dict[str, Any], user_parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create an executable alert from a template and user parameters

    Args:
        alert_template: DSPy-generated alert template
        user_parameters: User-provided parameter values

    Returns:
        Dictionary containing executable alert specification
    """
    try:
        # Process the template with user parameters
        processed = process_alert_template(alert_template, user_parameters)

        # Create executable alert specification
        executable_alert = {
            "alert_id": processed["alert_id"],
            "alert_type": processed["alert_type"],
            "description": processed["description"],
            "data_sources": processed["data_sources"],
            "polars_dsl": processed["executable_dsl"],
            "output_mapping": processed["output_mapping"],
            "parameters": processed["parameters_used"],
            "created_at": datetime.now().isoformat(),
            "status": "ready",
            "validation_issues": processed.get("validation_issues", [])
        }

        return executable_alert

    except Exception as e:
        logger.error(f"Failed to create executable alert: {str(e)}")
        raise TemplateProcessingError(f"Executable alert creation failed: {str(e)}")

# ═══════════════════════════════════════════════════════════════════════════════
# Utility Functions
# ═══════════════════════════════════════════════════════════════════════════════

def get_template_parameter_info(alert_template: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract parameter information from an alert template

    Args:
        alert_template: DSPy-generated alert template

    Returns:
        Dictionary with parameter information for UI display
    """
    parameter_schema = alert_template.get("parameter_schema", {})
    polars_template = alert_template.get("polars_template", "")

    # Extract placeholders from template
    placeholders = extract_placeholders(polars_template)

    # Build parameter info
    parameter_info = {
        "required_parameters": [],
        "optional_parameters": [],
        "total_parameters": len(placeholders),
        "template_placeholders": placeholders
    }

    for param_name in placeholders:
        schema = parameter_schema.get(param_name, {})
        param_info = {
            "name": param_name,
            "type": schema.get("type", "string"),
            "description": schema.get("description", f"Parameter {param_name}"),
            "required": schema.get("required", False),
            "default": schema.get("default"),
            "allowed_values": schema.get("allowed_values"),
            "min": schema.get("min"),
            "max": schema.get("max"),
            "pattern": schema.get("pattern")
        }

        if param_info["required"]:
            parameter_info["required_parameters"].append(param_info)
        else:
            parameter_info["optional_parameters"].append(param_info)

    return parameter_info

def preview_dsl_with_sample_parameters(alert_template: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a preview of the DSL with sample parameter values

    Args:
        alert_template: DSPy-generated alert template

    Returns:
        Dictionary with sample DSL and parameter values
    """
    try:
        parameter_schema = alert_template.get("parameter_schema", {})
        polars_template = alert_template.get("polars_template", "")

        # Generate sample parameters
        sample_parameters = {}
        for param_name, schema in parameter_schema.items():
            param_type = schema.get("type", "string")

            if param_type == "string":
                if "allowed_values" in schema:
                    sample_parameters[param_name] = schema["allowed_values"][0]
                elif param_name == "WALLET_ADDRESS":
                    sample_parameters[param_name] = "0x1234567890abcdef1234567890abcdef12345678"
                else:
                    sample_parameters[param_name] = f"sample_{param_name.lower()}"

            elif param_type in ["float", "integer"]:
                min_val = schema.get("min", 0)
                max_val = schema.get("max", 100)
                sample_parameters[param_name] = min_val + (max_val - min_val) / 2

            elif param_type == "boolean":
                sample_parameters[param_name] = True

            elif param_type == "enum":
                allowed_values = schema.get("allowed_values", ["sample"])
                sample_parameters[param_name] = allowed_values[0]

        # Generate sample DSL
        sample_dsl = substitute_template_parameters(polars_template, sample_parameters, parameter_schema)

        return {
            "sample_parameters": sample_parameters,
            "sample_dsl": sample_dsl,
            "parameter_count": len(sample_parameters)
        }

    except Exception as e:
        logger.error(f"Failed to generate DSL preview: {str(e)}")
        return {
            "sample_parameters": {},
            "sample_dsl": polars_template,
            "error": str(e)
        }
