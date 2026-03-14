from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="CodeReview",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("language", models.CharField(default="unknown", max_length=50)),
                ("code_snippet", models.TextField()),
                ("review_result", models.JSONField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
