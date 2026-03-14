import json
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings


def index(request):
    return HttpResponse("Hello from the AI Reviewer!")


@csrf_exempt
def review(request):
    """
    POST /aibot/review/
    Accepts code, language, and optional context.
    Calls Gemini API and returns structured review feedback.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    # Service-level authentication via shared bearer token
    expected_token = getattr(settings, "WORKER_SECRET", None)
    if expected_token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header != f"Bearer {expected_token}":
            return JsonResponse({"error": "Unauthorized"}, status=401)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    code = data.get("code", "").strip()
    language = data.get("language", "unknown")
    context = data.get("context", "")

    if not code:
        return JsonResponse({"error": "Field 'code' is required"}, status=400)

    api_key = getattr(settings, "GEMINI_API_KEY", None)
    if not api_key:
        return JsonResponse({"error": "GEMINI_API_KEY is not configured"}, status=500)

    try:
        from google import genai
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
            from .models import CodeReview
            CodeReview.objects.create(
                language=language,
                code_snippet=code,
                review_result=review_data
            )
        except Exception:
            pass  # Do not fail the response if persistence fails

        return JsonResponse({"status": "success", "analysis": review_data})

    except Exception as e:
        return JsonResponse({"error": "Review failed. Please try again later."}, status=500)
