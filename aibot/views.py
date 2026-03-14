import json
import logging
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from google import genai
from .models import CodeReview

logger = logging.getLogger(__name__)


def index(request):
    return HttpResponse("Hello from the AI Reviewer!")


@csrf_exempt
def review(request):
    """
    POST /review/
    Accepts code, language, and optional context.
    Calls Gemini API and returns structured review feedback.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    # Service-level authentication via shared bearer token
    # Fail closed: if WORKER_SECRET is not configured, reject all requests
    expected_token = getattr(settings, "WORKER_SECRET", None)
    if not expected_token:
        return JsonResponse({"error": "Service authentication not configured"}, status=503)
    auth_header = request.headers.get("Authorization", "")
    if auth_header != f"Bearer {expected_token}":
        return JsonResponse({"error": "Unauthorized"}, status=401)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if not isinstance(data, dict):
        return JsonResponse({"error": "Request body must be a JSON object"}, status=400)

    code = data.get("code", "")
    if not isinstance(code, str):
        return JsonResponse({"error": "Field 'code' must be a string"}, status=400)
    code = code.strip()

    language = data.get("language", "unknown")
    if not isinstance(language, str):
        language = "unknown"
    language = language[:50]  # enforce DB max_length

    context = data.get("context", "")
    if not isinstance(context, str):
        context = ""

    if not code:
        return JsonResponse({"error": "Field 'code' is required"}, status=400)

    api_key = getattr(settings, "GEMINI_API_KEY", None)
    if not api_key:
        return JsonResponse({"error": "GEMINI_API_KEY is not configured"}, status=500)

    try:
        client = genai.Client(api_key=api_key)
        prompt = (
            f"Review the following {language} code and provide:\n"
            f"1. A list of bugs or issues\n"
            f"2. Security concerns\n"
            f"3. Improvement suggestions\n"
            f"4. A brief summary\n\n"
            f"Context: {context}\n\n"
            f"Code:\n```{language}\n{code}\n```\n\n"
            f"Respond in JSON with keys: issues, security_concerns, suggestions, summary."
        )
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        review_text = response.text
        # Strip markdown code fences if present
        clean = review_text.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        try:
            review_data = json.loads(clean)
        except json.JSONDecodeError:
            review_data = {"summary": review_text}

        # Persist review result
        try:
            CodeReview.objects.create(
                language=language,
                code_snippet=code,
                review_result=review_data
            )
        except Exception:
            logger.warning("Failed to persist CodeReview", exc_info=True)

        return JsonResponse({"status": "success", "analysis": review_data})

    except Exception as e:
        logger.exception("Gemini API call failed")
        return JsonResponse({"error": "Review failed. Please try again later."}, status=500)
