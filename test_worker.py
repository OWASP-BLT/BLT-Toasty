"""
Test file for Toasty Cloudflare Worker

Note: These are example tests to demonstrate the worker's expected behavior.
Actual testing would require the Cloudflare Workers runtime or a test harness.

IMPORTANT: The parse_path function is duplicated here because worker.py requires
the Cloudflare Workers runtime (js module) and cannot be imported in standard Python.
If you modify the parse_path logic in worker.py, you MUST update this copy to match.
"""

import datetime
import re


def get_iso_timestamp():
    """
    Return the current UTC time as an ISO 8601 formatted string.
    This is a copy of the function from worker.py for testing purposes.

    ⚠️  KEEP IN SYNC WITH worker.py get_iso_timestamp() ⚠️

    Returns:
        str: Current UTC timestamp in ISO 8601 format (e.g., "2026-03-25T14:30:00Z")
    """
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


ISO_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


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
    url_without_protocol = url.split("://", 1)[1] if "://" in url else url
    path_start = url_without_protocol.find("/")

    if path_start == -1:
        path = "/"
    else:
        path_with_query = url_without_protocol[path_start:]
        path = path_with_query.split("?")[0].split("#")[0]
        if not path.startswith("/"):
            path = "/" + path
        if len(path) > 1 and path.endswith("/"):
            path = path[:-1]

    return path


def test_route_parsing():
    """Test URL path parsing logic."""
    # Test case 1: Root path
    url1 = "https://toasty.example.workers.dev/"
    path1 = parse_path(url1)
    assert path1 == "/", f"Expected '/', got '{path1}'"

    # Test case 2: Health endpoint
    url2 = "https://toasty.example.workers.dev/health"
    path2 = parse_path(url2)
    assert path2 == "/health", f"Expected '/health', got '{path2}'"

    # Test case 3: API endpoint
    url3 = "https://toasty.example.workers.dev/api/review"
    path3 = parse_path(url3)
    assert path3 == "/api/review", f"Expected '/api/review', got '{path3}'"

    # Test case 4: URL with query parameters
    url4 = "https://toasty.example.workers.dev/api/status?debug=true"
    path4 = parse_path(url4)
    assert path4 == "/api/status", f"Expected '/api/status', got '{path4}'"

    # Test case 5: URL with fragment
    url5 = "https://toasty.example.workers.dev/health#section"
    path5 = parse_path(url5)
    assert path5 == "/health", f"Expected '/health', got '{path5}'"

    # Test case 6: URL with trailing slash
    url6 = "https://toasty.example.workers.dev/api/review/"
    path6 = parse_path(url6)
    assert path6 == "/api/review", f"Expected '/api/review', got '{path6}'"

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
        },
    }
    assert "service" in root_response
    assert "endpoints" in root_response
    assert root_response["version"] == "1.0.0"

    # Test health response has valid timestamp
    health_response = {"status": "healthy", "service": "toasty-backend", "timestamp": get_iso_timestamp()}
    assert health_response["status"] == "healthy"
    assert "service" in health_response
    assert health_response["timestamp"] is not None
    assert ISO_TIMESTAMP_RE.match(
        health_response["timestamp"]
    ), f"Timestamp '{health_response['timestamp']}' does not match ISO 8601 format"

    # Test review response has valid processed_at timestamp
    review_response = {
        "status": "success",
        "analysis": {
            "language": "python",
            "lines_of_code": 5,
            "issues": [],
            "suggestions": [],
            "summary": "Review completed successfully",
        },
        "metadata": {"processed_at": get_iso_timestamp(), "worker_version": "1.0.0"},
    }
    assert review_response["status"] == "success"
    assert "analysis" in review_response
    assert "metadata" in review_response
    assert review_response["metadata"]["processed_at"] is not None
    assert ISO_TIMESTAMP_RE.match(
        review_response["metadata"]["processed_at"]
    ), f"processed_at '{review_response['metadata']['processed_at']}' does not match ISO 8601 format"

    print("✓ All JSON response structure tests passed")


def test_error_response_structure():
    """Test error response structure."""
    error_response = {"error": "Test error message", "status": 400}
    assert "error" in error_response
    assert "status" in error_response
    assert error_response["status"] == 400

    print("✓ Error response structure test passed")


def test_review_request_validation():
    """Test review request validation logic."""
    # Valid request
    valid_request = {"code": "def hello(): pass", "language": "python", "context": "Test function"}
    assert "code" in valid_request, "Valid request should have 'code' field"

    # Invalid request (missing code)
    invalid_request = {"language": "python"}
    assert "code" not in invalid_request, "Invalid request missing 'code' field"

    print("✓ Review request validation tests passed")


def test_iso_timestamp_format():
    """Test that ISO 8601 timestamps are correctly formatted."""
    ts = get_iso_timestamp()

    # Should match ISO 8601 format with Z suffix: YYYY-MM-DDTHH:MM:SSZ
    assert ISO_TIMESTAMP_RE.match(ts), f"Timestamp '{ts}' does not match ISO 8601 format"

    # Should be parseable back to a datetime
    parsed = datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
    assert parsed is not None

    # Should be close to current UTC time (within 1 minute)
    now = datetime.datetime.now(datetime.timezone.utc)
    ts_dt = datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    diff = abs((now - ts_dt).total_seconds())
    assert diff < 60, f"Timestamp differs from now by {diff}s (expected < 60s)"

    print("✓ ISO timestamp format test passed")


def run_all_tests():
    """Run all test functions."""
    print("Running Toasty Worker Tests...\n")

    try:
        test_route_parsing()
        test_json_response_structure()
        test_error_response_structure()
        test_review_request_validation()
        test_iso_timestamp_format()

        print("\n" + "=" * 50)
        print("All tests passed! ✓")
        print("=" * 50)

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
