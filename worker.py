"""
Cloudflare Worker for Toasty - AI Code Reviewer Backend

This worker handles API requests for the Toasty AI code review service.
It provides endpoints for code analysis, health checks, and status monitoring.
"""

from js import Response, Headers
import json
import hmac
import hashlib
from datetime import datetime

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
    elif path == '/webhook/github':
        if method == 'POST':
            return await handle_github_webhook(request, env)
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
            "/webhook/github": "POST - GitHub App webhook endpoint"
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


async def handle_github_webhook(request, env):
    """
    Handle incoming GitHub webhooks.
    
    Args:
        request: The incoming HTTP request
        env: Environment variables and bindings
        
    Returns:
        Response: Webhook processing status
    """
    try:
        # 1. Get and Validate Headers
        signature = request.headers.get("X-Hub-Signature-256")
        event_type = request.headers.get("X-GitHub-Event")
        delivery_id = request.headers.get("X-GitHub-Delivery")
        
        if not signature or not event_type or not delivery_id:
            return create_error_response("Missing required GitHub headers (Signature, Event, or Delivery)", 400)
            
        # 1.1. Body Size Guard (Professional Practice)
        content_length = request.headers.get("Content-Length")
        if content_length and int(content_length) > MAX_BODY_SIZE:
            return create_error_response("Payload too large", 413)

        # 2. Extract Webhook Secret
        # Professional practice: Explicitly check for "development" before fallback
        environment = getattr(env, "ENVIRONMENT", None)
        webhook_secret = getattr(env, "GITHUB_WEBHOOK_SECRET", None)
            
        if not webhook_secret:
            # Fallback for development if secret not set
            if environment == "development":
                print("Warning: GITHUB_WEBHOOK_SECRET not set, skipping verification in development")
            else:
                return create_error_response("Webhook secret not configured", 500)

        # 3. Read payload as raw bytes for signature verification
        # Optimization: Rely on Pyodide's automatic JsProxy -> memoryview conversion
        payload_buffer = await request.arrayBuffer()
        payload_bytes = bytes(payload_buffer)
        
        # 4. Verify signature (if secret configured)
        if webhook_secret:
            if not verify_github_signature(signature, payload_bytes, webhook_secret):
                return create_error_response("Invalid webhook signature", 401)

        # 4.1. Webhook Replay Protection (Idempotency) 
        # Verified ONLY after signature validation for security.
        kv = getattr(env, "TOASTY_KV", None)
        if kv:
            is_duplicate = await check_is_duplicate_webhook(delivery_id, kv)
            if is_duplicate:
                print(f"Duplicate webhook detected: {delivery_id}. Skipping.")
                return create_json_response({
                    "status": "ignored",
                    "message": "Duplicate delivery ID",
                    "delivery_id": delivery_id
                }, 200)
        else:
            # Fail open for availability if KV is misconfigured
            if environment == "development":
                print("Warning: TOASTY_KV binding not found. Replay protection disabled.")
        
        # 5. Parse JSON payload
        try:
            payload = json.loads(payload_bytes.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return create_error_response("Invalid JSON or encoding in payload", 400)
            
        # 6. Route by event type
        if event_type == "ping":
            return create_json_response({"message": "pong", "zen": payload.get("zen")}, 200)
            
        elif event_type == "pull_request":
            action = payload.get("action")
            pr_number = payload.get("number")
            repo_name = payload.get("repository", {}).get("full_name")
            
            print(f"Received PR event: {action} for {repo_name}#{pr_number}")
            
            # TODO: Phase 2.4 - Fetch PR diff and trigger AI review
            return create_json_response({
                "status": "accepted",
                "message": f"PR {action} event received for {repo_name}#{pr_number}",
                "delivery_id": delivery_id
            }, 202)
            
        elif event_type == "issue_comment":
            action = payload.get("action")
            issue_number = payload.get("issue", {}).get("number")
            comment_body = payload.get("comment", {}).get("body", "")
            
            print(f"Received Issue Comment event: {action} on #{issue_number}")
            
            # Check if bot was mentioned
            if "@toasty-bot" in comment_body.lower():
                return create_json_response({
                    "status": "accepted",
                    "message": "Bot mention detected",
                    "delivery_id": delivery_id
                }, 202)
                
            return create_json_response({"status": "ignored", "reason": "No bot mention"}, 200)
            
        else:
            return create_json_response({
                "status": "ignored", 
                "message": f"Unsupported event type: {event_type}"
            }, 200)
            
    except (ValueError, KeyError) as e:
        return create_error_response(f"Malformed webhook data: {str(e)}", 400)
    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        import traceback
        traceback.print_exc()
        return create_error_response("Internal server error during webhook processing", 500)


async def check_is_duplicate_webhook(delivery_id, kv):
    """
    Check if this webhook delivery ID has been seen before using KV.
    
    Professional implementation:
    - Fails open (returns False) if KV errors occur to ensure availability.
    - Uses a 24-hour TTL for replay protection state.
    """
    try:
        key = f"webhook_delivery:{delivery_id}"
        existing = await kv.get(key)
        
        if existing:
            return True
            
        # Store for 24 hours (86400 seconds)
        await kv.put(key, "1", {"expirationTtl": 86400})
        return False
    except Exception as e:
        print(f"KV Error in replay protection: {str(e)}")
        return False


def verify_github_signature(signature_header, payload_bytes, secret):
    """
    Verify GitHub HMAC SHA256 signature.
    """
    if not signature_header.startswith("sha256="):
        return False
        
    expected_signature = signature_header[7:]
    
    # Calculate HMAC
    mac = hmac.new(secret.encode(), payload_bytes, hashlib.sha256)
    actual_signature = mac.hexdigest()
    
    return hmac.compare_digest(actual_signature, expected_signature)


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

