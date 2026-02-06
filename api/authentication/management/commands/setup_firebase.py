"""
Django management command to help set up Firebase configuration
"""

from django.core.management.base import BaseCommand
from django.conf import settings
import os
import json


class Command(BaseCommand):
    help = 'Help set up Firebase configuration for ekko authentication'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check',
            action='store_true',
            help='Check current Firebase configuration status',
        )
        parser.add_argument(
            '--service-account',
            type=str,
            help='Path to Firebase service account JSON file',
        )
        parser.add_argument(
            '--project-id',
            type=str,
            help='Firebase project ID',
        )
        parser.add_argument(
            '--web-api-key',
            type=str,
            help='Firebase web API key',
        )
        parser.add_argument(
            '--auth-domain',
            type=str,
            help='Firebase auth domain',
        )

    def handle(self, *args, **options):
        if options['check']:
            self.check_firebase_config()
        else:
            self.setup_firebase_config(options)

    def check_firebase_config(self):
        """Check current Firebase configuration"""
        self.stdout.write(self.style.HTTP_INFO('🔍 Checking Firebase Configuration...'))
        
        try:
            from authentication.firebase_utils import firebase_auth_manager
            
            # Check if Firebase is available
            is_available = firebase_auth_manager.is_available()
            
            if is_available:
                self.stdout.write(self.style.SUCCESS('✅ Firebase is properly configured and available'))
                
                # Show configuration details
                firebase_config = getattr(settings, 'FIREBASE_ADMIN_CONFIG', {})
                web_config = getattr(settings, 'FIREBASE_WEB_CONFIG', {})
                
                self.stdout.write('\n📋 Configuration Details:')
                self.stdout.write(f'   Project ID: {firebase_config.get("project_id", "Not set")}')
                self.stdout.write(f'   Credentials Path: {firebase_config.get("credentials_path", "Not set")}')
                self.stdout.write(f'   Service Account Key: {"Set" if firebase_config.get("service_account_key") else "Not set"}')
                self.stdout.write(f'   Web API Key: {"Set" if web_config.get("apiKey") else "Not set"}')
                self.stdout.write(f'   Auth Domain: {web_config.get("authDomain", "Not set")}')
                
            else:
                self.stdout.write(self.style.WARNING('⚠️  Firebase is not configured'))
                self.stdout.write('   Firebase features will be disabled')
                self.stdout.write('   Authentication will work with Django-only features')
                
                self.stdout.write('\n🔧 To configure Firebase:')
                self.stdout.write('   1. Create a Firebase project at https://console.firebase.google.com/')
                self.stdout.write('   2. Enable Authentication with Email/Password and Email Link')
                self.stdout.write('   3. Generate a service account key')
                self.stdout.write('   4. Run: python manage.py setup_firebase --help')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error checking Firebase configuration: {e}'))

    def setup_firebase_config(self, options):
        """Set up Firebase configuration"""
        self.stdout.write(self.style.HTTP_INFO('🔧 Setting up Firebase Configuration...'))
        
        env_file_path = os.path.join(settings.BASE_DIR, '.env')
        env_updates = {}
        
        # Handle service account file
        if options['service_account']:
            service_account_path = options['service_account']
            
            if os.path.exists(service_account_path):
                self.stdout.write(f'📁 Using service account file: {service_account_path}')
                env_updates['FIREBASE_CREDENTIALS_PATH'] = service_account_path
                
                # Also read the project ID from the service account file
                try:
                    with open(service_account_path, 'r') as f:
                        service_account_data = json.load(f)
                        project_id = service_account_data.get('project_id')
                        if project_id and not options['project_id']:
                            env_updates['FIREBASE_PROJECT_ID'] = project_id
                            self.stdout.write(f'📋 Extracted project ID: {project_id}')
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'⚠️  Could not read service account file: {e}'))
            else:
                self.stdout.write(self.style.ERROR(f'❌ Service account file not found: {service_account_path}'))
                return
        
        # Handle other options
        if options['project_id']:
            env_updates['FIREBASE_PROJECT_ID'] = options['project_id']
            
        if options['web_api_key']:
            env_updates['FIREBASE_WEB_API_KEY'] = options['web_api_key']
            
        if options['auth_domain']:
            env_updates['FIREBASE_AUTH_DOMAIN'] = options['auth_domain']
        elif options['project_id']:
            # Auto-generate auth domain from project ID
            env_updates['FIREBASE_AUTH_DOMAIN'] = f"{options['project_id']}.firebaseapp.com"
        
        if not env_updates:
            self.stdout.write(self.style.WARNING('⚠️  No configuration options provided'))
            self.stdout.write('Use --help to see available options')
            return
        
        # Update .env file
        self.update_env_file(env_file_path, env_updates)
        
        self.stdout.write(self.style.SUCCESS('✅ Firebase configuration updated'))
        self.stdout.write('\n🔄 Next steps:')
        self.stdout.write('   1. Restart the Django server')
        self.stdout.write('   2. Run: python manage.py setup_firebase --check')
        self.stdout.write('   3. Run: python manage.py test apps.api.tests.test_authentication.AuthenticationSystemArchitectureTest.test_firebase_integration_configuration')

    def update_env_file(self, env_file_path, updates):
        """Update .env file with new values"""
        env_lines = []
        
        # Read existing .env file if it exists
        if os.path.exists(env_file_path):
            with open(env_file_path, 'r') as f:
                env_lines = f.readlines()
        
        # Update or add new values
        updated_keys = set()
        
        for i, line in enumerate(env_lines):
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                key = line.split('=')[0]
                if key in updates:
                    env_lines[i] = f"{key}={updates[key]}\n"
                    updated_keys.add(key)
                    self.stdout.write(f'   Updated: {key}')
        
        # Add new keys that weren't found
        for key, value in updates.items():
            if key not in updated_keys:
                env_lines.append(f"{key}={value}\n")
                self.stdout.write(f'   Added: {key}')
        
        # Write back to .env file
        with open(env_file_path, 'w') as f:
            f.writelines(env_lines)
        
        self.stdout.write(f'📝 Updated {env_file_path}')

    def style_text(self, text, style_func):
        """Helper to style text"""
        return style_func(text)
