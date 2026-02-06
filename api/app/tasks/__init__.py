"""
Django 6.0 Tasks for async background processing.

Phase 1: Async NLP parse pipeline.
"""

from .nlp_tasks import parse_nl_description

__all__ = ['parse_nl_description']
