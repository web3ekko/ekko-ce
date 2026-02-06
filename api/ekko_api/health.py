"""
Health check views for Ekko API
Provides endpoints for container health monitoring and load balancer checks
"""

import json
import time
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from django.db import connection
from django.core.cache import cache
from django.conf import settings


@never_cache
@require_http_methods(["GET"])
def health_check(request):
    """
    Basic health check endpoint
    Returns 200 OK if the service is running
    """
    return JsonResponse({
        "status": "healthy",
        "service": "ekko-api",
        "version": "1.0.0",
        "timestamp": time.time()
    })


@never_cache
@require_http_methods(["GET"])
def health_detailed(request):
    """
    Detailed health check with dependency status
    Checks database, cache, and other critical services
    """
    health_status = {
        "status": "healthy",
        "service": "ekko-api",
        "version": "1.0.0",
        "timestamp": time.time(),
        "checks": {}
    }
    
    overall_healthy = True
    
    # Database check
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        health_status["checks"]["database"] = {
            "status": "healthy",
            "message": "Database connection successful"
        }
    except Exception as e:
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "message": f"Database connection failed: {str(e)}"
        }
        overall_healthy = False
    
    # Cache check
    try:
        cache_key = "health_check_test"
        cache_value = "test_value"
        cache.set(cache_key, cache_value, 30)
        retrieved_value = cache.get(cache_key)
        
        if retrieved_value == cache_value:
            health_status["checks"]["cache"] = {
                "status": "healthy",
                "message": "Cache read/write successful"
            }
        else:
            health_status["checks"]["cache"] = {
                "status": "unhealthy",
                "message": "Cache read/write failed"
            }
            overall_healthy = False
            
        cache.delete(cache_key)
    except Exception as e:
        health_status["checks"]["cache"] = {
            "status": "unhealthy",
            "message": f"Cache connection failed: {str(e)}"
        }
        overall_healthy = False
    
    # Settings check
    try:
        required_settings = ['SECRET_KEY', 'ALLOWED_HOSTS']
        missing_settings = []
        
        for setting in required_settings:
            if not getattr(settings, setting, None):
                missing_settings.append(setting)
        
        if missing_settings:
            health_status["checks"]["configuration"] = {
                "status": "unhealthy",
                "message": f"Missing required settings: {', '.join(missing_settings)}"
            }
            overall_healthy = False
        else:
            health_status["checks"]["configuration"] = {
                "status": "healthy",
                "message": "All required settings present"
            }
    except Exception as e:
        health_status["checks"]["configuration"] = {
            "status": "unhealthy",
            "message": f"Configuration check failed: {str(e)}"
        }
        overall_healthy = False
    
    # Update overall status
    if not overall_healthy:
        health_status["status"] = "unhealthy"
    
    # Return appropriate HTTP status code
    status_code = 200 if overall_healthy else 503
    
    return JsonResponse(health_status, status=status_code)


@never_cache
@require_http_methods(["GET"])
def readiness_check(request):
    """
    Kubernetes readiness probe endpoint
    Checks if the service is ready to receive traffic
    """
    try:
        # Check database connectivity
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        
        # Check cache connectivity
        cache.set("readiness_test", "ready", 10)
        cache.get("readiness_test")
        cache.delete("readiness_test")
        
        return JsonResponse({
            "status": "ready",
            "timestamp": time.time()
        })
        
    except Exception as e:
        return JsonResponse({
            "status": "not_ready",
            "error": str(e),
            "timestamp": time.time()
        }, status=503)


@never_cache
@require_http_methods(["GET"])
def liveness_check(request):
    """
    Kubernetes liveness probe endpoint
    Simple check to verify the service is alive
    """
    return JsonResponse({
        "status": "alive",
        "timestamp": time.time()
    })


@never_cache
@require_http_methods(["GET"])
def metrics(request):
    """
    Basic metrics endpoint for monitoring
    Returns simple metrics in Prometheus format
    """
    if not getattr(settings, 'ENABLE_METRICS', True):
        return HttpResponse("Metrics disabled", status=404)
    
    try:
        # Database connection count
        db_connections = len(connection.queries) if settings.DEBUG else 0
        
        # Cache hit/miss ratio (simplified)
        cache_status = "1" if cache.get("metrics_test") is None else "0"
        cache.set("metrics_test", "1", 60)
        
        metrics_data = f"""# HELP ekko_api_up Service availability
# TYPE ekko_api_up gauge
ekko_api_up 1

# HELP ekko_api_db_connections Database connections
# TYPE ekko_api_db_connections gauge
ekko_api_db_connections {db_connections}

# HELP ekko_api_cache_available Cache availability
# TYPE ekko_api_cache_available gauge
ekko_api_cache_available {cache_status}

# HELP ekko_api_timestamp Current timestamp
# TYPE ekko_api_timestamp gauge
ekko_api_timestamp {time.time()}
"""
        
        return HttpResponse(metrics_data, content_type="text/plain")
        
    except Exception as e:
        return HttpResponse(f"# Error generating metrics: {str(e)}", 
                          content_type="text/plain", status=500)
