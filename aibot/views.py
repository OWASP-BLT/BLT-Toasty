import json
import logging

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .github_utils import GitHubAppAuth, verify_webhook_signature

logger = logging.getLogger(__name__)


def index(request):
    return HttpResponse("Hello from the AI Reviewer!")


@csrf_exempt
@require_http_methods(["POST"])
def webhook(request):
    """
    Handle incoming webhook events from GitHub.
    """
    # Verify webhook signature
    is_valid, error_reason = verify_webhook_signature(request)
    if not is_valid:
        if error_reason == "missing_secret":
            logger.error("GITHUB_WEBHOOK_SECRET is not configured. Unable to verify webhook signatures.")
            return JsonResponse({"error": "Server configuration error"}, status=500)
        elif error_reason == "missing_signature":
            logger.warning("Webhook request missing X-Hub-Signature-256 header")
            return JsonResponse({"error": "Missing signature"}, status=401)
        else:
            logger.warning("Invalid webhook signature")
            return JsonResponse({"error": "Invalid signature"}, status=401)

    # Parse the payload
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        logger.error("Invalid JSON payload")
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    # Get event type
    event_type = request.headers.get("X-GitHub-Event")
    logger.info(f"Received {event_type} event")

    # Handle different event types
    if event_type == "ping":
        return JsonResponse({"message": "Pong!"})

    elif event_type == "issue_comment":
        return handle_issue_comment(payload)

    elif event_type in ["pull_request", "pull_request_review", "pull_request_review_comment"]:
        return handle_pull_request(payload)

    # For other events, just acknowledge receipt
    return JsonResponse({"message": "Event received"})


def handle_issue_comment(payload):
    """
    Handle issue comment events.
    Processes commands like /ping.
    """
    # Only process new comments
    if payload.get("action") != "created":
        return JsonResponse({"message": "Not a new comment"})

    comment_body = payload.get("comment", {}).get("body", "").strip()
    issue_number = payload.get("issue", {}).get("number")
    repository = payload.get("repository", {})
    owner = repository.get("owner", {}).get("login")
    repo_name = repository.get("name")

    logger.info(f"Processing comment on {owner}/{repo_name}#{issue_number}: {comment_body}")

    # Handle /ping command
    if comment_body.lower() == "/ping":
        try:
            github_auth = GitHubAppAuth()
            github_auth.create_comment(
                owner=owner,
                repo=repo_name,
                issue_number=issue_number,
                body="🏓 Pong! The GitHub App is working correctly.",
            )
            return JsonResponse({"message": "Pong sent!"})
        except Exception:
            logger.exception("Error sending pong")
            return JsonResponse({"error": "Failed to send response. Check server logs for details."}, status=500)

    return JsonResponse({"message": "No command recognized"})


def handle_pull_request(payload):
    """
    Handle pull request events.
    This is a placeholder for future AI code review functionality.
    """
    action = payload.get("action")
    pr_number = payload.get("pull_request", {}).get("number")
    repository = payload.get("repository", {})
    owner = repository.get("owner", {}).get("login")
    repo_name = repository.get("name")

    logger.info(f"Pull request {action} on {owner}/{repo_name}#{pr_number}")

    # TODO: Implement AI code review logic here

    return JsonResponse({"message": "Pull request event received"})
