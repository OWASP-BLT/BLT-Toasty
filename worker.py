"""
Cloudflare Worker for Toasty - AI Code Reviewer Backend

This worker handles API requests for the Toasty AI code review service.
It provides endpoints for code analysis, health checks, and status monitoring.
"""

from js import Response, Headers, fetch as js_fetch, AbortSignal
import sys
import re
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
    headers.set("Access-Control-Allow-Headers", "Content-Type, Authorization")
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
    Handle code review requests using Gemini API directly from Cloudflare Worker.
    No Django backend required — runs entirely at the edge.

    Requires GEMINI_API_KEY and WORKER_SECRET secrets set via wrangler secret put.

    Args:
        request: The incoming HTTP request
        env: Environment variables and bindings

    Returns:
        Response: AI-generated code review results
    """
    try:
        # Auth gate — WORKER_SECRET is mandatory, fail closed if not configured
        worker_secret = getattr(env, "WORKER_SECRET", None)
        if not worker_secret:
            return create_error_response(
                "Service misconfigured: authentication not set up", 503
            )
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer ") or auth_header[7:] != worker_secret:
            return create_error_response("Unauthorized", 401)

        # Check Content-Length header if present
        content_length_header = request.headers.get("Content-Length")
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

        # Shape check — must be a JSON object
        if not isinstance(data, dict):
            return create_error_response(
                "Request body must be a JSON object",
                400
            )

        code = data.get("code")
        language = data.get("language", "unknown")
        # Sanitize language: strip whitespace and allow only safe characters
        language = re.sub(r"[^a-zA-Z0-9+#._-]", "", str(language).strip()) or "unknown"
        context = data.get("context", "")

        if not isinstance(code, str) or not code.strip():
            return create_error_response("Missing or empty field: 'code'", 400)

        # Get Gemini API key from Worker secrets
        gemini_api_key = getattr(env, "GEMINI_API_KEY", None)
        if not gemini_api_key:
            return create_error_response("AI service not configured", 500)

        # Build prompt — close code fence before JSON instructions
        prompt = (
            f"You are an expert code reviewer. Review the following {language} code.\n"
            f"Context: {context}\n\n"
            f"Code to review:\n"
            f"```{language}\n"
            f"{code}\n"
            f"```\n\n"
            'Respond ONLY with a valid JSON object (no markdown fences) in exactly this shape: '
            '{"status": "ok", "analysis": {"summary": "brief summary", '
            '"security_issues": [], "quality_issues": [], "suggestions": []}, '
            f'"metadata": {{"language": {json.dumps(language)}, "model": "gemini-2.0-flash"}}}}'
        )

        gemini_url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-2.0-flash:generateContent"
        )

        gemini_headers = Headers.new()
        gemini_headers.set("Content-Type", "application/json")
        gemini_headers.set("x-goog-api-key", gemini_api_key)

        gemini_payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 2048
            }
        })

        # Wrap js_fetch separately to catch timeout and network errors
        try:
            gemini_response = await js_fetch(
                gemini_url,
                method="POST",
                body=gemini_payload,
                headers=gemini_headers,
                signal=AbortSignal.timeout(30000)
            )
        except Exception as e:
            print(f"[toasty] Gemini fetch error: {type(e).__name__}: {e}", file=sys.stderr)
            return create_error_response("Service temporarily unavailable", 504)

        if not gemini_response.ok:
            return create_error_response("Failed to get review from AI service", 502)

        gemini_text = await gemini_response.text()

        try:
            gemini_data = json.loads(gemini_text)
            review_text = gemini_data["candidates"][0]["content"]["parts"][0]["text"]
            review = json.loads(review_text)
        except (json.JSONDecodeError, KeyError, IndexError):
            return create_error_response("Failed to parse AI response", 502)

        # Normalise to stable contract: status / analysis / metadata
        if not isinstance(review, dict):
            return create_error_response("Unexpected AI response shape", 502)

        analysis = review.get("analysis", review)
        if not isinstance(analysis, dict):
            analysis = {}

        # Coerce each analysis field individually
        summary = analysis.get("summary", "")
        if not isinstance(summary, str):
            summary = str(summary)

        security_issues = analysis.get("security_issues", [])
        if not isinstance(security_issues, list):
            security_issues = []

        quality_issues = analysis.get("quality_issues", [])
        if not isinstance(quality_issues, list):
            quality_issues = []

        suggestions = analysis.get("suggestions", [])
        if not isinstance(suggestions, list):
            suggestions = []

        # Coerce metadata fields individually
        metadata = review.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        meta_language = metadata.get("language", language)
        if not isinstance(meta_language, str):
            meta_language = language

        meta_model = metadata.get("model", "gemini-2.0-flash")
        if not isinstance(meta_model, str):
            meta_model = "gemini-2.0-flash"

        # Coerce status
        status = review.get("status", "ok")
        if not isinstance(status, str):
            status = "ok"

        return create_json_response({
            "status": status,
            "analysis": {
                "summary": summary,
                "security_issues": security_issues,
                "quality_issues": quality_issues,
                "suggestions": suggestions
            },
            "metadata": {
                "language": meta_language,
                "model": meta_model
            }
        }, 200)

    except Exception as e:
        print(f"[toasty] handle_review error: {type(e).__name__}: {e}", file=sys.stderr)
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
    headers.set("Access-Control-Allow-Headers", "Content-Type, Authorization")

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
    headers.set("Access-Control-Allow-Headers", "Content-Type, Authorization")
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
