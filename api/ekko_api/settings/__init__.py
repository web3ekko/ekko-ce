"""
Django settings module for Ekko API
Automatically loads the appropriate settings based on environment
"""

import os

# Determine which settings to use
ENVIRONMENT = os.getenv('DJANGO_SETTINGS_MODULE', 'ekko_api.settings.base')

if ENVIRONMENT.endswith('.test'):
    from .test import *
elif ENVIRONMENT.endswith('.production'):
    from .production import *
else:
    from .base import *
