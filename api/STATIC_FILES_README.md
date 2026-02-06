# Static Files Configuration

This API uses WhiteNoise to serve static files (including Django Admin assets) directly from the Django application, eliminating the need for a separate web server like nginx in development and simplifying production deployments.

## Configuration

### 1. WhiteNoise Middleware
WhiteNoise is configured in the middleware stack right after `SecurityMiddleware`:
```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    ...
]
```

### 2. Static Files Storage
Django 6.0+ uses the STORAGES setting:
```python
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
```

### 3. Static Files Collection
During the Docker build process, static files are collected:
```dockerfile
RUN mkdir -p /app/staticfiles \
    && python manage.py collectstatic --noinput --clear \
    && chown -R app:app /app
```

## Testing Static Files

### Check Configuration
```bash
docker-compose exec api python manage.py check_static
```

### Manual Collection
```bash
docker-compose exec api python manage.py collectstatic --noinput
```

### Verify Admin Access
1. Navigate to http://localhost:8000/admin/
2. Admin CSS and JS should load correctly
3. Check browser console for any 404 errors

## Troubleshooting

### Missing Admin Styles
If admin styles are missing:
1. Check that WhiteNoise is installed: `pip list | grep whitenoise`
2. Verify middleware configuration
3. Run `collectstatic` command
4. Check Docker logs for any errors

### Development vs Production
- **Development**: WhiteNoise auto-refreshes static files
- **Production**: Static files are compressed and cached

### Environment Variables
- `DJANGO_SETTINGS_MODULE`: Should be set appropriately
  - Development: `ekko_api.settings.development`
  - Production: `ekko_api.settings.production`

## Benefits
1. **Simplicity**: No need for nginx or separate static file server
2. **Security**: Static files served with proper headers
3. **Performance**: Files are compressed and cached
4. **Docker-friendly**: Everything runs in a single container
