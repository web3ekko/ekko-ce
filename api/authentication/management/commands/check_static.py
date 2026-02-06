from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.staticfiles import finders
import os


class Command(BaseCommand):
    help = 'Check static files configuration'

    def handle(self, *args, **options):
        self.stdout.write("Static Files Configuration:")
        self.stdout.write(f"STATIC_URL: {settings.STATIC_URL}")
        self.stdout.write(f"STATIC_ROOT: {settings.STATIC_ROOT}")
        self.stdout.write(f"STATICFILES_STORAGE: {settings.STATICFILES_STORAGE}")
        self.stdout.write("")
        
        # Check middleware
        if 'whitenoise.middleware.WhiteNoiseMiddleware' in settings.MIDDLEWARE:
            self.stdout.write(self.style.SUCCESS("✓ WhiteNoise middleware is installed"))
        else:
            self.stdout.write(self.style.ERROR("✗ WhiteNoise middleware is NOT installed"))
        
        # Check if admin static files can be found
        admin_css = finders.find('admin/css/base.css')
        if admin_css:
            self.stdout.write(self.style.SUCCESS(f"✓ Admin CSS found at: {admin_css}"))
        else:
            self.stdout.write(self.style.ERROR("✗ Admin CSS not found!"))
        
        # Check STATIC_ROOT exists
        if os.path.exists(settings.STATIC_ROOT):
            self.stdout.write(self.style.SUCCESS(f"✓ STATIC_ROOT exists: {settings.STATIC_ROOT}"))
            
            # Check for admin files
            admin_path = os.path.join(settings.STATIC_ROOT, 'admin')
            if os.path.exists(admin_path):
                self.stdout.write(self.style.SUCCESS(f"✓ Admin static files exist in STATIC_ROOT"))
            else:
                self.stdout.write(self.style.WARNING(f"⚠ Admin static files not found in STATIC_ROOT"))
        else:
            self.stdout.write(self.style.WARNING(f"⚠ STATIC_ROOT does not exist: {settings.STATIC_ROOT}"))