"""
Cloudflare Worker for Toasty - AI Code Reviewer Backend

This worker handles API requests for the Toasty AI code review service.
It provides endpoints for code analysis, health checks, and status monitoring.
"""

from js import Response, Headers
import json
from datetime import datetime, timezone

# Maximum request body size in bytes (1MB)
MAX_BODY_SIZE = 1024 * 1024
DEFAULT_CLOUDFLARE_AI_MODEL = "@cf/meta/llama-3.1-8b-instruct"
MAX_AI_REVIEW_LENGTH = 6000



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
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    return create_json_response(health_data, 200)


async def handle_review(request, env):
    """
    Handle code review requests.
    
    Args:
        request: The incoming HTTP request
        env: Environment variables and bindings
        
    Returns:
        Response: Code review results
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
                pass  # Invalid Content-Length, will be caught during reading
        
        # Parse request body with size limit
        body = await request.text()
        
        if len(body) > MAX_BODY_SIZE:
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
        
        # Validate required fields
        if 'code' not in data:
            return create_error_response("Missing required field: 'code'", 400)
        
        code = data.get('code')
        
        # Validate that code is a non-empty string
        if not isinstance(code, str):
            return create_error_response("Field 'code' must be a string", 400)
        
        if not code or not code.strip():
            return create_error_response("Field 'code' cannot be empty", 400)
        
        language = data.get('language', 'unknown')
        context = data.get('context', '')

        ai_review, ai_error = await generate_cloudflare_ai_review(code, language, context, env)

        suggestions = []
        summary = "Review completed successfully"
        ai_provider = "cloudflare_workers_ai" if ai_review else "fallback"

        if ai_review:
            suggestions.append(
                {
                    "type": "info",
                    "message": ai_review,
                    "line": 0
                }
            )
        else:
            summary = "Review completed without Cloudflare AI response"
            fallback_message = "Cloudflare AI review unavailable"
            if ai_error:
                fallback_message = f"{fallback_message}: {ai_error}"
            suggestions.append(
                {
                    "type": "warning",
                    "message": fallback_message,
                    "line": 0
                }
            )
        
        review_result = {
            "status": "success",
            "analysis": {
                "language": language,
                "lines_of_code": len(code.split('\n')),
                "issues": [],
                "suggestions": suggestions,
                "summary": summary
            },
            "metadata": {
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "worker_version": "1.0.0",
                "ai_provider": ai_provider
            }
        }
        
        return create_json_response(review_result, 200)
        
    except Exception as e:
        return create_error_response(f"Error processing review request: {str(e)}", 500)


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
            "status_monitoring": "available",
            "cloudflare_ai_review": "available"
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


def extract_cloudflare_ai_text(ai_result):
    """
    Extract text output from Cloudflare AI response payloads.
    """
    if isinstance(ai_result, str):
        return ai_result

    if not isinstance(ai_result, dict):
        return ""

    for key in ("response", "result", "output", "text"):
        value = ai_result.get(key)
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, list):
            text_parts = []
            for item in value:
                if isinstance(item, dict):
                    item_text = item.get("text")
                    if isinstance(item_text, str):
                        text_parts.append(item_text)
                elif isinstance(item, str):
                    text_parts.append(item)
            merged = "\n".join(part for part in text_parts if part).strip()
            if merged:
                return merged

    return ""


async def generate_cloudflare_ai_review(code, language, context, env):
    """
    Generate review text using Cloudflare Workers AI binding.
    """
    ai_binding = getattr(env, "AI", None)
    if ai_binding is None:
        return None, "AI binding is not configured"

    prompt = (
        "You are an expert code reviewer. Provide concise review feedback.\n"
        f"Language: {language}\n"
        f"Context: {context or 'No additional context provided'}\n\n"
        "Code:\n"
        f"{code}\n\n"
        "Return a short markdown review with: strengths, issues, and improvement suggestions."
    )

    try:
        ai_result = await ai_binding.run(
            DEFAULT_CLOUDFLARE_AI_MODEL,
            {
                "prompt": prompt,
                "max_tokens": 700
            }
        )
    except Exception:
        return None, "request failed"

    ai_text = extract_cloudflare_ai_text(ai_result).strip()
    if not ai_text:
        return None, "empty response"

    if len(ai_text) > MAX_AI_REVIEW_LENGTH:
        ai_text = ai_text[:MAX_AI_REVIEW_LENGTH].rstrip() + "..."

    return ai_text, None
