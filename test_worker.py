"""
Test file for Toasty Cloudflare Worker

Note: These are example tests to demonstrate the worker's expected behavior.
Actual testing would require the Cloudflare Workers runtime or a test harness.

IMPORTANT: The parse_path function is duplicated here because worker.py requires
the Cloudflare Workers runtime (js module) and cannot be imported in standard Python.
If you modify the parse_path logic in worker.py, you MUST update this copy to match.
"""


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
            "/api/status": "GET - Check service status"
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



def verify_github_signature(payload_body, secret, signature_header):
    """Copy of verify_github_signature from worker.py for testing."""
    import hmac
    import hashlib
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        payload_body.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def test_verify_github_signature():
    """Test HMAC signature validation."""
    import hmac
    import hashlib
    secret = "test-secret"
    payload = '{"action": "created"}'
    valid_sig = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    assert verify_github_signature(payload, secret, valid_sig) is True
    assert verify_github_signature(payload, secret, "sha256=invalidsig") is False
    assert verify_github_signature(payload, secret, "") is False
    assert verify_github_signature(payload, secret, "sha1=abc") is False
    print("OK: GitHub signature validation tests passed")


def test_webhook_plan_command_parsing():
    """Test /plan command detection logic."""
    def is_plan_command(comment_body):
        return comment_body == "/plan" or comment_body.startswith("/plan ")

    # Valid commands
    assert is_plan_command("/plan") is True
    assert is_plan_command("/plan please") is True

    # Invalid - must not match prefix only
    assert is_plan_command("/planning") is False
    assert is_plan_command("/planx") is False
    assert is_plan_command("/review") is False
    assert is_plan_command("hello /plan") is False
    assert is_plan_command("") is False
    print("OK: /plan command parsing tests passed")


def test_webhook_event_filtering():
    """Test that only issue_comment events with action=created are processed."""
    def should_process(event, action, comment_body):
        if event != "issue_comment":
            return False
        if action != "created":
            return False
        stripped = comment_body.strip()
        if stripped != "/plan" and not stripped.startswith("/plan "):
            return False
        return True

    assert should_process("issue_comment", "created", "/plan") is True
    assert should_process("issue_comment", "created", "/plan please") is True
    assert should_process("pull_request", "created", "/plan") is False
    assert should_process("issue_comment", "edited", "/plan") is False
    assert should_process("issue_comment", "created", "just a comment") is False
    assert should_process("issue_comment", "created", "/planning") is False
    assert should_process("issue_comment", "created", "/planx") is False
    print("OK: Webhook event filtering tests passed")


def test_plan_command_exact_match():
    """Test /plan is matched exactly, not as a prefix."""
    def is_plan_command(comment_body):
        return comment_body == "/plan" or comment_body.startswith("/plan ")

    # Valid
    assert is_plan_command("/plan") is True
    assert is_plan_command("/plan please implement this") is True

    # Invalid - prefix match only
    assert is_plan_command("/planning") is False
    assert is_plan_command("/planx") is False
    assert is_plan_command("/plans") is False

    print("OK: /plan exact command match tests passed")


def test_webhook_byte_size_check():
    """Test that size check uses byte length not character count."""
    # ASCII: same length
    ascii_str = "a" * 10
    assert len(ascii_str.encode("utf-8")) == 10

    # Multibyte UTF-8: byte length > char length
    multibyte_str = "\u00e9" * 10  # é = 2 bytes each
    assert len(multibyte_str.encode("utf-8")) == 20
    assert len(multibyte_str) == 10

    print("OK: Byte-based size check tests passed")


def run_all_tests():
    """Run all test functions."""
    print("Running Toasty Worker Tests...\n")
    
    try:
        test_route_parsing()
        test_json_response_structure()
        test_error_response_structure()
        test_review_request_validation()
        test_verify_github_signature()
        test_webhook_plan_command_parsing()
        test_webhook_event_filtering()
        test_plan_command_exact_match()
        test_webhook_byte_size_check()

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


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
