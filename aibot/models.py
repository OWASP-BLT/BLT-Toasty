from django.db import models


class CodeReview(models.Model):
    language = models.CharField(max_length=50, default="unknown")
    code_snippet = models.TextField()
    review_result = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Review ({self.language}) at {self.created_at}"
