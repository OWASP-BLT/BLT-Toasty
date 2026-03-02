from django.db import models
from django.utils import timezone


class InstallationState(models.TextChoices):
    ACTIVE = "active", "Active"
    REMOVED = "removed", "Removed"
    SUSPENDED = "suspended", "Suspended"


class GithubAppInstallation(models.Model):
    installation_id = models.BigIntegerField(unique=True, primary_key=True)
    app_id = models.BigIntegerField()
    app_name = models.CharField(max_length=100)
    account_login = models.CharField(max_length=100)
    account_type = models.CharField(
        max_length=12,
        choices=[
            ("User", "User"),
            ("Organization", "Organization"),
        ],
    )
    state = models.CharField(
        max_length=20,
        choices=InstallationState.choices,
        default=InstallationState.ACTIVE,
    )
    activated_at = models.DateTimeField(null=True, blank=True)
    activated_by_account_login = models.CharField(max_length=100, null=True, blank=True)
    removed_at = models.DateTimeField(null=True, blank=True)
    removed_by_account_login = models.CharField(max_length=100, null=True, blank=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    suspended_by_account_login = models.CharField(max_length=100, null=True, blank=True)
    permissions = models.JSONField(help_text="Permissions granted to this installation", default=dict)
    subscribed_events = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.app_name} by {self.account_login} [{self.account_type} account] ({self.state}) id={self.installation_id}"

    def apply_webhook_state(self, action, sender_login=None):
        now = timezone.now()

        if action == "suspend":
            self.state = InstallationState.SUSPENDED
            self.suspended_at = now
            self.suspended_by_account_login = sender_login

        elif action == "remove":
            self.state = InstallationState.REMOVED
            self.removed_at = now
            self.removed_by_account_login = sender_login

        elif action == "activate":
            self.state = InstallationState.ACTIVE
            self.activated_at = now
            self.activated_by_account_login = sender_login
            self.suspended_at = None
            self.suspended_by_account_login = None


class RepoState(models.TextChoices):
    ACTIVE = "active", "Active"
    REMOVED = "removed", "Removed"
    PROCESSING = "processing", "Processing"
    ERROR = "error", "Error"
    ARCHIVED = "archived", "Archived"
    DELETED = "deleted", "Deleted"
    SUSPENDED = "suspended", "Suspended"


class GithubAppRepo(models.Model):
    installation = models.ForeignKey(GithubAppInstallation, on_delete=models.CASCADE, related_name="repositories")
    repo_id = models.BigIntegerField(unique=True)
    name = models.CharField(max_length=200)
    full_name = models.CharField(max_length=200)

    state = models.CharField(
        max_length=20,
        choices=RepoState.choices,
        default=RepoState.PROCESSING,
    )
    is_private = models.BooleanField(default=False)
    default_branch = models.CharField(max_length=100, default="main")
    permissions = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.installation.app_name} on {self.full_name} [{self.state}]"

    @property
    def http_url(self) -> str:
        return f"https://github.com/{self.full_name}"

    @property
    def api_url(self) -> str:
        return f"https://api.github.com/repos/{self.full_name}"

    @property
    def raw_content_url(self) -> str:
        return f"https://raw.githubusercontent.com/{self.full_name}"

    @property
    def qdrant_collection_name(self) -> str:
        # NOTE: Must stay in sync with `process_remote_repo` in `qdrant_utils`.
        # Use a filesystem/URL-safe token: owner__repo, lowercase.
        safe_full = self.full_name.replace("/", "__").lower()
        return f"aibot-{safe_full}-{self.repo_id}"


class AibotComment(models.Model):
    installation = models.ForeignKey(
        GithubAppInstallation,
        on_delete=models.SET_NULL,
        related_name="aibot_comments",
        help_text="The GitHub App installation that triggered this",
        null=True,
    )
    repository = models.ForeignKey(
        GithubAppRepo,
        on_delete=models.SET_NULL,
        related_name="aibot_comments",
        help_text="The repo where the comment was made",
        null=True,
    )
    issue_number = models.BigIntegerField(help_text="Issue or PR number on GitHub")
    comment_id = models.BigIntegerField(null=True, blank=True)
    comment_url = models.URLField(max_length=500, blank=True, null=True)
    comment_action = models.CharField(
        max_length=10, choices=[("posted", "Posted"), ("patched", "Patched")], default="posted"
    )
    revision = models.IntegerField(default=1)
    trigger_event = models.CharField(
        max_length=50, db_index=True, help_text="e.g., 'issue_comment.created', 'pull_request.opened'"
    )
    triggered_by_username = models.CharField(max_length=100, help_text="GitHub user who triggered the bot")
    trigger_comment_body = models.TextField(blank=True, null=True)
    prompt = models.TextField(help_text="Full prompt sent to LLM")
    response = models.TextField(help_text="AI-generated response")
    model_used = models.CharField(max_length=50, default="gemini-2.0-flash")
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveIntegerField(default=0)
    estimated_cost_usd = models.DecimalField(
        max_digits=10, decimal_places=6, null=True, blank=True, help_text="Estimated cost of this LLM call"
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        repo = self.repository.full_name if self.repository else "unknown-repo"
        return f"AI → {repo}#{self.issue_number} ({self.model_used})"

    def save(self, *args, **kwargs):
        self.total_tokens = self.prompt_tokens + self.completion_tokens
        if self.pk and self.comment_action == "patched":
            self.revision += 1
        super().save(*args, **kwargs)
