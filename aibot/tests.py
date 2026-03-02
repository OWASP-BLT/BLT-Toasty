"""
Tests for the GitHub App webhook functionality.
"""

import hashlib
import hmac
import json
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings


class WebhookViewTests(TestCase):
    """Test cases for the GitHub webhook endpoint."""

    def setUp(self):
        """Set up test data."""
        self.webhook_url = "/webhook/"
        self.webhook_secret = "test_webhook_secret"

    def _create_signature(self, payload):
        """Create a valid GitHub webhook signature."""
        signature = "sha256=" + hmac.new(
            self.webhook_secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return signature

    @override_settings(GITHUB_WEBHOOK_SECRET="test_webhook_secret")
    def test_ping_event(self):
        """Test that ping events return pong."""
        payload = json.dumps({"zen": "Keep it simple"})
        signature = self._create_signature(payload)

        response = self.client.post(
            self.webhook_url,
            data=payload,
            content_type="application/json",
            HTTP_X_GITHUB_EVENT="ping",
            HTTP_X_HUB_SIGNATURE_256=signature,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["message"], "Pong!")

    @override_settings(GITHUB_WEBHOOK_SECRET="test_webhook_secret")
    def test_invalid_signature(self):
        """Test that invalid signatures are rejected."""
        payload = json.dumps({"action": "created"})

        response = self.client.post(
            self.webhook_url,
            data=payload,
            content_type="application/json",
            HTTP_X_GITHUB_EVENT="issue_comment",
            HTTP_X_HUB_SIGNATURE_256="sha256=invalid",
        )

        self.assertEqual(response.status_code, 401)
        data = response.json()
        self.assertEqual(data["error"], "Invalid signature")

    @override_settings(GITHUB_WEBHOOK_SECRET="test_webhook_secret")
    def test_missing_signature(self):
        """Test that requests without signatures are rejected."""
        payload = json.dumps({"action": "created"})

        response = self.client.post(
            self.webhook_url, data=payload, content_type="application/json", HTTP_X_GITHUB_EVENT="issue_comment"
        )

        self.assertEqual(response.status_code, 401)

    @override_settings(
        GITHUB_WEBHOOK_SECRET="test_webhook_secret",
        GITHUB_APP_ID="123456",
        GITHUB_APP_INSTALLATION_ID="7891011",
    )
    @patch("aibot.views.GitHubAppAuth")
    def test_ping_command(self, mock_github_auth):
        """Test that /ping command triggers a response."""
        # Mock the GitHub API call
        mock_auth_instance = Mock()
        mock_github_auth.return_value = mock_auth_instance

        payload = json.dumps(
            {
                "action": "created",
                "comment": {"body": "/ping"},
                "issue": {"number": 123},
                "repository": {"name": "test-repo", "owner": {"login": "test-owner"}},
            }
        )
        signature = self._create_signature(payload)

        response = self.client.post(
            self.webhook_url,
            data=payload,
            content_type="application/json",
            HTTP_X_GITHUB_EVENT="issue_comment",
            HTTP_X_HUB_SIGNATURE_256=signature,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["message"], "Pong sent!")

        # Verify that create_comment was called
        mock_auth_instance.create_comment.assert_called_once_with(
            owner="test-owner",
            repo="test-repo",
            issue_number=123,
            body="🏓 Pong! The GitHub App is working correctly.",
        )

    @override_settings(GITHUB_WEBHOOK_SECRET="test_webhook_secret")
    def test_non_ping_comment(self):
        """Test that non-command comments are ignored."""
        payload = json.dumps(
            {
                "action": "created",
                "comment": {"body": "This is just a regular comment"},
                "issue": {"number": 123},
                "repository": {"name": "test-repo", "owner": {"login": "test-owner"}},
            }
        )
        signature = self._create_signature(payload)

        response = self.client.post(
            self.webhook_url,
            data=payload,
            content_type="application/json",
            HTTP_X_GITHUB_EVENT="issue_comment",
            HTTP_X_HUB_SIGNATURE_256=signature,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["message"], "No command recognized")

    @override_settings(GITHUB_WEBHOOK_SECRET="test_webhook_secret")
    def test_invalid_json(self):
        """Test that invalid JSON payloads are rejected."""
        signature = self._create_signature("invalid json")

        response = self.client.post(
            self.webhook_url,
            data="invalid json",
            content_type="application/json",
            HTTP_X_GITHUB_EVENT="issue_comment",
            HTTP_X_HUB_SIGNATURE_256=signature,
        )

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["error"], "Invalid JSON")
