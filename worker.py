"""
Cloudflare Worker for Toasty - AI Code Reviewer Backend

This worker handles API requests for the Toasty AI code review service.
It provides endpoints for code analysis, health checks, and status monitoring.
"""

from js import Response, Headers, fetch as js_fetch
import json
import hmac
import hashlib
from datetime import datetime, timezone

# Maximum request body size in bytes (1MB)
MAX_BODY_SIZE = 1024 * 1024



def verify_github_signature(payload_body: str, secret: str, signature_header: str) -> bool:
    """Validate GitHub webhook X-Hub-Signature-256 header."""
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        payload_body.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


async def generate_plan(issue_title: str, issue_body: str, env) -> str:
    """Generate an implementation plan using Gemini."""
    try:
        from google import genai
        api_key = getattr(env, "GEMINI_API_KEY", None)
        if not api_key:
            return "⚠️ AI plan generation is unavailable: missing GEMINI_API_KEY."
        prompt = f"""You are a senior software engineer.
Generate a clear, step-by-step implementation plan for the following GitHub issue.

**Issue Title:** {issue_title}

**Issue Description:**
{issue_body or 'No description provided.'}

Respond with a numbered markdown list of implementation steps."""
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        return f"## 🗺️ AI-Generated Implementation Plan\n\n{response.text}"
    except Exception as e:
        return f"⚠️ Failed to generate plan: {str(e)}"


async def post_github_comment(repo_full_name: str, issue_number: int, body: str, env) -> None:
    """Post a comment on a GitHub issue."""
    token = getattr(env, "GITHUB_TOKEN", None)
    if not token or not repo_full_name or not issue_number:
        return
    url = f"https://api.github.com/repos/{repo_full_name}/issues/{issue_number}/comments"
    payload = json.dumps({"body": body})
    headers = Headers.new()
    headers.set("Authorization", f"Bearer {token}")
    headers.set("Content-Type", "application/json")
    headers.set("Accept", "application/vnd.github+json")
    headers.set("X-GitHub-Api-Version", "2022-11-28")
    headers.set("User-Agent", "BLT-Toasty/1.0")
    await js_fetch(url, method="POST", headers=headers, body=payload)


async def handle_webhook(request, env):
    """Handle incoming GitHub webhook events."""
    body = await request.text()
    if len(body) > MAX_BODY_SIZE:
        return create_error_response("Payload too large", 413)

    sig = request.headers.get("X-Hub-Signature-256", "")
    secret = getattr(env, "GITHUB_WEBHOOK_SECRET", None)
    if not secret or not verify_github_signature(body, secret, sig):
        return create_error_response("Unauthorized: invalid signature", 401)

    event = request.headers.get("X-GitHub-Event", "")
    if event != "issue_comment":
        return create_json_response({"status": "ignored", "event": event}, 200)

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return create_error_response("Invalid JSON payload", 400)

    if payload.get("action") != "created":
        return create_json_response({"status": "ignored", "action": payload.get("action")}, 200)

    comment_body = payload.get("comment", {}).get("body", "").strip()
    if not comment_body.startswith("/plan"):
        return create_json_response({"status": "ignored", "reason": "not a /plan command"}, 200)

    issue = payload.get("issue", {})
    repo = payload.get("repository", {})
    issue_number = issue.get("number")
    repo_full_name = repo.get("full_name")
    issue_title = issue.get("title", "")
    issue_body = issue.get("body", "")

    plan = await generate_plan(issue_title, issue_body, env)
    await post_github_comment(repo_full_name, issue_number, plan, env)

    return create_json_response({"status": "ok", "command": "/plan"}, 200)


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
    elif path == '/webhook':
        if method == 'POST':
            return await handle_webhook(request, env)
        else:
            return create_method_not_allowed_response(path, ['POST'])
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
            "/api/status": "GET - Check service status",
            "/webhook": "POST - Receive GitHub webhook events (issue_comment /plan command)"
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
        
        # Placeholder for actual AI review logic
        # In production, this would call AI services, perform static analysis, etc.
        review_result = {
            "status": "success",
            "analysis": {
                "language": language,
                "lines_of_code": len(code.split('\n')),
                "issues": [],
                "suggestions": [
                    {
                        "type": "info",
                        "message": "Code review placeholder - integration with AI services pending",
                        "line": 0
                    }
                ],
                "summary": "Review completed successfully"
            },
            "metadata": {
                "processed_at": None,  # Would use datetime in production
                "worker_version": "1.0.0"
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

