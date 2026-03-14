import json
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.conf import settings


class ReviewEndpointTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.url = "/review/"
        self.valid_body = {"code": "print('hello')", "language": "python"}

    def _auth_headers(self):
        return {"HTTP_AUTHORIZATION": f"Bearer {settings.WORKER_SECRET}"}

    # --- Auth tests ---

    def test_missing_worker_secret_returns_503(self):
        """When WORKER_SECRET is not configured, return 503."""
        with self.settings(WORKER_SECRET=None):
            resp = self.client.post(
                self.url,
                data=json.dumps(self.valid_body),
                content_type="application/json"
            )
        self.assertEqual(resp.status_code, 503)

    def test_wrong_token_returns_401(self):
        """Wrong bearer token returns 401."""
        with self.settings(WORKER_SECRET="test-secret"):
            resp = self.client.post(
                self.url,
                data=json.dumps(self.valid_body),
                content_type="application/json",
                HTTP_AUTHORIZATION="Bearer wrongtoken"
            )
        self.assertEqual(resp.status_code, 401)

    def test_missing_auth_header_returns_401(self):
        """Missing Authorization header returns 401."""
        with self.settings(WORKER_SECRET="test-secret"):
            resp = self.client.post(
                self.url,
                data=json.dumps(self.valid_body),
                content_type="application/json"
            )
        self.assertEqual(resp.status_code, 401)

    # --- Input validation tests ---

    def test_invalid_json_returns_400(self):
        """Invalid JSON body returns 400."""
        with self.settings(WORKER_SECRET="test-secret"):
            resp = self.client.post(
                self.url,
                data="not json",
                content_type="application/json",
                HTTP_AUTHORIZATION="Bearer test-secret"
            )
        self.assertEqual(resp.status_code, 400)

    def test_missing_code_field_returns_400(self):
        """Missing code field returns 400."""
        with self.settings(WORKER_SECRET="test-secret"):
            resp = self.client.post(
                self.url,
                data=json.dumps({"language": "python"}),
                content_type="application/json",
                HTTP_AUTHORIZATION="Bearer test-secret"
            )
        self.assertEqual(resp.status_code, 400)

    def test_empty_code_returns_400(self):
        """Empty code field returns 400."""
        with self.settings(WORKER_SECRET="test-secret"):
            resp = self.client.post(
                self.url,
                data=json.dumps({"code": "   "}),
                content_type="application/json",
                HTTP_AUTHORIZATION="Bearer test-secret"
            )
        self.assertEqual(resp.status_code, 400)

    def test_wrong_method_returns_405(self):
        """GET request returns 405."""
        with self.settings(WORKER_SECRET="test-secret"):
            resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 405)

    # --- Gemini integration tests ---

    def test_valid_request_returns_success(self):
        """Valid request with mocked Gemini returns success."""
        mock_response = MagicMock()
        mock_response.text = '{"issues": [], "security_concerns": [], "suggestions": [], "summary": "Looks good"}'

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with self.settings(WORKER_SECRET="test-secret", GEMINI_API_KEY="fake-key"), \
             patch("aibot.views.genai.Client", return_value=mock_client):
            resp = self.client.post(
                self.url,
                data=json.dumps(self.valid_body),
                content_type="application/json",
                HTTP_AUTHORIZATION="Bearer test-secret"
            )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("analysis", data)
        analysis = data["analysis"]
        self.assertIn("issues", analysis)
        self.assertIn("security_concerns", analysis)
        self.assertIn("suggestions", analysis)
        self.assertIn("summary", analysis)

    def test_gemini_failure_returns_500(self):
        """Gemini API failure returns 500 with generic message."""
        with self.settings(WORKER_SECRET="test-secret", GEMINI_API_KEY="fake-key"), \
             patch("aibot.views.genai.Client", side_effect=Exception("API error")):
            resp = self.client.post(
                self.url,
                data=json.dumps(self.valid_body),
                content_type="application/json",
                HTTP_AUTHORIZATION="Bearer test-secret"
            )
        self.assertEqual(resp.status_code, 500)
        self.assertNotIn("API error", resp.json().get("error", ""))

    def test_persistence_failure_does_not_affect_response(self):
        """If CodeReview.objects.create fails, response still succeeds."""
        mock_response = MagicMock()
        mock_response.text = '{"summary": "ok"}'

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with self.settings(WORKER_SECRET="test-secret", GEMINI_API_KEY="fake-key"), \
             patch("aibot.views.genai.Client", return_value=mock_client), \
             patch("aibot.views.CodeReview.objects.create", side_effect=Exception("DB error")):
            resp = self.client.post(
                self.url,
                data=json.dumps(self.valid_body),
                content_type="application/json",
                HTTP_AUTHORIZATION="Bearer test-secret"
            )
        self.assertEqual(resp.status_code, 200)
