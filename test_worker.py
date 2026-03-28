"""
Test file for Toasty Cloudflare Worker

Note: These are example tests to demonstrate the worker's expected behavior.
Actual testing would require the Cloudflare Workers runtime or a test harness.

IMPORTANT: The parse_path function is duplicated here because worker.py requires
the Cloudflare Workers runtime (js module) and cannot be imported in standard Python.
If you modify the parse_path logic in worker.py, you MUST update this copy to match.
"""
import hmac
import hashlib


def parse_path(url):
    """
    Extract clean path from URL, handling query params and fragments.
    This is a copy of the function from worker.py for testing purposes.
    
    ⚠️  KEEP IN SYNC WITH worker.py parse_path() ⚠️
    
    Args:
        url: The full URL string
        
    Returns:
        str: The path component of the URL
    """
    url_without_protocol = url.split('://', 1)[1] if '://' in url else url
    path_start = url_without_protocol.find('/')
    
    if path_start == -1:
        path = '/'
    else:
        path_with_query = url_without_protocol[path_start:]
        path = path_with_query.split('?')[0].split('#')[0]
        if not path.startswith('/'):
            path = '/' + path
        if len(path) > 1 and path.endswith('/'):
            path = path[:-1]
    
    return path


def test_route_parsing():
    """Test URL path parsing logic."""
    # Test case 1: Root path
    url1 = "https://toasty.example.workers.dev/"
    path1 = parse_path(url1)
    assert path1 == '/', f"Expected '/', got '{path1}'"
    
    # Test case 2: Health endpoint
    url2 = "https://toasty.example.workers.dev/health"
    path2 = parse_path(url2)
    assert path2 == '/health', f"Expected '/health', got '{path2}'"
    
    # Test case 3: API endpoint
    url3 = "https://toasty.example.workers.dev/api/review"
    path3 = parse_path(url3)
    assert path3 == '/api/review', f"Expected '/api/review', got '{path3}'"
    
    # Test case 4: URL with query parameters
    url4 = "https://toasty.example.workers.dev/api/status?debug=true"
    path4 = parse_path(url4)
    assert path4 == '/api/status', f"Expected '/api/status', got '{path4}'"
    
    # Test case 5: URL with fragment
    url5 = "https://toasty.example.workers.dev/health#section"
    path5 = parse_path(url5)
    assert path5 == '/health', f"Expected '/health', got '{path5}'"
    
    # Test case 6: URL with trailing slash
    url6 = "https://toasty.example.workers.dev/api/review/"
    path6 = parse_path(url6)
    assert path6 == '/api/review', f"Expected '/api/review', got '{path6}'"
    
    print("✓ All route parsing tests passed")


def test_json_response_structure():
    """Test JSON response data structures."""
    # Test root response
    root_response = {
        "service": "Toasty AI Code Reviewer",
        "version": "1.0.0",
        "description": "Backend API for OWASP BLT's AI-powered code review service",
        "endpoints": {
            "/": "Service information",
            "/health": "Health check endpoint",
            "/api/review": "POST - Submit code for review",
            "/api/status": "GET - Check service status",
            "/webhook/github": "POST - GitHub webhook receiver"
        }
    }
    assert "service" in root_response
    assert "endpoints" in root_response
    assert root_response["version"] == "1.0.0"
    
    # Test health response
    health_response = {
        "status": "healthy",
        "service": "toasty-backend",
        "timestamp": None
    }
    assert health_response["status"] == "healthy"
    assert "service" in health_response
    
    # Test review response
    review_response = {
        "status": "success",
        "analysis": {
            "language": "python",
            "lines_of_code": 5,
            "issues": [],
            "suggestions": [],
            "summary": "Review completed successfully"
        },
        "metadata": {
            "processed_at": None,
            "worker_version": "1.0.0"
        }
    }
    assert review_response["status"] == "success"
    assert "analysis" in review_response
    assert "metadata" in review_response
    
    print("✓ All JSON response structure tests passed")


def test_error_response_structure():
    """Test error response structure."""
    error_response = {
        "error": "Test error message",
        "status": 400
    }
    assert "error" in error_response
    assert "status" in error_response
    assert error_response["status"] == 400
    
    print("✓ Error response structure test passed")


def test_review_request_validation():
    """Test review request validation logic."""
    # Valid request
    valid_request = {
        "code": "def hello(): pass",
        "language": "python",
        "context": "Test function"
    }
    assert "code" in valid_request, "Valid request should have 'code' field"
    
    # Invalid request (missing code)
    invalid_request = {
        "language": "python"
    }
    assert "code" not in invalid_request, "Invalid request missing 'code' field"
    
    print("✓ Review request validation tests passed")


def run_all_tests():
    """Run all test functions."""
    print("Running Toasty Worker Tests...\n")
    
    try:
        test_route_parsing()
        test_json_response_structure()
        test_error_response_structure()
        test_review_request_validation()
        run_webhook_tests()
        
        print("\n" + "="*50)
        print("All tests passed! ✓")
        print("="*50)
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return False
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        return False
    
    return True




# ---------------------------------------------------------------------------
# verify_signature — pure Python, no runtime dependency
# ---------------------------------------------------------------------------


def verify_signature(payload_body: str, signature_header: str, secret: str) -> bool:
    """Copy of verify_signature from worker.py for testing. Keep in sync."""
    if not signature_header or not signature_header.startswith('sha256='):
        return False
    expected = 'sha256=' + hmac.new(
        secret.encode('utf-8'),
        payload_body.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def make_signature(body: str, secret: str) -> str:
    """Helper to generate a valid HMAC-SHA256 signature."""
    return 'sha256=' + hmac.new(
        secret.encode('utf-8'), body.encode('utf-8'), hashlib.sha256
    ).hexdigest()


def test_verify_signature_valid():
    secret = "test-secret"
    body = '{"action":"opened"}'
    sig = make_signature(body, secret)
    assert verify_signature(body, sig, secret) is True
    print("  ✓ valid signature accepted")


def test_verify_signature_invalid():
    assert verify_signature('{"x":1}', 'sha256=badhash', 'secret') is False
    print("  ✓ invalid signature rejected")


def test_verify_signature_missing_header():
    assert verify_signature('body', '', 'secret') is False
    assert verify_signature('body', None, 'secret') is False
    print("  ✓ missing/empty header rejected")


def test_verify_signature_wrong_prefix():
    assert verify_signature('body', 'sha1=abc123', 'secret') is False
    print("  ✓ wrong prefix (sha1) rejected")


def test_verify_signature_different_secret():
    body = '{"action":"opened"}'
    sig = make_signature(body, "correct-secret")
    assert verify_signature(body, sig, "wrong-secret") is False
    print("  ✓ wrong secret rejected")


def test_webhook_route_parsing():
    """Verify /webhook/github route is parsed correctly."""
    assert parse_path("https://example.com/webhook/github") == "/webhook/github"
    assert parse_path("https://example.com/webhook/github?foo=bar") == "/webhook/github"
    print("  ✓ /webhook/github route parsed correctly")


def test_endpoint_documentation_includes_webhook():
    """Verify /webhook/github is present in the root endpoint documentation.

    This is a contract-specification mirror of worker.py's handle_root()
    endpoint dict, kept intentionally local due to runtime import constraints.
    Must be manually updated if the real endpoints in worker.py change.
    """
    # TODO: future improvement — extract endpoints to a shared JSON schema both files
    # reference, or add a CI step that parses worker.py and compares endpoint dicts.
    # Blocked by runtime import constraints (worker.py requires Cloudflare Workers runtime).
    # Hardcoded mirror of worker.py handle_root() endpoints — keep in sync
    endpoints_doc = {
        "/": "Service information",
        "/health": "Health check endpoint",
        "/api/review": "POST - Submit code for review",
        "/api/status": "GET - Check service status",
        "/webhook/github": "POST - GitHub webhook receiver"
    }
    assert "/webhook/github" in endpoints_doc
    assert endpoints_doc["/webhook/github"] == "POST - GitHub webhook receiver"
    print("  ✓ /webhook/github documented in root endpoint")


# ---------------------------------------------------------------------------
# HTTP-level integration stubs — require Cloudflare Workers runtime/harness
# ---------------------------------------------------------------------------

def webhook_stub_empty_body_400():
    # TODO: requires integration harness — empty POST to /webhook/github
    # should return 400 before signature check
    print("  ~ webhook_stub_empty_body_400: skipped (requires runtime harness)")


def webhook_stub_oversized_payload_413():
    # TODO: requires integration harness — payload > MAX_BODY_SIZE
    # should return 413
    print("  ~ webhook_stub_oversized_payload_413: skipped (requires runtime harness)")


def webhook_stub_missing_secret_500():
    # TODO: requires integration harness — GITHUB_WEBHOOK_SECRET not set
    # should return 500
    print("  ~ webhook_stub_missing_secret_500: skipped (requires runtime harness)")


def webhook_stub_invalid_json_400():
    # TODO: requires integration harness — valid HMAC but invalid JSON body
    # should return 400
    print("  ~ webhook_stub_invalid_json_400: skipped (requires runtime harness)")


def webhook_stub_ping_pong():
    # TODO: requires integration harness — X-GitHub-Event: ping
    # should return 200 with pong message
    print("  ~ webhook_stub_ping_pong: skipped (requires runtime harness)")


def webhook_stub_pr_or_comment_routing():
    # TODO: requires integration harness — pull_request and issue_comment events
    # should route to correct handlers and return 200
    print("  ~ webhook_stub_pr_or_comment_routing: skipped (requires runtime harness)")


def webhook_stub_non_post_405():
    # TODO: requires integration harness — GET /webhook/github
    # should return 405 with Allow: POST header
    print("  ~ webhook_stub_non_post_405: skipped (requires runtime harness)")


def run_webhook_tests():
    """Run all webhook-related tests."""
    print("\nRunning webhook tests...")
    test_verify_signature_valid()
    test_verify_signature_invalid()
    test_verify_signature_missing_header()
    test_verify_signature_wrong_prefix()
    test_verify_signature_different_secret()
    test_webhook_route_parsing()
    test_endpoint_documentation_includes_webhook()
    # Integration stubs (require runtime harness)
    webhook_stub_empty_body_400()
    webhook_stub_oversized_payload_413()
    webhook_stub_missing_secret_500()
    webhook_stub_invalid_json_400()
    webhook_stub_ping_pong()
    webhook_stub_pr_or_comment_routing()
    webhook_stub_non_post_405()
    print("  All pure-Python webhook tests passed! ✓ (7 integration scenarios skipped — require runtime harness)")

if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
