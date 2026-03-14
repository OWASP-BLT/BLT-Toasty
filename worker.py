"""
Cloudflare Worker for Toasty - AI Code Reviewer Backend

This worker handles API requests for the Toasty AI code review service.
It provides endpoints for code analysis, health checks, and status monitoring.
"""

from js import Response, Headers
import json

# Maximum request body size in bytes (1MB)
MAX_BODY_SIZE = 1024 * 1024



def parse_path(url):
    """
    Extract clean path from URL, handling query params and fragments.
    
    Args:
        url: The full URL string
        
    Returns:
        str: The path component of the URL
    """
    # Extract path from URL (handle query params and fragments)
    # Format: https://domain.com/path?query#fragment
    url_without_protocol = url.split('://', 1)[1] if '://' in url else url
    path_start = url_without_protocol.find('/')
    
    if path_start == -1:
        path = '/'
    else:
        # Get everything after the domain
        path_with_query = url_without_protocol[path_start:]
        # Remove query parameters and fragments
        path = path_with_query.split('?')[0].split('#')[0]
        # Ensure path starts with /
        if not path.startswith('/'):
            path = '/' + path
        # Remove trailing slash for consistent matching (except root)
        if len(path) > 1 and path.endswith('/'):
            path = path[:-1]
    
    return path


async def on_fetch(request, env):
    """
    Main entry point for Cloudflare Worker requests.
    
    Args:
        request: The incoming HTTP request
        env: Environment variables and bindings
        
    Returns:
        Response: HTTP response object
    """
    url = request.url
    method = request.method
    
    # Parse the URL to get the path
    try:
        path = parse_path(url)
    except Exception as e:
        return create_error_response(f"Error parsing URL: {str(e)}", 500)
    
    # Handle CORS preflight requests
    if method == 'OPTIONS':
        return handle_options(request)
    
    # Route requests based on path and method
    if path == '/' or path == '':
        if method in ('GET', 'HEAD'):
            return handle_root(request)
        else:
            return create_method_not_allowed_response(path, ['GET', 'HEAD'])
    elif path == '/health':
        if method in ('GET', 'HEAD'):
            return handle_health(request)
        else:
            return create_method_not_allowed_response(path, ['GET', 'HEAD'])
    elif path == '/api/review':
        if method == 'POST':
            return await handle_review(request, env)
        else:
            return create_method_not_allowed_response(path, ['POST'])
    elif path == '/api/status':
        if method in ('GET', 'HEAD'):
            return handle_status(request)
        else:
            return create_method_not_allowed_response(path, ['GET', 'HEAD'])
    else:
        return create_error_response(f"Not Found: {path}", 404)


def handle_options(request):
    """
    Handle CORS preflight OPTIONS requests.
    
    Args:
        request: The incoming HTTP request
        
    Returns:
        Response: 204 No Content with CORS headers
    """
    headers = Headers.new()
    headers.set("Access-Control-Allow-Origin", "*")
    headers.set("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
    headers.set("Access-Control-Allow-Headers", "Content-Type")
    headers.set("Access-Control-Max-Age", "86400")
    
    return Response.new("", status=204, headers=headers)


def handle_root(request):
    """
    Handle root endpoint requests.
    
    Args:
        request: The incoming HTTP request
        
    Returns:
        Response: Welcome message
    """
    response_data = {
        "service": "Toasty AI Code Reviewer",
        "version": "1.0.0",
        "description": "Backend API for OWASP BLT's AI-powered code review service",
        "endpoints": {
            "/": "Service information",
            "/health": "Health check endpoint",
            "/api/review": "POST - Submit code for review",
            "/api/status": "GET - Check service status"
        }
    }
    
    return create_json_response(response_data, 200)


def handle_health(request):
    """
    Handle health check endpoint.
    
    Args:
        request: The incoming HTTP request
        
    Returns:
        Response: Health status
    """
    health_data = {
        "status": "healthy",
        "service": "toasty-backend",
        "timestamp": None  # Would use datetime in production
    }
    
    return create_json_response(health_data, 200)


async def handle_review(request, env):
    """
    Handle code review requests by forwarding to Django backend.

    Args:
        request: The incoming HTTP request
        env: Environment variables and bindings

    Returns:
        Response: Code review results from Django backend
    """
    try:
        # Check Content-Length header if present
        content_length_header = request.headers.get('Content-Length')
        if content_length_header:
            try:
                content_length = int(content_length_header)
                if content_length > MAX_BODY_SIZE:
                    return create_error_response(
                        f"Request body too large. Maximum size is {MAX_BODY_SIZE} bytes",
                        413
                    )
            except ValueError:
                pass

        body = await request.text()

        if len(body.encode("utf-8")) > MAX_BODY_SIZE:
            return create_error_response(
                f"Request body too large. Maximum size is {MAX_BODY_SIZE} bytes",
                413
            )

        if not body:
            return create_error_response("Request body is required", 400)

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return create_error_response("Invalid JSON in request body", 400)

        code = data.get("code")
        if not isinstance(code, str) or not code.strip():
            return create_error_response("Missing or empty field: 'code'", 400)

        # Forward to Django backend
        backend_url = getattr(env, "BACKEND_URL", None)
        if not backend_url:
            return create_error_response("Backend URL not configured", 500)

        headers = Headers.new()
        headers.set("Content-Type", "application/json")

        backend_response = await js_fetch(
            backend_url + "/aibot/review/",
            method="POST",
            body=body,
            headers=headers
        )
        result_text = await backend_response.text()
        try:
            result = json.loads(result_text)
        except json.JSONDecodeError:
            result = {"error": "Invalid response from backend"}

        return create_json_response(result, backend_response.status)

    except Exception as e:
        return create_error_response("Error processing review request", 500)


def handle_status(request):
    """
    Handle status check endpoint.
    
    Args:
        request: The incoming HTTP request
        
    Returns:
        Response: Service status information
    """
    status_data = {
        "service": "toasty-backend",
        "status": "operational",
        "version": "1.0.0",
        "features": {
            "code_review": "available",
            "health_check": "available",
            "status_monitoring": "available"
        },
        "uptime": "available"
    }
    
    return create_json_response(status_data, 200)


def create_json_response(data, status_code=200):
    """
    Create a JSON response with proper headers.
    
    Args:
        data: Dictionary to serialize as JSON
        status_code: HTTP status code
        
    Returns:
        Response: JSON response object
    """
    headers = Headers.new()
    headers.set("Content-Type", "application/json")
    headers.set("Access-Control-Allow-Origin", "*")
    headers.set("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
    headers.set("Access-Control-Allow-Headers", "Content-Type")
    
    return Response.new(
        json.dumps(data),
        status=status_code,
        headers=headers
    )


def create_error_response(message, status_code=500):
    """
    Create an error response.
    
    Args:
        message: Error message
        status_code: HTTP status code
        
    Returns:
        Response: Error response object
    """
    error_data = {
        "error": message,
        "status": status_code
    }
    
    return create_json_response(error_data, status_code)


def create_method_not_allowed_response(path, allowed_methods):
    """
    Create a 405 Method Not Allowed response.
    
    Args:
        path: The request path
        allowed_methods: List of allowed HTTP methods
        
    Returns:
        Response: HTTP 405 response with Allow header
    """
    message = f"Method Not Allowed for {path}. Allowed methods: {', '.join(allowed_methods)}"
    
    headers = Headers.new()
    headers.set("Content-Type", "application/json")
    headers.set("Access-Control-Allow-Origin", "*")
    headers.set("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
    headers.set("Access-Control-Allow-Headers", "Content-Type")
    headers.set("Allow", ", ".join(allowed_methods))
    
    error_data = {
        "error": "Method Not Allowed",
        "message": message,
        "status": 405
    }
    
    return Response.new(
        json.dumps(error_data),
        status=405,
        headers=headers
    )

