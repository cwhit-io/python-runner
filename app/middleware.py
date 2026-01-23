import time
import json
from django.utils.deprecation import MiddlewareMixin
from app.models import APILog


def get_client_ip(request):
    """Extract client IP address from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


class APILoggingMiddleware(MiddlewareMixin):
    """Middleware to log API requests and responses."""
    
    def process_request(self, request):
        """Store request start time."""
        request._api_log_start_time = time.time()
        return None
    
    def process_response(self, request, response):
        """Log API request after response is ready."""
        # Only log API endpoints (paths starting with /api/)
        if not request.path.startswith('/api/'):
            return response
        
        # Calculate duration
        start_time = getattr(request, '_api_log_start_time', None)
        duration_ms = None
        if start_time:
            duration_ms = (time.time() - start_time) * 1000
        
        # Get request body
        request_body = ''
        if request.method in ['POST', 'PUT', 'PATCH']:
            try:
                if hasattr(request, 'body'):
                    body = request.body.decode('utf-8')
                    # Try to format JSON nicely
                    try:
                        parsed = json.loads(body)
                        request_body = json.dumps(parsed, indent=2)
                    except (json.JSONDecodeError, ValueError):
                        request_body = body
                    # Limit body size to avoid bloat
                    if len(request_body) > 10000:
                        request_body = request_body[:10000] + '... [truncated]'
            except Exception:
                request_body = '[Could not decode body]'
        
        # Get response body
        response_body = ''
        try:
            if hasattr(response, 'content'):
                content = response.content.decode('utf-8')
                # Try to format JSON nicely
                try:
                    parsed = json.loads(content)
                    response_body = json.dumps(parsed, indent=2)
                except (json.JSONDecodeError, ValueError):
                    response_body = content
                # Limit response size
                if len(response_body) > 10000:
                    response_body = response_body[:10000] + '... [truncated]'
        except Exception:
            response_body = '[Could not decode response]'
        
        # Get query parameters
        query_params = request.GET.urlencode() if request.GET else ''
        
        # Create log entry
        try:
            APILog.objects.create(
                method=request.method,
                path=request.path,
                full_path=request.get_full_path(),
                user=request.user if request.user.is_authenticated else None,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                query_params=query_params,
                request_body=request_body,
                status_code=response.status_code,
                response_body=response_body,
                duration_ms=duration_ms,
            )
        except Exception as e:
            # Don't fail the request if logging fails
            print(f"Failed to log API request: {e}")
        
        return response
    
    def process_exception(self, request, exception):
        """Log exceptions that occur during request processing."""
        # Only log API endpoints
        if not request.path.startswith('/api/'):
            return None
        
        # Calculate duration
        start_time = getattr(request, '_api_log_start_time', None)
        duration_ms = None
        if start_time:
            duration_ms = (time.time() - start_time) * 1000
        
        # Get request body
        request_body = ''
        if request.method in ['POST', 'PUT', 'PATCH']:
            try:
                if hasattr(request, 'body'):
                    body = request.body.decode('utf-8')
                    request_body = body[:10000]  # Limit size
            except Exception:
                request_body = '[Could not decode body]'
        
        # Get query parameters
        query_params = request.GET.urlencode() if request.GET else ''
        
        # Create log entry for the error
        try:
            APILog.objects.create(
                method=request.method,
                path=request.path,
                full_path=request.get_full_path(),
                user=request.user if request.user.is_authenticated else None,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                query_params=query_params,
                request_body=request_body,
                status_code=500,
                error=f"{type(exception).__name__}: {str(exception)}"[:5000],
                duration_ms=duration_ms,
            )
        except Exception as e:
            # Don't fail the request if logging fails
            print(f"Failed to log API exception: {e}")
        
        return None  # Let Django handle the exception normally
