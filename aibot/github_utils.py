"""
Utilities for GitHub App authentication and API interactions.
"""

import hashlib
import hmac
import time
from pathlib import Path

import jwt
import requests
from django.conf import settings


class GitHubAppAuth:
    """Handle GitHub App authentication and API requests."""

    def __init__(self):
        # Validate required settings
        if not settings.GITHUB_APP_ID:
            raise ValueError("GITHUB_APP_ID environment variable is required")
        if not settings.GITHUB_APP_INSTALLATION_ID:
            raise ValueError("GITHUB_APP_INSTALLATION_ID environment variable is required")

        self.app_id = str(settings.GITHUB_APP_ID)
        self.private_key = self._load_private_key()
        self.installation_id = settings.GITHUB_APP_INSTALLATION_ID

        # Cache for installation access token
        self._cached_token = None
        self._token_expiry = 0

    def _load_private_key(self):
        """Load the private key from file or environment variable."""
        # Try to load from environment variable first
        if settings.GITHUB_APP_PRIVATE_KEY:
            return settings.GITHUB_APP_PRIVATE_KEY.replace("\\n", "\n")

        # Otherwise load from file
        if settings.GITHUB_APP_PRIVATE_KEY_PATH:
            key_path = Path(settings.GITHUB_APP_PRIVATE_KEY_PATH)
            if key_path.exists():
                return key_path.read_text()

        raise ValueError("GitHub App private key not found in environment variables or file path")

    def generate_jwt(self):
        """Generate a JWT for authenticating as a GitHub App."""
        now = int(time.time())
        payload = {
            "iat": now - 60,  # Issued at time (60 seconds in the past to allow for clock drift)
            "exp": now + (10 * 60),  # Expiration time (10 minutes from now)
            "iss": self.app_id,
        }

        return jwt.encode(payload, self.private_key, algorithm="RS256")

    def get_installation_access_token(self):
        """Get an installation access token for making API requests.

        Caches the token and reuses it until it's near expiration.
        """
        # Return cached token if it's still valid (with 5 minute buffer)
        now = int(time.time())
        if self._cached_token and self._token_expiry > now + 300:
            return self._cached_token

        jwt_token = self.generate_jwt()

        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        url = f"https://api.github.com/app/installations/{self.installation_id}/access_tokens"
        try:
            response = requests.post(url, headers=headers, timeout=10)
            response.raise_for_status()
            token_data = response.json()

            # Cache the token and its expiry
            self._cached_token = token_data["token"]
            # GitHub tokens expire in 1 hour by default
            self._token_expiry = now + 3600

            return self._cached_token
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise ValueError("GitHub App authentication failed. Check your App ID and private key.") from e
            elif e.response.status_code == 404:
                raise ValueError("GitHub App installation not found. Check your installation ID.") from e
            else:
                raise ValueError(f"GitHub API error: {e.response.status_code}") from e
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Network error communicating with GitHub API: {e}") from e
        except (KeyError, ValueError) as e:
            raise ValueError(f"Invalid response from GitHub API: {e}") from e

    def create_comment(self, owner, repo, issue_number, body):
        """Create a comment on an issue or pull request."""
        token = self.get_installation_access_token()

        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/comments"
        data = {"body": body}

        try:
            response = requests.post(url, headers=headers, json=data, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                raise ValueError("GitHub App lacks permission to comment. Check repository permissions.") from e
            elif e.response.status_code == 404:
                raise ValueError(f"Repository or issue not found: {owner}/{repo}#{issue_number}") from e
            else:
                raise ValueError(f"GitHub API error: {e.response.status_code}") from e
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Network error communicating with GitHub API: {e}") from e


def verify_webhook_signature(request):
    """
    Verify that the webhook request came from GitHub.

    Args:
        request: Django HttpRequest object

    Returns:
        tuple: (bool, str) - (is_valid, error_message)
            - (True, "") if signature is valid
            - (False, "missing_signature") if signature header is missing
            - (False, "missing_secret") if webhook secret is not configured
            - (False, "invalid_signature") if signature doesn't match
    """
    signature_header = request.headers.get("X-Hub-Signature-256")
    if not signature_header:
        return False, "missing_signature"

    webhook_secret = settings.GITHUB_WEBHOOK_SECRET
    if not webhook_secret:
        return False, "missing_secret"

    # Calculate expected signature
    expected_signature = "sha256=" + hmac.new(
        webhook_secret.encode("utf-8"), request.body, hashlib.sha256
    ).hexdigest()

    # Use constant-time comparison to prevent timing attacks
    if hmac.compare_digest(signature_header, expected_signature):
        return True, ""
    else:
        return False, "invalid_signature"
